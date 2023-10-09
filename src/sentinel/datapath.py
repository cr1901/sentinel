from amaranth import Cat, C, Module, Signal, Memory, Mux
from amaranth.lib.wiring import Component, Signature, In, Out, connect, flipped

from .ucodefields import PcAction, RegSet


PCControlSignature = Signature({
    "action": Out(PcAction)
})

GPControlSignature = Signature({
    "reg_read": Out(1),
    "reg_write": Out(1),
    "reg_set": Out(RegSet)
})

GPSignature = Signature({
    "adr_r": Out(5),
    "adr_w": Out(5),
    "dat_r": In(32),
    "dat_w": Out(32),
    "ctrl": Out(GPControlSignature)
})

PcSignature = Signature({
    "dat_r": In(30),
    "dat_w": Out(30),
    "ctrl": Out(PCControlSignature)
})

DataPathSignature = Signature({
    "gp": Out(GPSignature),
    "pc": Out(PcSignature),
})


class ProgramCounter(Component):
    signature = PcSignature.flip()

    def elaborate(self, platform):
        m = Module()

        with m.Switch(self.ctrl.action):
            with m.Case(PcAction.INC):
                m.d.sync += self.dat_r.eq(self.dat_r + 1)
            with m.Case(PcAction.LOAD_ALU_O):
                m.d.sync += self.dat_r.eq(self.dat_w)

        return m


class RegFile(Component):
    signature = GPSignature.flip()

    def __init__(self):
        super().__init__()
        # 31 GP regs, 32 scratch regs
        self.mem = Memory(width=32, depth=32*2)

    def elaborate(self, platform):
        m = Module()

        adr_r_prev = Signal.like(self.adr_r)

        m.submodules.rdport = rdport = self.mem.read_port()
        m.submodules.wrport = wrport = self.mem.write_port()

        m.d.comb += [
            rdport.en.eq(self.ctrl.reg_read),
            rdport.addr.eq(Cat(self.adr_r, self.ctrl.reg_set)),
            wrport.addr.eq(Cat(self.adr_w, self.ctrl.reg_set)),
            wrport.data.eq(self.dat_w),
        ]

        # We have to simulate a single cycle latency for accessing the zero
        # reg.
        m.d.sync += adr_r_prev.eq(self.adr_r)

        # Zero register logic- ignore writes/return 0 for reads.
        with m.If(adr_r_prev == 0):
            m.d.comb += self.dat_r.eq(0)
        with m.Else():
            m.d.comb += self.dat_r.eq(rdport.data)

        # If you write to address 0, well, congrats, you're not reading
        # that data back!
        m.d.comb += wrport.en.eq(self.ctrl.reg_write)

        return m


class DataPath(Component):
    gp: In(GPSignature)
    pc: In(PcSignature)

    def __init__(self):
        super().__init__()

        self.pc_mod = ProgramCounter()
        self.regfile = RegFile()

    def elaborate(self, platform):
        m = Module()

        m.submodules.pc_mod = self.pc_mod
        m.submodules.regfile = self.regfile

        connect(m, self.regfile, flipped(self.gp))
        connect(m, self.pc_mod, flipped(self.pc))

        return m
