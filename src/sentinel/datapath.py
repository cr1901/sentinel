import enum

from amaranth import Cat, C, Module, Signal, Elaboratable, Memory
from amaranth.lib.wiring import Component, Signature, In, Out


class PcAction(enum.Enum):
    HOLD = 0
    INC = 1
    LOAD_ABS = 2
    LOAD_REL = 3


class ProgramCounter(Elaboratable):
    def __init__(self):
        self.pc = Signal(32)
        self.action = Signal(PcAction)
        self.dat_w = Signal(30)

    def elaborate(self, platform):
        m = Module()

        with m.Switch(self.action):
            with m.Case(PcAction.INC):
                m.d.sync += self.pc.eq(self.pc + 4)
            with m.Case(PcAction.LOAD_ABS):
                m.d.sync += self.pc.eq(Cat(C(0, 2), self.dat_w))
            with m.Case(PcAction.LOAD_REL):
                m.d.sync += self.pc.eq(self.pc + Cat(C(0, 2), self.dat_w))

        return m


RegFileSignature = Signature({
    "adr": Out(5),
    "dat_r": In(32),
    "dat_w": Out(32),
    "we": Out(1)
})


class RegFile(Component):
    signature = RegFileSignature.flip()

    def __init__(self):
        super().__init__()
        self.mem = Memory(width=32, depth=32)

    def elaborate(self, platform):
        m = Module()

        # Re: transparent, let's attempt to save some resources for now.
        m.submodules.rdport = rdport = self.mem.read_port(transparent=False)
        m.submodules.wrport = wrport = self.mem.write_port()

        m.d.comb += [
            rdport.addr.eq(self.adr),
            wrport.addr.eq(self.adr),
            wrport.data.eq(self.dat_w),
        ]

        # Zero register logic- ignore writes/return 0 for reads.
        with m.If(self.adr == 0):
            m.d.comb += self.dat_r.eq(0)
        with m.Else():
            m.d.comb += [
                self.dat_r.eq(rdport.data),
                wrport.en.eq(self.we)
            ]

        return m


DataPathSignature = Signature({
    "reg_adr": Out(5),
    "dat_r": In(32),
    "dat_w": Out(32),
    "we": Out(1),
    "pc": In(32),
    "pc_action": Out(PcAction)
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
            self.dat_r.eq(self.regfile.dat_r),
            self.regfile.adr.eq(self.reg_adr),
            self.regfile.we.eq(self.we),
            self.regfile.dat_w.eq(self.dat_w),
            self.pc_mod.action.eq(self.pc_action),
            self.pc.eq(self.pc_mod.pc),
            self.pc_mod.dat_w.eq(self.dat_w[2:])
        ]

        return m
