from amaranth import Cat, C, Module, Signal, Memory, Mux
from amaranth.lib.data import View
from amaranth.lib.wiring import Component, Signature, In, Out, connect, flipped

from .ucodefields import PcAction, CSROp, ExceptCtl

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


CSRControlSignature = Signature({
    "op": Out(CSROp),
    "exception": Out(ExceptCtl)
})


CSRSignature = Signature({
    "adr_r": Out(5),
    "adr_w": Out(5),
    "dat_r": In(32),
    "dat_w": Out(32),
    "ctrl": Out(CSRControlSignature),

    "mstatus_r": In(MStatus),
    "mip_w": Out(MIP),
    "mip_r": In(MIP),
    "mie_r": In(MIE),
    # These 4 are mainly for peeking in simulation.
    "mscratch_r": In(32),
    "mepc_r": In(30),
    "mtvec_r": In(MTVec),
    "mcause_r": In(MCause)
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
        # "BUG": self.adr_w != 0 prevents mstatus from being shadowed inside
        # block RAM, but this is probably not an actual problem.
        m.d.comb += wrport.en.eq(self.ctrl.reg_write &
                                 (self.adr_w != 0 | self.ctrl.allow_zero_wr))

        return m


class CSRFile(Component):
    MSTATUS = 0
    MIE = 0x4
    MTVEC = 0x5
    MSCRATCH = 0x8
    MEPC = 0x9
    MCAUSE = 0xA
    MIP = 0xC

    signature = CSRSignature.flip()

    def elaborate(self, platform):
        m = Module()

        mstatus = Signal(MStatus, reset={"mpp": 0b11})
        mip = Signal(MIP)
        mie = Signal(MIE)

        read_buf = Signal(32)

        m.d.comb += [
            self.mstatus_r.eq(mstatus),
            self.mip_r.eq(mip),
            self.mie_r.eq(mie),
            self.dat_r.eq(read_buf),
        ]

        with m.If(self.ctrl.op == CSROp.WRITE_CSR):
            with m.If(self.adr_w == self.MSTATUS):
                mstatus_in = View(MStatus, self.dat_w)
                m.d.sync += [
                    mstatus.mie.eq(mstatus_in.mie),
                    mstatus.mpie.eq(mstatus_in.mpie),
                ]
            with m.If(self.adr_w == self.MIE):
                mie_in = View(MIE, self.dat_w)
                m.d.sync += mie.meie.eq(mie_in.meie)
            with m.If(self.adr_w == self.MIP):
                mip_in = View(MIP, self.dat_w)
                m.d.sync += mip.meip.eq(mip_in.meip)

        with m.If(self.ctrl.op == CSROp.READ_CSR):
            with m.If(self.adr_r == self.MSTATUS):
                mstatus_buf = View(MStatus, read_buf)
                m.d.sync += [
                    read_buf.eq(0),
                    mstatus_buf.mie.eq(mstatus.mie),
                    mstatus_buf.mpie.eq(mstatus.mpie),
                    mstatus_buf.mpp.eq(mstatus.mpp),
                ]
            with m.If(self.adr_r == self.MIE):
                mie_buf = View(MIE, read_buf)
                m.d.sync += [
                    read_buf.eq(0),
                    mie_buf.meie.eq(mie.meie)
                ]
            with m.If(self.adr_r == self.MIP):
                mip_buf = View(MIP, read_buf)
                m.d.sync += [
                    read_buf.eq(0),
                    mip_buf.meip.eq(mip.meip)
                ]

        # Make sure we don't lose interrupts.
        with m.If(self.mip_w.meip):
            m.d.sync += mip.meip.eq(1)

        # This stack is probably rather difficult to orchestrate in
        # microcode for little gain.
        with m.If(self.ctrl.exception == ExceptCtl.ENTER_INT):
            m.d.sync += [
                mstatus.mpie.eq(mstatus.mie),
                mstatus.mie.eq(0)
            ]
        with m.Elif(self.ctrl.exception == ExceptCtl.LEAVE_INT):
            m.d.sync += [
                mstatus.mie.eq(mstatus.mpie),
                mstatus.mpie.eq(1)
            ]

        return m


class DataPath(Component):
    gp: In(GPSignature)
    csr: In(CSRSignature)
    pc: In(PcSignature)

    def __init__(self, *, formal=False):
        super().__init__()

        self.pc_mod = ProgramCounter()
        self.regfile = RegFile(formal=formal)
        self.csrfile = CSRFile()

    def elaborate(self, platform):
        m = Module()

        m.submodules.pc_mod = self.pc_mod
        m.submodules.regfile = self.regfile
        m.submodules.csrfile = self.csrfile

        connect(m, self.regfile, flipped(self.gp))
        connect(m, self.pc_mod, flipped(self.pc))
        connect(m, self.csrfile, flipped(self.csr))

        prev_csr_adr = Signal.like(self.csr.adr_r)

        m.d.sync += prev_csr_adr.eq(self.csr.adr_r)

        # Some CSRs are stored in block RAM. Always write to the block RAM,
        # but preempt reads from CSRs which can't be block RAM.
        with m.If(~((prev_csr_adr == CSRFile.MSTATUS) |
                  (prev_csr_adr == CSRFile.MIP) |
                  (prev_csr_adr == CSRFile.MIE))):
            m.d.comb += self.csr.dat_r.eq(self.regfile.dat_r)

        # For MTVEC, only Direct Mode is supported, and field is WARL,
        # so honor that.
        # MEPC is also WARL, and says low 2 bits are always zero for
        # only-IALIGN=32.
        # By contrast, MCAUSE is WLRL ("anything goes if illegal value is
        # written"), and MSCRATCH can hold anything.
        with m.If((self.csr.adr_w == CSRFile.MTVEC) |
                  (self.csr.adr_w == CSRFile.MEPC)):
            m.d.comb += self.regfile.dat_w[0:2].eq(0)

        return m
