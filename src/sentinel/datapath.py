import enum

from amaranth import *

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


class RegFile(Elaboratable):
    def __init__(self):
        self.adr = Signal(5)
        self.dat_r = Signal(32)
        self.dat_w = Signal(32)
        self.we = Signal()
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

    def ports(self):
        return [self.adr, self.dat_r, self.dat_w, self.we]


class DataPath(Elaboratable):
    def __init__(self):
        self.reg_adr = Signal(5)
        self.dat_w = Signal(32)
        self.dat_r = Signal(32)
        self.we = Signal()
        self.pc = Signal(32)
        self.pc_action = Signal(PcAction)

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

    def ports(self):
        return [self.reg_adr, self.dat_w, self.dat_r, self.we, self.pc,
                self.pc_action]
