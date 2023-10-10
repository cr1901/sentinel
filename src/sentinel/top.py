from amaranth import Signal, Elaboratable, Module, Cat, C
from amaranth.lib.wiring import Component, Signature, Out, connect
from amaranth_soc import wishbone

from .alu import ALU
from .control import Control
from .datapath import DataPath
from .decode import Decode
from .ucodefields import ASrc, BSrc, SrcOp, RegRSel, MemSel


class Top(Component):
    signature = Signature({
        "bus": Out(wishbone.Signature(addr_width=30, data_width=32,
                                      granularity=8)),
    })

    def __init__(self):
        super().__init__()

        self.req_next = Signal()
        self.insn_fetch_curr = Signal()
        self.insn_fetch_next = Signal()

        ###

        self.alu = ALU(32)
        self.control = Control()
        self.datapath = DataPath()
        self.decode = Decode()

        # ALU
        self.a_input = Signal(32)
        self.b_input = Signal(32)

        # Decode
        self.reg_r_adr = Signal(5)
        self.reg_w_adr = Signal(5)

    def elaborate(self, platform):
        m = Module()

        m.submodules.alu = self.alu
        m.submodules.control = self.control
        m.submodules.datapath = self.datapath
        m.submodules.decode = self.decode

        # ALU conns
        a_mux_o = Signal(32)
        b_mux_o = Signal(32)
        connect(m, self.alu.ctrl, self.control.alu)

        # ALU conns
        m.d.comb += [
            self.alu.data.a.eq(self.a_input),
            self.alu.data.b.eq(self.b_input),
        ]

        # Connect ALU sources
        with m.If((self.control.src_op == SrcOp.LATCH_A) |
                  (self.control.src_op == SrcOp.LATCH_A_B)):
            with m.Switch(self.control.a_src):
                with m.Case(ASrc.GP):
                    m.d.sync += self.a_input.eq(self.datapath.gp.dat_r)
                with m.Case(ASrc.IMM):
                    m.d.sync += self.a_input.eq(self.decode.imm)
                with m.Case(ASrc.PC):
                    m.d.sync += self.a_input.eq(Cat(C(0, 2),
                                                    self.datapath.pc.dat_r))
                with m.Case(ASrc.ZERO):
                    m.d.sync += self.a_input.eq(0)
                with m.Case(ASrc.ALU_O):
                    m.d.sync += self.a_input.eq(self.alu.data.o)

        with m.If((self.control.src_op == SrcOp.LATCH_B) |
                  (self.control.src_op == SrcOp.LATCH_A_B)):
            with m.Switch(self.control.b_src):
                with m.Case(BSrc.GP):
                    m.d.sync += self.b_input.eq(self.datapath.gp.dat_r)
                with m.Case(BSrc.IMM):
                    m.d.sync += self.b_input.eq(self.decode.imm)
                with m.Case(BSrc.TARGET):
                    m.d.sync += self.b_input.eq(self.decode.dst)
                with m.Case(BSrc.ONE):
                    m.d.sync += self.b_input.eq(1)
                with m.Case(BSrc.FOUR):
                    m.d.sync += self.b_input.eq(4)

        # Control conns
        m.d.comb += [
            self.control.opcode.eq(self.decode.opcode),
            self.control.requested_op.eq(self.decode.requested_op),
            self.control.e_type.eq(self.decode.e_type),
            self.req_next.eq(self.control.mem_req),
            self.insn_fetch_next.eq(self.control.insn_fetch),
            self.control.mem_valid.eq(self.bus.ack),

            # TODO: Spin out into a register of exception sources.
            self.control.exception.eq(self.decode.illegal)
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
            self.datapath.pc.ctrl.action.eq(self.control.pc.action)
        ]

        # connect(m, self.datapath.gp.ctrl, self.control.gp)
        # connect(m, self.datapath.pc.ctrl, self.control.pc)

        write_data = Signal.like(self.bus.dat_w)
        with m.If(self.control.latch_data):
            m.d.sync += write_data.eq(self.alu.data.o)

        m.d.comb += [
            self.bus.we.eq(self.control.write_mem),
            self.bus.dat_w.eq(write_data),
            self.datapath.gp.dat_w.eq(self.alu.data.o),
            self.datapath.gp.adr_r.eq(self.reg_r_adr),
            self.datapath.gp.adr_w.eq(self.reg_w_adr),
            # FIXME: Compressed insns.
            self.datapath.pc.dat_w.eq(self.alu.data.o[2:]),
        ]

        data_adr = Signal.like(self.bus.adr)
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
                m.d.comb += self.bus.adr.eq(data_adr)

                with m.Switch(self.control.mem_sel):
                    with m.Case(MemSel.BYTE):
                        m.d.comb += self.bus.sel.eq(1)
                    with m.Case(MemSel.HWORD):
                        m.d.comb += self.bus.sel.eq(3)
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
                m.d.comb += self.reg_r_adr.eq(self.decode.src_a)
            with m.Case(RegRSel.INSN_RS2):
                m.d.comb += self.reg_r_adr.eq(self.decode.src_b)
            with m.Case(RegRSel.INSN_RS1_UNREGISTERED):
                m.d.comb += self.reg_r_adr.eq(self.decode.rs1)

        m.d.comb += self.reg_w_adr.eq(self.decode.dst)

        return m


class TopMem(Elaboratable):
    def __init__(self):

        self.top = Top()
