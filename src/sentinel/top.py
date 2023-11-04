from amaranth import Signal, Module, Cat, C
from amaranth.lib.wiring import Component, Signature, Out, In, connect
from amaranth_soc import wishbone

from .alu import ALU
from .control import Control
from .csr import MCause
from .datapath import DataPath
from .decode import Decode
from .ucodefields import ASrc, BSrc, RegRSel, RegWSel, MemSel, \
    MemExtend, CSRSel, CSROp, ExceptCtl


class Top(Component):
    @property
    def signature(self):
        if self.formal:
            return Signature({
                "bus": Out(wishbone.Signature(addr_width=30, data_width=32,
                                              granularity=8)),
                # Helper internal signals for RVFI that are not otherwise
                # exposed.
                "rvfi": Out(Signature({
                    "exception": Out(1)
                })),
                "irq": In(1)
            })
        else:
            return Signature({
                "bus": Out(wishbone.Signature(addr_width=30, data_width=32,
                                              granularity=8)),
                "irq": In(1)
            })

    def __init__(self, *, formal=False):
        self.formal = formal
        super().__init__()

        self.req_next = Signal()
        self.insn_fetch_curr = Signal()
        self.insn_fetch_next = Signal()

        ###

        self.alu = ALU(32)
        self.control = Control()
        self.datapath = DataPath(formal=formal)
        self.decode = Decode()

        # ALU
        self.a_input = Signal(32)
        self.b_input = Signal(32)

        # Decode
        self.reg_r_adr = Signal(6)
        self.reg_w_adr = Signal(6)

    def elaborate(self, platform):
        m = Module()

        m.submodules.alu = self.alu
        m.submodules.control = self.control
        m.submodules.datapath = self.datapath
        m.submodules.decode = self.decode

        # Exception handling.
        mcause_latch = Signal(MCause)
        exception = Signal(1)
        data_adr = Signal.like(self.alu.data.o)

        m.d.comb += [
            self.datapath.csr.mip_w.meip.eq(self.irq),
            self.datapath.csr.ctrl.exception.eq(self.control.except_ctl)
        ]

        with m.If(self.control.except_ctl == ExceptCtl.LATCH_DECODER):
            with m.If(self.decode.exception):
                m.d.comb += exception.eq(1)
                m.d.sync += mcause_latch.cause.eq(self.decode.e_type)

            with m.If(self.datapath.csr.mstatus_r.mie &
                      self.datapath.csr.mip_r.meip &
                      self.datapath.csr.mie_r.meie):
                m.d.comb += exception.eq(1)
                m.d.sync += [
                    mcause_latch.cause.eq(11),
                    mcause_latch.interrupt.eq(1)
                ]
        with m.Elif(self.control.except_ctl == ExceptCtl.LATCH_STORE_ADR):
            with m.If((((self.control.mem_sel == MemSel.HWORD) &
                        self.alu.data.o[0] == 1)) |
                      ((self.control.mem_sel == MemSel.WORD) &
                       ((self.alu.data.o[0] == 1) |
                        (self.alu.data.o[1] == 1)))):
                m.d.comb += exception.eq(1)
                m.d.sync += mcause_latch.cause.eq(
                    MCause.Cause.STORE_MISALIGNED)
        with m.Elif(self.control.except_ctl == ExceptCtl.LATCH_LOAD_ADR):
            with m.If((((self.control.mem_sel == MemSel.HWORD) &
                        self.alu.data.o[0] == 1)) |
                      ((self.control.mem_sel == MemSel.WORD) &
                       ((self.alu.data.o[0] == 1) |
                        (self.alu.data.o[1] == 1)))):
                m.d.comb += exception.eq(1)
                m.d.sync += mcause_latch.eq(MCause.Cause.LOAD_MISALIGNED)
        with m.Elif(self.control.except_ctl == ExceptCtl.LATCH_JAL):
            with m.If(self.alu.data.o[1] == 1):
                m.d.comb += exception.eq(1)
                m.d.sync += mcause_latch.cause.eq(MCause.Cause.INSN_MISALIGNED)

        # ALU conns
        connect(m, self.alu.ctrl, self.control.alu)

        # ALU conns
        m.d.comb += [
            self.alu.data.a.eq(self.a_input),
            self.alu.data.b.eq(self.b_input),
        ]

        # Connect ALU sources
        with m.If(self.control.latch_a):
            with m.Switch(self.control.a_src):
                with m.Case(ASrc.GP):
                    m.d.sync += self.a_input.eq(self.datapath.gp.dat_r)
                with m.Case(ASrc.IMM):
                    m.d.sync += self.a_input.eq(self.decode.imm)
                with m.Case(ASrc.ZERO):
                    m.d.sync += self.a_input.eq(0)
                with m.Case(ASrc.ALU_O):
                    m.d.sync += self.a_input.eq(self.alu.data.o)
                with m.Case(ASrc.FOUR):
                    m.d.sync += self.a_input.eq(4)
                with m.Case(ASrc.NEG_ONE):
                    m.d.sync += self.a_input.eq(C(-1, 32))
                with m.Case(ASrc.THIRTY_ONE):
                    m.d.sync += self.a_input.eq(31)

        raw_dat_r = Signal.like(self.b_input)
        with m.If(self.control.latch_b):
            with m.Switch(self.control.b_src):
                with m.Case(BSrc.GP):
                    m.d.sync += self.b_input.eq(self.datapath.gp.dat_r)
                with m.Case(BSrc.IMM):
                    m.d.sync += self.b_input.eq(self.decode.imm)
                with m.Case(BSrc.ONE):
                    m.d.sync += self.b_input.eq(1)
                with m.Case(BSrc.PC):
                    m.d.sync += self.b_input.eq(Cat(C(0, 2),
                                                    self.datapath.pc.dat_r))
                with m.Case(BSrc.DAT_R):
                    with m.Switch(self.control.mem_sel):
                        with m.Case(MemSel.BYTE):
                            with m.If(data_adr[0:2] == 0):
                                m.d.comb += raw_dat_r.eq(self.bus.dat_r[0:8])
                            with m.Elif(data_adr[0:2] == 1):
                                m.d.comb += raw_dat_r.eq(self.bus.dat_r[8:16])
                            with m.Elif(data_adr[0:2] == 2):
                                m.d.comb += raw_dat_r.eq(self.bus.dat_r[16:24])
                            with m.Else():
                                m.d.comb += raw_dat_r.eq(self.bus.dat_r[24:])

                            with m.If(self.control.mem_extend == MemExtend.SIGN):  # noqa: E501
                                m.d.sync += self.b_input.eq(raw_dat_r[0:8].as_signed())  # noqa: E501
                            with m.Else():
                                m.d.sync += self.b_input.eq(raw_dat_r[0:8])
                        with m.Case(MemSel.HWORD):
                            with m.If(data_adr[1] == 0):
                                m.d.comb += raw_dat_r.eq(self.bus.dat_r[0:16])
                            with m.Else():
                                m.d.comb += raw_dat_r.eq(self.bus.dat_r[16:])

                            with m.If(self.control.mem_extend == MemExtend.SIGN):  # noqa: E501
                                m.d.sync += self.b_input.eq(raw_dat_r[0:16].as_signed())  # noqa: E501
                            with m.Else():
                                m.d.sync += self.b_input.eq(raw_dat_r[0:16])
                        with m.Case(MemSel.WORD):
                            m.d.sync += self.b_input.eq(self.bus.dat_r)
                with m.Case(BSrc.CSR_IMM):
                    m.d.sync += self.b_input.eq(self.decode.src_a)
                with m.Case(BSrc.CSR):
                    m.d.sync += self.b_input.eq(self.datapath.csr.dat_r)
                with m.Case(BSrc.MCAUSE_LATCH):
                    m.d.sync += self.b_input.eq(mcause_latch)

        # Control conns
        m.d.comb += [
            self.control.opcode.eq(self.decode.opcode),
            self.control.requested_op.eq(self.decode.requested_op),
            self.control.e_type.eq(self.decode.e_type),
            self.req_next.eq(self.control.mem_req),
            self.insn_fetch_next.eq(self.control.insn_fetch),
            self.control.mem_valid.eq(self.bus.ack),

            # TODO: Spin out into a register of exception sources.
            self.control.exception.eq(self.decode.exception | exception)
        ]

        # An ACK stops the request b/c the microcode's to avoid a 1-cycle delay
        # due to registered REQ/FETCH signal.
        m.d.comb += [
            self.bus.cyc.eq(self.control.mem_req),
            self.bus.stb.eq(self.control.mem_req),
            # self.insn_fetch.eq(self.control.insn_fetch)
        ]

        m.d.comb += [
            self.datapath.gp.ctrl.reg_read.eq(self.control.gp.reg_read),
            self.datapath.gp.ctrl.reg_write.eq(self.control.gp.reg_write),
            self.datapath.csr.ctrl.op.eq(self.control.csr.op),
            self.datapath.pc.ctrl.action.eq(self.control.pc.action)
        ]

        # connect(m, self.datapath.gp.ctrl, self.control.gp)
        # connect(m, self.datapath.pc.ctrl, self.control.pc)

        write_data = Signal.like(self.bus.dat_w)
        with m.If(self.control.latch_data):
            # TODO: Misaligned accesses
            with m.Switch(self.control.mem_sel):
                with m.Case(MemSel.BYTE):
                    with m.If(data_adr[0:2] == 0):
                        m.d.sync += write_data[0:8].eq(self.alu.data.o[0:8])
                    with m.Elif(data_adr[0:2] == 1):
                        m.d.sync += write_data[8:16].eq(self.alu.data.o[0:8])
                    with m.Elif(data_adr[0:2] == 2):
                        m.d.sync += write_data[16:24].eq(self.alu.data.o[0:8])
                    with m.Else():
                        m.d.sync += write_data[24:].eq(self.alu.data.o[0:8])
                with m.Case(MemSel.HWORD):
                    with m.If(data_adr[1] == 0):
                        m.d.sync += write_data[0:16].eq(self.alu.data.o[0:16])
                    with m.Else():
                        m.d.sync += write_data[16:].eq(self.alu.data.o[0:16])
                with m.Case(MemSel.WORD):
                    m.d.sync += write_data.eq(self.alu.data.o)

        m.d.comb += [
            self.bus.we.eq(self.control.write_mem),
            self.bus.dat_w.eq(write_data),
            self.datapath.gp.dat_w.eq(self.alu.data.o),
            self.datapath.gp.adr_r.eq(self.reg_r_adr),
            self.datapath.gp.adr_w.eq(self.reg_w_adr),
            # FIXME: Compressed insns.
            self.datapath.pc.dat_w.eq(self.alu.data.o[2:]),
            self.datapath.csr.dat_w.eq(self.alu.data.o)
        ]

        with m.If(self.control.latch_adr):
            m.d.sync += data_adr.eq(self.alu.data.o)

        # DataPath.dat_w constantly has traffic. We only want to latch
        # the address once per mem access, and we want it the address to be
        # valid synchronous with ready assertion.
        with m.If(self.bus.cyc & self.bus.stb):
            with m.If(self.insn_fetch_next):
                m.d.comb += [self.bus.adr.eq(self.datapath.pc.dat_r),
                             self.bus.sel.eq(0xf)]
            with m.Else():
                m.d.comb += self.bus.adr.eq(data_adr[2:])

                # TODO: Misaligned accesses
                with m.Switch(self.control.mem_sel):
                    with m.Case(MemSel.BYTE):
                        with m.If(data_adr[0:2] == 0):
                            m.d.comb += self.bus.sel.eq(1)
                        with m.Elif(data_adr[0:2] == 1):
                            m.d.comb += self.bus.sel.eq(2)
                        with m.Elif(data_adr[0:2] == 2):
                            m.d.comb += self.bus.sel.eq(4)
                        with m.Else():
                            m.d.comb += self.bus.sel.eq(8)
                    with m.Case(MemSel.HWORD):
                        with m.If(data_adr[1] == 0):
                            m.d.comb += self.bus.sel.eq(3)
                        with m.Else():
                            m.d.comb += self.bus.sel.eq(0xc)
                    with m.Case(MemSel.WORD):
                        m.d.comb += self.bus.sel.eq(0xf)

        # Decode conns
        m.d.comb += [
            self.decode.insn.eq(self.bus.dat_r),
            # Decode begins automatically.
            self.decode.do_decode.eq(self.control.insn_fetch & self.bus.ack),
        ]

        with m.Switch(self.control.reg_r_sel):
            with m.Case(RegRSel.INSN_RS1):
                with m.If(self.control.insn_fetch):
                    m.d.comb += self.reg_r_adr.eq(self.decode.rs1)
                with m.Else():
                    m.d.comb += self.reg_r_adr.eq(self.decode.src_a)
            with m.Case(RegRSel.INSN_RS2):
                m.d.comb += self.reg_r_adr.eq(self.decode.src_b)

        with m.Switch(self.control.reg_w_sel):
            with m.Case(RegWSel.INSN_RD):
                m.d.comb += self.reg_w_adr.eq(self.decode.dst)
            with m.Case(RegWSel.ZERO):
                m.d.comb += [
                    self.reg_w_adr.eq(0),
                    self.datapath.gp.ctrl.allow_zero_wr.eq(1)
                ]

        with m.Switch(self.control.csr_sel):
            with m.Case(CSRSel.INSN_CSR):
                with m.If(self.control.csr.op != CSROp.NONE):
                    m.d.comb += [
                        self.datapath.gp.ctrl.reg_read.eq(self.control.csr.op
                                                          == CSROp.READ_CSR),
                        self.datapath.gp.ctrl.reg_write.eq(self.control.csr.op
                                                           == CSROp.WRITE_CSR),
                        self.reg_r_adr.eq(self.decode.csr_encoding),
                        self.reg_w_adr.eq(self.decode.csr_encoding),
                        self.datapath.gp.ctrl.csr_access.eq(1),
                        self.datapath.csr.adr_r.eq(self.decode.csr_encoding),
                        self.datapath.csr.adr_w.eq(self.decode.csr_encoding)
                    ]

            with m.Case(CSRSel.TRG_CSR):
                with m.If(self.control.csr.op != CSROp.NONE):
                    m.d.comb += [
                        self.datapath.gp.ctrl.reg_read.eq(self.control.csr.op
                                                          == CSROp.READ_CSR),
                        self.datapath.gp.ctrl.reg_write.eq(self.control.csr.op
                                                           == CSROp.WRITE_CSR),
                        self.reg_r_adr.eq(self.control.target[0:4]),
                        self.reg_w_adr.eq(self.control.target[0:4]),
                        self.datapath.gp.ctrl.csr_access.eq(1),
                        self.datapath.csr.adr_w.eq(self.control.target[0:4]),
                        self.datapath.csr.adr_r.eq(self.control.target[0:4]),
                    ]

        if self.formal:
            m.d.comb += self.rvfi.exception.eq(exception)

        return m
