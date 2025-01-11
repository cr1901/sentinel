from amaranth import Cat, Module, Signal
from amaranth.lib.data import View
from amaranth.lib.memory import Memory, MemoryData
from amaranth.lib.wiring import Component, Signature, In, Out, connect, flipped

from .ucodefields import CSRSel, PcAction, CSROp, ExceptCtl, RegRSel, \
    RegWSel, Target

from .csr import MStatus, MTVec, MIP, MIE, MCause


class ProgramCounter(Component):
    """Sentinel RV32I Program Counter.

    Unlike most registers, the :class:`ProgramCounter` (PC) is implemented
    using sequential logic rather than in RAM, because the value needs to be
    available as an :attr:`ALU source <sentinel.alu.BSrcMux.pc>` on any given
    clock cycle. See the bottom half of :class:`CSRFile` documentation for
    more details. Before microcode takes an
    :class:`action <sentinel.ucodefields.PcAction>` on the PC besides
    :attr:`~sentinel.ucodefields.PcAction.HOLD`, the PC points to the
    *currently-executing* instruction. After an action is taken, the PC will
    point to the *next* instruction address to be executed.

    For any given clock cycle, the PC is modified on the next active edge by
    setting :class:`~sentinel.ucodefields.PcAction` to a value besides
    :attr:`~sentinel.ucodefields.PcAction.HOLD`:

    * If :attr:`~sentinel.ucodefields.PcAction.INC` is selected, automatically
      increment by the PC ``4`` bytes on the next active edge. Physically,
      the increment is by ``1`` 32-bit word, because the bottom two bits of
      the PC are unimplemented.
    * If :attr:`~sentinel.ucodefields.PcAction.LOAD_ALU_O` is selected, load
      the PC with the current :attr:`alu output <sentinel.alu.ALU.o>` on the
      next active edge.

    :class:`ProgramCounter` only physically implements the top 30 bits of the
    register, because the least-significant bits are the PC are always ``0``
    for valid RV32I instructions. Loads to the PC from the
    :attr:`alu output <sentinel.alu.ALU.o>` will discard the low two bits.
    With that said, microcode should take care to trigger an exception *as if*
    loading a non-zero value to the low bits of the PC would succeed, when
    appropriate (e.g. :attr:`~sentinel.insn.OpcodeType.JAL` and
    :attr:`~sentinel.insn.OpcodeType.JALR` instructions.)
    """

    #: Signature: Program Counter microcode signals.
    #:
    #: The signature is of the form
    #:
    #: .. code-block::
    #:
    #:    Signature({
    #:        "action": Out(PcAction)
    #:    })
    #:
    #: .. py:attribute:: action
    #:    :type: Out(~sentinel.ucodefields.PcAction)
    #:
    #:    Perform an action on the PC for the current clock cycle.
    ControlSignature = Signature({
        "action": Out(PcAction)
    })

    #: Signature: Program Counter interface that is passed to external modules.
    #:
    #: The signature is of the form
    #:
    #: .. code-block::
    #:
    #:    Signature({
    #:        "dat_r": In(30),
    #:        "dat_w": Out(30),
    #:        "ctrl": Out(ControlSignature)
    #:    })
    #:
    #: where
    #:
    #: .. py:attribute:: dat_r
    #:    :type: In(30)
    #:
    #:    Current value
    #:
    #: .. py:attribute:: imod
    #:    :type: Out(~sentinel.ucodefields.ALUIMod)
    #:
    #:    Modify the inputs :attr:`a` and :attr:`b` before doing ALU
    #:    operation.
    #:
    #: .. py:attribute:: omod
    #:    :type: Out(~sentinel.ucodefields.ALUOMod)
    #:
    #:    Modify the output after doing ALU operation, but before latching
    #:    the ALU output into :attr:`o` (for next cycle).
    #:
    #: .. py:attribute:: zero
    #:    :type: In(1)
    #:
    #:    Set if  the current :attr:`output <o>` (i.e. the result of the ALU
    #:    operation done *last* cycle) is ``0``.
    PublicSignature = Signature({
        "dat_r": In(30),
        "dat_w": Out(30),
        "ctrl": Out(ControlSignature)
    })

    def __init__(self):
        super().__init__(ProgramCounter.PublicSignature.flip())

    def elaborate(self, platform):  # noqa: D102
        m = Module()

        with m.Switch(self.ctrl.action):
            with m.Case(PcAction.INC):
                m.d.sync += self.dat_r.eq(self.dat_r + 1)
            with m.Case(PcAction.LOAD_ALU_O):
                m.d.sync += self.dat_r.eq(self.dat_w)

        return m


