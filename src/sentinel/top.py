from amaranth import Signal, Module, Cat, C
from amaranth.lib.wiring import Component, Signature, Out, In, connect, flipped
from amaranth_soc import wishbone

from .alu import ALU, ASrcMux, BSrcMux
from .align import AddressAlign, WriteDataAlign
from .control import Control
from .datapath import DataPath
from .decode import Decode
from .exception import ExceptionRouter
from .ucodefields import ASrc, BSrc, RegRSel, RegWSel, MemSel, \
    MemExtend, CSRSel


class Top(Component):
    def __init__(self, *, formal=False):
        self.formal = formal

        self.req_next = Signal()
        self.insn_fetch_curr = Signal()
        self.insn_fetch_next = Signal()

        ###

        self.alu = ALU(32)
        self.addr_align = AddressAlign()
        self.a_src = ASrcMux()
        self.b_src = BSrcMux()
        self.control = Control()
        self.datapath = DataPath(formal=formal)
        self.decode = Decode(formal=formal)
        self.exception_router = ExceptionRouter()
        self.wdata_align = WriteDataAlign()

        # ALU
        self.a_input = Signal(32)
        self.b_input = Signal(32)

        # Decode
        self.reg_r_adr = Signal(6)
        self.reg_w_adr = Signal(6)

        sig = {
                "bus": Out(wishbone.Signature(addr_width=30, data_width=32,
                                              granularity=8)),
                "irq": In(1)
        }
        if self.formal:
            sig["rvfi"] = Out(Signature({
                    "exception": Out(1),
                    "decode": Out(self.decode.rvfi.signature)
            }))

        super().__init__(sig)

    def elaborate(self, platform):
        m = Module()

        m.submodules.alu = self.alu
        m.submodules.addr_align = self.addr_align
        m.submodules.a_src = self.a_src
        m.submodules.b_src = self.b_src
        m.submodules.control = self.control
        m.submodules.datapath = self.datapath
        m.submodules.decode = self.decode
        m.submodules.exception_router = self.exception_router
        m.submodules.wdata_align = self.wdata_align

        data_adr = Signal.like(self.alu.o)

        with m.If(self.control.latch_adr):
            m.d.sync += data_adr.eq(self.alu.o)

        m.d.comb += [
            self.datapath.csr.mip_w.meip.eq(self.irq),
            self.datapath.csr.ctrl.exception.eq(self.control.except_ctl)
        ]

        # ALU conns
        connect(m, self.alu.ctrl, self.control.alu)

        m.d.comb += [
            self.alu.a.eq(self.a_src.data),
            self.a_src.latch.eq(self.control.latch_a),
            self.a_src.sel.eq(self.control.a_src),
            self.a_src.gp.eq(self.datapath.gp.dat_r),
            self.a_src.imm.eq(self.decode.imm),
            self.a_src.alu.eq(self.alu.o),

            self.alu.b.eq(self.b_src.data),
            self.b_src.latch.eq(self.control.latch_b),
            self.b_src.sel.eq(self.control.b_src),
            self.b_src.gp.eq(self.datapath.gp.dat_r),
            self.b_src.imm.eq(self.decode.imm),
            self.b_src.pc.eq(self.datapath.pc.dat_r),
            self.b_src.dat_r.eq(self.bus.dat_r),
            self.b_src.csr_imm.eq(self.decode.src_a),
            self.b_src.csr.eq(self.datapath.csr.dat_r),
            self.b_src.mcause.eq(self.exception_router.out.mcause)
        ]

        # Control conns
        m.d.comb += [
            self.control.opcode.eq(self.decode.opcode),
            self.control.requested_op.eq(self.decode.requested_op),
            self.req_next.eq(self.control.mem_req),
            self.insn_fetch_next.eq(self.control.insn_fetch),
            self.control.mem_valid.eq(self.bus.ack),

            # TODO: Spin out into a register of exception sources.
            self.control.exception.eq(self.exception_router.out.exception)
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
        m.d.comb += [
            self.bus.we.eq(self.control.write_mem),
            self.bus.dat_w.eq(write_data),
            self.datapath.gp.dat_w.eq(self.alu.o),
            self.datapath.gp.adr_r.eq(self.reg_r_adr),
            self.datapath.gp.adr_w.eq(self.reg_w_adr),
            # FIXME: Compressed insns.
            self.datapath.pc.dat_w.eq(self.alu.o[2:]),
            self.datapath.csr.dat_w.eq(self.alu.o)
        ]

        # Alignment conns
        m.d.comb += [
            self.addr_align.mem_req.eq(self.control.mem_req),
            self.addr_align.mem_sel.eq(self.control.mem_sel),
            self.addr_align.insn_fetch.eq(self.control.insn_fetch),
            self.addr_align.latched_adr.eq(data_adr),
            self.addr_align.pc.eq(self.datapath.pc.dat_r),
            self.bus.adr.eq(self.addr_align.wb_adr),
            self.bus.sel.eq(self.addr_align.wb_sel),

            self.b_src.mem_sel.eq(self.control.mem_sel),
            self.b_src.mem_extend.eq(self.control.mem_extend),
            self.b_src.data_adr.eq(data_adr),

            self.wdata_align.mem_sel.eq(self.control.mem_sel),
            self.wdata_align.latched_adr.eq(data_adr),
            self.wdata_align.data.eq(self.alu.o),
        ]

        with m.If(self.control.latch_data):
            m.d.sync += write_data.eq(self.wdata_align.wb_dat_w)

        # Decode conns
        m.d.comb += [
            self.decode.insn.eq(self.bus.dat_r),
            # Decode begins automatically.
            self.decode.do_decode.eq(self.control.insn_fetch & self.bus.ack),
        ]

        with m.Switch(self.control.reg_r_sel):
            with m.Case(RegRSel.INSN_RS1):
                with m.If(self.control.insn_fetch):
                    m.d.comb += self.reg_r_adr.eq(self.decode.src_a_unreg)
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

        # CSR Op/Address control (data conns taken care above)
        m.d.comb += self.datapath.csr.ctrl.op.eq(self.control.csr.op)
        with m.Switch(self.control.csr_sel):
            with m.Case(CSRSel.INSN_CSR):
                m.d.comb += self.datapath.csr.adr.eq(self.decode.csr_encoding)
            with m.Case(CSRSel.TRG_CSR):
                m.d.comb += self.datapath.csr.adr.eq(self.control.target[0:4])

        # Exception Router sources
        m.d.comb += [
            self.exception_router.src.alu_lo.eq(self.alu.o[0:2]),
            self.exception_router.src.csr.mstatus.eq(
                self.datapath.csr.mstatus_r),
            self.exception_router.src.csr.mip.eq(self.datapath.csr.mip_r),
            self.exception_router.src.csr.mie.eq(self.datapath.csr.mie_r),
            self.exception_router.src.ctrl.mem_sel.eq(self.control.mem_sel),
            self.exception_router.src.ctrl.except_ctl.eq(
                self.control.except_ctl),
            self.exception_router.src.decode.eq(self.decode.exception),
        ]

        if self.formal:
            m.d.comb += self.rvfi.exception.eq(
                self.exception_router.out.exception)
            connect(m, flipped(self.rvfi.decode), self.decode.rvfi)

        return m
