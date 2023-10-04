from amaranth import Cat, C, Module, Signal, Elaboratable, Memory
from amaranth.lib.wiring import Component, Signature, In, Out

from .ucodefields import PcAction, RegOp


PcSignature = Signature({
    "pc": In(32),
    "action": Out(PcAction),
    "dat_w": Out(30)
})


class ProgramCounter(Component):
    signature = PcSignature.flip()

    def elaborate(self, platform):
        m = Module()

        with m.Switch(self.action):
            with m.Case(PcAction.INC):
                m.d.sync += self.pc.eq(self.pc + 4)
            with m.Case(PcAction.LOAD):
                m.d.sync += self.pc.eq(Cat(C(0, 2), self.dat_w))

        return m


class RegFile(Elaboratable):
    def __init__(self):
        self.adr = Signal(5)
        self.dat_r = Signal(32)
        self.dat_w = Signal(32)
        self.action = Signal(RegOp)
        self.mem = Memory(width=32, depth=32)

    def elaborate(self, platform):
        m = Module()

        adr_prev = Signal.like(self.adr)

        # Re: transparent, let's attempt to save some resources for now.
        m.submodules.rdport = rdport = self.mem.read_port()
        m.submodules.wrport = wrport = self.mem.write_port()

        m.d.comb += [
            rdport.addr.eq(self.adr),
            wrport.addr.eq(self.adr),
            wrport.data.eq(self.dat_w),
        ]

        # We have to simulate a single cycle latency for accessing the zero
        # reg.
        m.d.sync += adr_prev.eq(self.adr)

        # Zero register logic- ignore writes/return 0 for reads.
        with m.If((adr_prev == 0) & (self.adr == 0)):
            m.d.comb += self.dat_r.eq(0)
        with m.Else():
            m.d.comb += [
                self.dat_r.eq(rdport.data),
                wrport.en.eq(self.action == RegOp.WRITE_DST)
            ]

        return m


DataPathControlSignature = Signature({
    "gp_action": Out(RegOp),
    "pc_action": Out(PcAction)
})


DataPathSignature = Signature({
    "gp": Out(Signature({
        "adr": Out(5),
        "dat_r": In(32),
        "dat_w": Out(32),
    })),
    "pc": Out(Signature({
        "dat_r": In(32),
        "dat_w": Out(32),
    })),
    "ctrl": Out(DataPathControlSignature)
})


class DataPath(Component):
    signature = DataPathSignature.flip()

    def __init__(self):
        super().__init__()

        self.pc_mod = ProgramCounter()
        self.regfile = RegFile()

    def elaborate(self, platform):
        m = Module()

        m.submodules.pc_mod = self.pc_mod
        m.submodules.regfile = self.regfile

        m.d.comb += [
            self.regfile.adr.eq(self.gp.adr),
            self.regfile.dat_w.eq(self.gp.dat_w),
            self.regfile.action.eq(self.ctrl.gp_action),
            self.gp.dat_r.eq(self.regfile.dat_r),

            self.pc_mod.action.eq(self.ctrl.pc_action),
            self.pc.dat_r.eq(self.pc_mod.pc),
            self.pc_mod.dat_w.eq(self.pc.dat_w[2:])
        ]

        return m