class RegFile(Component):
    ControlSignature = Signature({
        "reg_read": Out(1),
        "reg_write": Out(1),
        "allow_zero_wr": Out(1),
    })

    RoutingSignature = Signature({
        "reg_r_sel": Out(RegRSel),
        "reg_w_sel": Out(RegWSel),
    })

    #: Signature: GP register interface that is passed to external modules.
    PublicSignature = Signature({
        "adr_r": Out(5),
        "adr_w": Out(5),
        "dat_r": In(32),
        "dat_w": Out(32),
        "ctrl": Out(ControlSignature)
    })

    # Private interface to control accessing CSR regs stored in GP RAM.
    _PrivateCSRAccessSignature = Signature({
        "adr": Out(5),
        "dat_r": In(32),
        "dat_w": Out(32),
        "op": Out(CSROp)
    })

    pub: In(PublicSignature)

    #: Signature: CSR register interface that is passed to external modules.
    priv: In(_PrivateCSRAccessSignature)

    def __init__(self, *, formal):
        self.formal = formal

        # 32 GP regs, 32 scratch regs
        # 0xdeadbeef is a fake init value to ensure that microcode reset
        # properly initializes r0. If somehow we ever get to ASIC stage,
        # this will be removed.
        self.m_data = MemoryData(shape=32, depth=32 * 2, init=[0xdeadbeef])
        self.mem = Memory(self.m_data)

        # Formal needs to create several more read ports transparent
        # to a single write port. However, FormalTop elaborates before
        # Regfile, so squirrel away a reference.
        self.w_port = self.mem.write_port()

        super().__init__()

    def elaborate(self, platform):  # noqa: D102
        m = Module()
        m.submodules.mem = self.mem

        w_port = self.w_port
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
    """Control and Status Registers register file controller.

    As :data:`hinted <sentinel.ucodefields.RegRead>`
    :data:`at <sentinel.ucodefields.RegWrite>`
    :class:`by <sentinel.ucodefields.RegRSel>`
    :class:`several <sentinel.ucodefields.RegWSel>`
    :class:`microcode <sentinel.ucodefields.CSROp>`
    :class:`fields <sentinel.ucodefields.CSRSel>`, :class:`CSRFile` and
    :class:`RegFile` share a single memory resource defined in
    :class:`RegFile`; GP regs use the bottom half, and CSRs use the top half.
    This :class:`~amaranth:amaranth.lib.wiring.Component` masquerades as a
    register file whose control signals are completely independent from
    :class:`RegFile`, and generates the signals required to access the top
    half of the shared register memory. See :attr:`MSTATUS`, etc.

    :class:`CSRFile` and :class:`RegFile` sharing the same block RAM
    was originally supposed to be an implementation detail. The current
    :doc:`Interface <amaranth:stdlib/wiring>` *attempts* to hide these
    details, but the final design ended up more with a more
    tightly-coupled :class:`CSRFile` and :class:`RegFile` than I originally
    wanted. Right now, only a GP reg or a CSR reg op can happen on a given
    clock cycle, but not both.

    .. todo::

        I can likely relax this restriction without much extra logic (maybe
        even less logic!), but I haven't decided what guarantees I'm willing to
        provide as of 1/10/2025.

    Note that CSR registers are not necessarily stored sequentially in the
    top-half of block RAM. Rather, I store them at addresses that minimize the
    amount of logic to :attr:`map <sentinel.control.MappingROM.csr_encoding>`
    the :attr:`12-bit <sentinel.insn.Insn.CSR.addr>` CSR addresses to 4-bits.

    :class:`~sentinel.csr.MStatus`, :class:`~sentinel.csr.MIP`, and
    :class:`~sentinel.csr.MIE` regs are special in that, similar to the
    :class:`ProgramCounter`, they must be readable *or writable* on any given
    clock cycle for interrupt/exception handling. The block RAM as implemented
    in the :class:`RegFile` cannot accomodate registers whose values are
    always available. Therefore, the above registers are implemented as
    sequential logic storage elements outside of the shared block RAM. Writes
    to these registers go to both the physical logic and the block RAM, while
    reads are always from the dedicated logic for these registers.

    .. note::

        In principle, one can add dedicated read/write ports for each register
        (i.e. fixed address) to the shared block RAM to implement registers
        which can always be written/read in a shared memory. In my opinion,
        dedicated is far simpler, if less elegant, and it *definitely* requires
        more logic and RAM resources to implement!

    If the :attr:`IRQ line <sentinel.top.Top.irq>` is asserted on the same
    cycle that the CPU attempts to clear
    :attr:`MIP.MEIP <sentinel.csr.MIP.meip>`, the IRQ line takes priority to
    avoid lost interrupts.

    .. note::

        As of 1/10/2025, only :attr:`MIP.MEIP <sentinel.csr.MIP.meip>` is
        physically implemented, and it's not clear I will implement the 
        :attr:`MIP.MSIP <sentinel.csr.MIP.msip>`,
        :attr:`MIP.MTIP <sentinel.csr.MIP.mtip>`, and top 16 bits of
        :class:`~sentinel.csr.MIP`. However,
        the same "external value takes priority" will apply to any future
        bits of :class:`~sentinel.csr.MIP` that I implement.

    """

    ControlSignature = Signature({
        "op": Out(CSROp),
        "exception": Out(ExceptCtl)
    })

    RoutingSignature = Signature({
        "csr_sel": Out(CSRSel),
        "target": Out(Target)
    })

    #: Signature: CSR register interface that is passed to external modules.
    PublicSignature = Signature({
        "adr": Out(5),
        "dat_r": In(32),
        "dat_w": Out(32),
        "ctrl": Out(ControlSignature),

        "mstatus_r": In(MStatus),
        "mip_w": Out(MIP),
        "mip_r": In(MIP),
        "mie_r": In(MIE),
        # These 4 are mainly for peeking in simulation.
        # "mscratch_r": In(32),
        # "mepc_r": In(30),
        # "mtvec_r": In(MTVec),
        # "mcause_r": In(MCause)
    })

    pub: In(PublicSignature)
    priv: Out(RegFile._PrivateCSRAccessSignature)

    #: :class:`~sentinel.csr.MStatus` CSR address in the shared register file,
    #: relative to its top-half. Register is implemented as sequential logic,
    #: but a reg file address is required for decoding.
    MSTATUS = 0
    #: :class:`~sentinel.csr.MIE` CSR address in the shared register file,
    #: relative to its top-half. Register is implemented as sequential logic,
    #: but a reg file address is required for decoding.
    MIE = 0x4
    #: ``MTVEC`` CSR address in the shared register file, relative to its
    #: top-half.
    MTVEC = 0x5
    #: ``MSCRATCH`` CSR address in the shared register file, relative to its
    #: top-half.
    MSCRATCH = 0x8
    #: ``MEPC`` CSR address in the shared register file, relative to its
    #: top-half.
    MEPC = 0x9
    #: :class:`~sentinel.csr.MCause` CSR address in the shared register file,
    #: relative to its top-half.
    MCAUSE = 0xA
    #: :class:`~sentinel.csr.MIP` CSR address in the shared register file,
    #: relative to its top-half. Register is implemented as sequential logic,
    #: but a reg file address is required for decoding.
    MIP = 0xC

    def elaborate(self, platform):  # noqa: D102
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


