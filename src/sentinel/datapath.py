from amaranth import Cat, Module, Signal
from amaranth.lib.data import View
from amaranth.lib.memory import Memory
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
    "adr": Out(5),
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


# Private interface to control accessing CSR regs stored in GP RAM.
PrivateCSRGPSignature = Signature({
    "adr": Out(5),
    "dat_r": In(32),
    "dat_w": Out(32),
    "op": Out(CSROp)
})


PcSignature = Signature({
    "dat_r": In(30),
    "dat_w": Out(30),
    "ctrl": Out(PCControlSignature)
})


class ProgramCounter(Component):
    def __init__(self):
        super().__init__(PcSignature.flip())

    def elaborate(self, platform):
        m = Module()

        with m.Switch(self.ctrl.action):
            with m.Case(PcAction.INC):
                m.d.sync += self.dat_r.eq(self.dat_r + 1)
            with m.Case(PcAction.LOAD_ALU_O):
                m.d.sync += self.dat_r.eq(self.dat_w)

        return m


class RegFile(Component):
    pub: In(GPSignature)
    priv: In(PrivateCSRGPSignature)

    def __init__(self, *, formal):
        self.formal = formal

        # 32 GP regs, 32 scratch regs
        # 0xdeadbeef is a fake init value to ensure that microcode reset
        # properly initializes r0. If somehow we ever get to ASIC stage,
        # this will be removed.
        self.mem = Memory(shape=32, depth=32*2, init=[0xdeadbeef])

        super().__init__()

    def elaborate(self, platform):
        m = Module()
        m.submodules.mem = self.mem

        w_port = self.mem.write_port()
        r_port = self.mem.read_port(transparent_for=(w_port,))

        m.d.comb += [
            self.priv.dat_r.eq(r_port.data),
            self.pub.dat_r.eq(r_port.data),
            r_port.addr.eq(self.pub.adr_r),
            w_port.addr.eq(self.pub.adr_w),
            w_port.data.eq(self.pub.dat_w),
        ]

        with m.Switch(self.priv.op):
            with m.Case(CSROp.NONE):
                m.d.comb += [
                    r_port.en.eq(self.pub.ctrl.reg_read),
                    w_port.en.eq(self.pub.ctrl.reg_write &
                                 (self.pub.adr_w != 0 |
                                  self.pub.ctrl.allow_zero_wr))
                ]
            with m.Case(CSROp.READ_CSR):
                m.d.comb += [
                    r_port.en.eq(1),
                    r_port.addr.eq(Cat(self.priv.adr, 1)),
                ]
            with m.Case(CSROp.WRITE_CSR):
                m.d.comb += [
                    w_port.addr.eq(Cat(self.priv.adr, 1)),
                    w_port.data.eq(self.priv.dat_w),
                    w_port.en.eq(1)
                ]

        return m


class CSRFile(Component):
    pub: In(CSRSignature)
    priv: Out(PrivateCSRGPSignature)

    MSTATUS = 0
    MIE = 0x4
    MTVEC = 0x5
    MSCRATCH = 0x8
    MEPC = 0x9
    MCAUSE = 0xA
    MIP = 0xC

    def elaborate(self, platform):
        m = Module()

        mstatus = Signal(MStatus, init={"mpp": 0b11})
        mip = Signal(MIP)
        mie = Signal(MIE)

        read_buf = Signal(32)

        m.d.comb += [
            self.pub.mstatus_r.eq(mstatus),
            self.pub.mip_r.eq(mip),
            self.pub.mie_r.eq(mie),
            self.pub.dat_r.eq(read_buf),

            self.priv.adr.eq(self.pub.adr),
            self.priv.dat_w.eq(self.pub.dat_w),
            self.priv.op.eq(self.pub.ctrl.op)
        ]

        with m.If(self.pub.ctrl.op == CSROp.WRITE_CSR):
            with m.If(self.pub.adr == self.MSTATUS):
                mstatus_in = View(MStatus, self.pub.dat_w)
                m.d.sync += [
                    mstatus.mie.eq(mstatus_in.mie),
                    mstatus.mpie.eq(mstatus_in.mpie),
                ]
            with m.If(self.pub.adr == self.MIE):
                mie_in = View(MIE, self.pub.dat_w)
                m.d.sync += mie.meie.eq(mie_in.meie)
            # with m.If(self.pub.adr == self.MIP):
            #     mip_in = View(MIP, self.pub.dat_w)
            #     m.d.sync += mip.meip.eq(mip_in.meip)

        with m.If(self.pub.ctrl.op == CSROp.READ_CSR):
            with m.If(self.pub.adr == self.MSTATUS):
                mstatus_buf = View(MStatus, read_buf)
                m.d.sync += [
                    read_buf.eq(0),
                    mstatus_buf.mie.eq(mstatus.mie),
                    mstatus_buf.mpie.eq(mstatus.mpie),
                    mstatus_buf.mpp.eq(mstatus.mpp),
                ]
            with m.If(self.pub.adr == self.MIE):
                mie_buf = View(MIE, read_buf)
                m.d.sync += [
                    read_buf.eq(0),
                    mie_buf.meie.eq(mie.meie)
                ]
            with m.If(self.pub.adr == self.MIP):
                mip_buf = View(MIP, read_buf)
                m.d.sync += [
                    read_buf.eq(0),
                    mip_buf.meip.eq(mip.meip)
                ]

        prev_csr_adr = Signal.like(self.pub.adr)
        m.d.sync += prev_csr_adr.eq(self.pub.adr)

        # Some CSRs are stored in block RAM. Always write to the block RAM,
        # but preempt reads from CSRs which can't be block RAM.
        with m.If(~((prev_csr_adr == CSRFile.MSTATUS) |
                  (prev_csr_adr == CSRFile.MIP) |
                  (prev_csr_adr == CSRFile.MIE))):
            m.d.comb += self.pub.dat_r.eq(self.priv.dat_r)

        # For MTVEC, only Direct Mode is supported, and field is WARL,
        # so honor that.
        # MEPC is also WARL, and says low 2 bits are always zero for
        # only-IALIGN=32.
        # By contrast, MCAUSE is WLRL ("anything goes if illegal value is
        # written"), and MSCRATCH can hold anything.
        with m.If((self.pub.adr == CSRFile.MTVEC) |
                  (self.pub.adr == CSRFile.MEPC)):
            m.d.comb += self.priv.dat_w[0:2].eq(0)

        # Make sure we don't lose interrupts.
        # with m.If(self.pub.mip_w.meip):
        m.d.comb += mip.meip.eq(self.pub.mip_w.meip)

        # This stack is probably rather difficult to orchestrate in
        # microcode for little gain.
        with m.If(self.pub.ctrl.exception == ExceptCtl.ENTER_INT):
            m.d.sync += [
                mstatus.mpie.eq(mstatus.mie),
                mstatus.mie.eq(0)
            ]
        with m.Elif(self.pub.ctrl.exception == ExceptCtl.LEAVE_INT):
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

        connect(m, self.regfile.pub, flipped(self.gp))
        connect(m, self.pc_mod, flipped(self.pc))
        connect(m, self.csrfile.pub, flipped(self.csr))
        connect(m, self.regfile.priv, self.csrfile.priv)

        return m
