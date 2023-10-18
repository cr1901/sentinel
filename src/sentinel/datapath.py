from amaranth import Cat, C, Module, Signal, Memory, Mux
from amaranth.lib.wiring import Component, Signature, In, Out, connect, flipped

from .ucodefields import PcAction


PCControlSignature = Signature({
    "action": Out(PcAction)
})

GPControlSignature = Signature({
    "reg_read": Out(1),
    "reg_write": Out(1),
    "allow_zero_wr": Out(1)
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

    def __init__(self, *, formal):
        self.formal = formal

        # 32 GP regs, 32 scratch regs
        # 0xdeadbeef is a fake init value to ensure that microcode reset
        # properly initializes r0. If somehow we ever get to ASIC stage,
        # this will be removed.
        if self.formal:
            self.mem = Memory(width=32, depth=32*2, init=[0xdeadbeef])

        super().__init__()

    def elaborate(self, platform):
        m = Module()

        # 32 GP regs, 32 scratch regs
        # Avoid accidentally instantiating rd ports during pytest simulation
        # with no way to access the underlying memory, unless we're doing
        # formal (in which we have no choice).
        # See: https://github.com/amaranth-lang/amaranth/blob/392ead8d00c9a130b656b3af45c21fa410268301/amaranth/hdl/mem.py#L264-L268)  # noqa: E501
        if not self.formal:
            self.mem = Memory(width=32, depth=32*2, init=[0xdeadbeef])

        m.submodules.rdport = rdport = self.mem.read_port()
        m.submodules.wrport = wrport = self.mem.write_port()

        m.d.comb += [
            rdport.en.eq(self.ctrl.reg_read),
            rdport.addr.eq(self.adr_r),
            wrport.addr.eq(self.adr_w),
            wrport.data.eq(self.dat_w),
        ]

        m.d.comb += self.dat_r.eq(rdport.data)
        m.d.comb += wrport.en.eq(self.ctrl.reg_write &
                                 (self.adr_w != 0 | self.ctrl.allow_zero_wr))

        return m


class DataPath(Component):
    gp: In(GPSignature)
    pc: In(PcSignature)

    def __init__(self, *, formal=False):
        super().__init__()

        self.pc_mod = ProgramCounter()
        self.regfile = RegFile(formal=formal)

    def elaborate(self, platform):
        m = Module()

        m.submodules.pc_mod = self.pc_mod
        m.submodules.regfile = self.regfile

        connect(m, self.regfile, flipped(self.gp))
        connect(m, self.pc_mod, flipped(self.pc))

        return m