class DataPathSrcMux(Component):
    def __init__(self):
        sig = {
            "insn_fetch": Out(1),
            "reg_r_sel": Out(RegRSel),
            "reg_w_sel": Out(RegWSel),
            "csr_sel": Out(CSRSel),
            "src_a_unreg": Out(5),
            "src_a": Out(5),
            "src_b": Out(5),
            "dst": Out(5),
            "csr_encoding": Out(4),
            "csr_target": Out(4),

            "reg_r_adr": In(5),
            "reg_w_adr": In(5),
            "allow_zero_wr": In(1),
            "csr_adr": In(4)
        }
        super().__init__(Signature(sig).flip())

    def elaborate(self, platform):  # noqa: D102
        m = Module()

        with m.Switch(self.reg_r_sel):
            with m.Case(RegRSel.INSN_RS1):
                with m.If(self.insn_fetch):
                    m.d.comb += self.reg_r_adr.eq(self.src_a_unreg)
                with m.Else():
                    m.d.comb += self.reg_r_adr.eq(self.src_a)
            with m.Case(RegRSel.INSN_RS2):
                m.d.comb += self.reg_r_adr.eq(self.src_b)

        with m.Switch(self.reg_w_sel):
            with m.Case(RegWSel.INSN_RD):
                m.d.comb += self.reg_w_adr.eq(self.dst)
            with m.Case(RegWSel.ZERO):
                m.d.comb += [
                    self.reg_w_adr.eq(0),
                    self.allow_zero_wr.eq(1)
                ]

        # CSR Op/Address control (data conns taken care above)
        with m.Switch(self.csr_sel):
            with m.Case(CSRSel.INSN_CSR):
                m.d.comb += self.csr_adr.eq(self.csr_encoding)
            with m.Case(CSRSel.TRG_CSR):
                m.d.comb += self.csr_adr.eq(self.csr_target)

        return m


class DataPath(Component):
    gp: In(RegFile.PublicSignature)
    csr: In(CSRFile.PublicSignature)
    pc: In(ProgramCounter.PublicSignature)

    def __init__(self, *, formal=False):
        super().__init__()

        self.pc_mod = ProgramCounter()
        self.regfile = RegFile(formal=formal)
        self.csrfile = CSRFile()

    def elaborate(self, platform):  # noqa: D102
        m = Module()

        m.submodules.pc_mod = self.pc_mod
        m.submodules.regfile = self.regfile
        m.submodules.csrfile = self.csrfile

        connect(m, self.regfile.pub, flipped(self.gp))
        connect(m, self.pc_mod, flipped(self.pc))
        connect(m, self.csrfile.pub, flipped(self.csr))
        connect(m, self.regfile.priv, self.csrfile.priv)

        return m
