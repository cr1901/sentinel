from amaranth import Cat, C, Module, Signal, Memory, Mux
from amaranth.lib.wiring import Component, Signature, In, Out, connect, flipped

from .ucodefields import PcAction

from .csr import MStatus, MTVec, MIP, MIE, MCause


PCControlSignature = Signature({
    "action": Out(PcAction)
})

GPControlSignature = Signature({
    "reg_read": Out(1),
    "reg_write": Out(1),
    "allow_zero_wr": Out(1),
    "csr_access": Out(1)
})

GPSignature = Signature({
    "adr_r": Out(5),
    "adr_w": Out(5),
    "dat_r": In(32),
    "dat_w": Out(32),
    "ctrl": Out(GPControlSignature)
})


CSRSignature = Signature({
    # Some CSRs (mepc, mcause, mscratch, mtvec) are stored in the
    # unused portion of the block RAM used for GP registers. However, some
    # CSRs must be implemented as FFs so the rest of the core can use
    # them.
    #
    # Read/write CSRs via block RAM, and shadow the bits that must
    # exposed to the core at all times via FFs.
    "status_r": In(MIP),
    "mip_r": In(MIP),
    "mie_r": In(MIE),
})


PcSignature = Signature({
    "dat_r": In(30),
    "dat_w": Out(30),
    "ctrl": Out(PCControlSignature)
})

DataPathSignature = Signature({
    "gp": Out(GPSignature),
    "csr": Out(CSRSignature),
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
            rdport.addr.eq(Cat(self.adr_r, self.ctrl.csr_access)),
            wrport.addr.eq(Cat(self.adr_w, self.ctrl.csr_access)),
            wrport.data.eq(self.dat_w),
        ]

        m.d.comb += self.dat_r.eq(rdport.data)
        m.d.comb += wrport.en.eq(self.ctrl.reg_write &
                                 (self.adr_w != 0 | self.ctrl.allow_zero_wr))

        return m


class DataPath(Component):
    gp: In(GPSignature)
    csr: In(CSRSignature)
    pc: In(PcSignature)

    def __init__(self, *, formal=False):
        super().__init__()

        self.pc_mod = ProgramCounter()
        self.regfile = RegFile(formal=formal)

    def elaborate(self, platform):
        m = Module()

        # CSR shadows
        mstatus = Signal(MStatus)
        mip = Signal(MIP)
        mie = Signal(MIE)

        m.submodules.pc_mod = self.pc_mod
        m.submodules.regfile = self.regfile

        connect(m, self.regfile, flipped(self.gp))
        connect(m, self.pc_mod, flipped(self.pc))

        m.d.comb += [
            self.csr.status_r.eq(mstatus),
            self.csr.mip_r.eq(mip),
            self.csr.mie_r.eq(mie)
        ]

        with m.If(self.gp.ctrl.csr_access & self.gp.ctrl.reg_write):
            with m.If(self.gp.adr_w == 0):
                m.d.sync += mstatus.eq(self.gp.dat_w)
            with m.If(self.gp.adr_w == 4):
                m.d.sync += mie.eq(self.gp.dat_w)
            with m.If(self.gp.adr_w == 0xC):
                m.d.sync += mip.eq(self.gp.dat_w)

        return m
