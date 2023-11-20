from amaranth import Signal, Module
from amaranth.lib.wiring import Component, Signature, Out, In

from .csr import MCause, MStatus, MIP, MIE
from .ucodefields import MemSel, ExceptCtl


ExceptionSourcesSignature = Signature({
    "alu_lo": Out(2),
    "csr": Out(Signature({
        "mstatus": Out(MStatus),
        "mip": Out(MIP),
        "mie": Out(MIE)
    })),
    "ctrl": Out(Signature({
        "mem_sel": Out(MemSel),
        "except_ctl": Out(ExceptCtl)
    })),
    "decode": Out(Signature({
        "exception": Out(1),
        "e_type": Out(MCause.Cause)
    })),
})


ExceptionResultSignature = Signature({
    "exception": Out(1),
    "mcause": Out(MCause)
})


class ExceptionRouter(Component):
    src: In(ExceptionSourcesSignature)
    out: Out(ExceptionResultSignature)

    def elaborate(self, platform):
        m = Module()

        exception = Signal(1)
        mcause_latch = Signal(MCause)

        m.d.comb += [
            self.out.exception.eq(exception),
            self.out.mcause.eq(mcause_latch)
        ]

        with m.If(self.src.ctrl.except_ctl == ExceptCtl.LATCH_DECODER):
            with m.If(self.src.decode.exception):
                m.d.comb += exception.eq(1)
                m.d.sync += mcause_latch.cause.eq(self.src.decode.e_type)

            with m.If(self.src.csr.mstatus.mie & self.src.csr.mip.meip &
                      self.src.csr.mie.meie):
                m.d.comb += exception.eq(1)
                m.d.sync += [
                    mcause_latch.cause.eq(11),
                    mcause_latch.interrupt.eq(1)
                ]
        with m.Elif(self.src.ctrl.except_ctl == ExceptCtl.LATCH_STORE_ADR):
            with m.If((((self.src.ctrl.mem_sel == MemSel.HWORD) &
                        self.src.alu_lo[0] == 1)) |
                      ((self.src.ctrl.mem_sel == MemSel.WORD) &
                      ((self.src.alu_lo[0] == 1) |
                       (self.src.alu_lo[1] == 1)))):
                m.d.comb += exception.eq(1)
                m.d.sync += mcause_latch.cause.eq(
                    MCause.Cause.STORE_MISALIGNED)
        with m.Elif(self.src.ctrl.except_ctl == ExceptCtl.LATCH_LOAD_ADR):
            with m.If((((self.src.ctrl.mem_sel == MemSel.HWORD) &
                        self.src.alu_lo[0] == 1)) |
                      ((self.src.ctrl.mem_sel == MemSel.WORD) &
                      ((self.src.alu_lo[0] == 1) |
                       (self.src.alu_lo[1] == 1)))):
                m.d.comb += exception.eq(1)
                m.d.sync += mcause_latch.cause.eq(MCause.Cause.LOAD_MISALIGNED)
        with m.Elif(self.src.ctrl.except_ctl == ExceptCtl.LATCH_JAL):
            with m.If(self.src.alu_lo[1] == 1):
                m.d.comb += exception.eq(1)
                m.d.sync += mcause_latch.cause.eq(MCause.Cause.INSN_MISALIGNED)

        return m
