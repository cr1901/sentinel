"""Sentinel control unit implementation and microcode ROM wrapper."""

from amaranth import Signal, Elaboratable, Module, Cat, C, unsigned
from amaranth.lib.data import StructLayout
from amaranth.lib.wiring import Component, Signature, In, Out

from .alu import ALU
from .ucoderom import UCodeROM
from .datapath import GPControlSignature, PCControlSignature, \
    CSRControlSignature

from .insn import Insn, OpcodeType
from .ucodefields import JmpType, CondTest, MemReq, MemSel, WriteMem, \
    InsnFetch, MemExtend, LatchData, LatchAdr, ExceptCtl, Target, ASrc, \
    BSrc, LatchA, LatchB, RegRSel, RegWSel, CSRSel

from typing import TextIO, Optional


# The MappingROM itself knows how to handle CSRs. Logically it's part of the
# control unit. Physically, it's part of the instruction decoder for space
# reasons.
class MappingROM(Component):
    def __init__(self):
        sig = {
            "start": Out(1),
            "insn": Out(32),
            # Cannot use _DataLayout due to circular imports.
            "csr_attr": Out(StructLayout({
                "ill": unsigned(1),
                "ro0": unsigned(1)
            })),
            "requested_op": In(8),
            "csr_encoding": In(4)
        }

        super().__init__(Signature(sig).flip())

    def elaborate(self, platform):  # noqa: D102
        m = Module()

        insn = Insn(self.insn)

        src_a = Signal.like(insn.rs1)
        dst = Signal.like(insn.rd)
        forward_csr = Signal()
        csr_op = Signal.like(insn.funct3)
        csr_encode = Signal(4)

        m.d.sync += [
            forward_csr.eq(0),
            csr_op.eq(insn.funct3),
        ]

        with m.If(self.start):
            m.d.sync += [
                # For now, unconditionally propogate these and rely on
                # microcode program to ignore when necessary.
                src_a.eq(insn.rs1),
                dst.eq(insn.rd),
            ]

            # TODO: Might be worth hoisting comb statements out of m.If?
            with m.Switch(insn.opcode):
                with m.Case(OpcodeType.OP_IMM):
                    with m.If((insn.funct3 == 1) | (insn.funct3 == 5)):
                        op_map = Cat(insn.funct3, insn.funct7[-2],
                                     C(0x40 >> 4))
                        m.d.sync += self.requested_op.eq(op_map)
                    with m.Else():
                        op_map = Cat(insn.funct3, 0, C(0x40 >> 4))
                        m.d.sync += self.requested_op.eq(op_map)
                with m.Case(OpcodeType.LUI):
                    m.d.sync += self.requested_op.eq(0xD0)
                with m.Case(OpcodeType.AUIPC):
                    m.d.sync += self.requested_op.eq(0x50)
                with m.Case(OpcodeType.OP):
                    op_map = Cat(insn.funct3, insn.funct7[-2], C(0xC0 >> 4))
                    m.d.sync += self.requested_op.eq(op_map)
                with m.Case(OpcodeType.JAL):
                    m.d.sync += self.requested_op.eq(0xB0)
                with m.Case(OpcodeType.JALR):
                    m.d.sync += self.requested_op.eq(0x98)
                with m.Case(OpcodeType.BRANCH):
                    m.d.sync += self.requested_op.eq(Cat(insn.funct3,
                                                         C(0x88 >> 3)))
                with m.Case(OpcodeType.LOAD):
                    op_map = Cat(insn.funct3, C(0x08 >> 3))
                    m.d.sync += self.requested_op.eq(op_map)
                with m.Case(OpcodeType.STORE):
                    op_map = Cat(insn.funct3, C(0x10))
                    m.d.sync += self.requested_op.eq(op_map)
                with m.Case(OpcodeType.MISC_MEM):
                    m.d.sync += self.requested_op.eq(0x30)
                with m.Case(OpcodeType.SYSTEM):
                    with m.If(insn.raw == Insn.MRET):
                        m.d.sync += self.requested_op.eq(248)
                    with m.Elif(insn.raw == Insn.WFI):
                        m.d.sync += self.requested_op.eq(0x30)
                    with m.Elif((insn.funct3 != 0) & (insn.funct3 != 4)):
                        # csr
                        csr_encode = Cat(insn.funct12[0:3], insn.funct12[6])
                        m.d.sync += [
                            forward_csr.eq(1),
                            self.csr_encoding.eq(csr_encode),
                            self.requested_op.eq(0x24)
                        ]

        # Second decode cycle if this is a CSR access.
        with m.If(forward_csr):
            # It's illegal, sequencer will never send requested_op to ucode
            # ROM. So we can do nothing here...
            with m.If(self.csr_attr.ill):
                pass
            # Read-only Zero CSRs. Includes CSRs that are in actually
            # read-only space (top 2 bits set), all of which are 0
            # for this core.
            with m.Elif(self.csr_attr.ro0):
                # csrro0
                m.d.sync += self.requested_op.eq(0x25)
            with m.Else():
                # Jump to microcode routines for actual, implemented
                # CSR registers.
                with m.If((csr_op == Insn.CSR.RW) & (dst == 0)):
                    m.d.sync += self.requested_op.eq(0x26)  # csrw
                with m.Elif((csr_op == Insn.CSR.RW) & (dst != 0)):
                    m.d.sync += self.requested_op.eq(0x27)  # csrrw
                with m.Elif((csr_op == Insn.CSR.RS) & (src_a == 0)):
                    m.d.sync += self.requested_op.eq(0x28)  # csrr
                with m.Elif((csr_op == Insn.CSR.RS) & (src_a != 0)):
                    m.d.sync += self.requested_op.eq(0x29)  # csrrs
                with m.Elif((csr_op == Insn.CSR.RC) & (src_a == 0)):
                    m.d.sync += self.requested_op.eq(0x28)  # csrrc, no write
                with m.Elif((csr_op == Insn.CSR.RC) & (src_a != 0)):
                    m.d.sync += self.requested_op.eq(0x2a)  # csrrc
                with m.Elif((csr_op == Insn.CSR.RWI) & (dst == 0)):
                    m.d.sync += self.requested_op.eq(0x2b)  # csrwi
                with m.Elif((csr_op == Insn.CSR.RWI) & (dst != 0)):
                    m.d.sync += self.requested_op.eq(0x2c)  # csrrwi
                with m.Elif((csr_op == Insn.CSR.RSI) & (src_a == 0)):
                    m.d.sync += self.requested_op.eq(0x28)  # csrrsi, no write
                with m.Elif((csr_op == Insn.CSR.RSI) & (src_a != 0)):
                    m.d.sync += self.requested_op.eq(0x2d)  # csrrsi
                with m.Elif((csr_op == Insn.CSR.RCI) & (src_a == 0)):
                    m.d.sync += self.requested_op.eq(0x28)  # csrrci, no write
                with m.Elif((csr_op == Insn.CSR.RCI) & (src_a != 0)):
                    m.d.sync += self.requested_op.eq(0x2e)  # csrrci
                with m.Else():
                    # TODO: cover via rvformal.
                    # This might be reachable, but not while
                    # requested_op has a meaningful value in it.
                    # Make sure this is actually the case.
                    pass

        return m


# Control at present doesn't have a parametric interface. However, I anticipate
# that will change in the near-future, so preemptively stuff Attributes into
# class docstring.
class Control(Component):
    """Sentinel Control Unit.

    The Sentinel Control Unit consists of three parts:

    * :class:`Sequencer`
    * :class:`~sentinel.ucoderom.UCodeROM`
    * Multiplexer for :class:`condition test <sentinel.ucodefields.CondTest>`
      sources.

    In principle :class:`MappingROM` is also part of the Control Unit.
    However, I found it to be a space win to tightly couple it to the
    :class:`~sentinel.decode.Decoder`.

    This :class:`Component <amaranth.lib.wiring.Component>` is pure
    combinational logic. Beyond connecting the above parts together,
    :class:`Control` propagates microcode ROM
    :mod:`control signals <sentinel.ucodefields>` to the rest of the core. In
    turn, it snoops control and data signals from *other* parts of the core
    to drive the microcode program forward.

    .. todo::

        Interface attributes are incomplete.

    Parameters
    ----------
    ucode: Optional[TextIO] = None
        Microcode file to assemble and load. By default, use
        :func:`~sentinel.ucoderom.UCodeROM.main_microcode_file`.

    Attributes
    ----------
    ucoderom: UCodeROM

    sequencer: Sequencer
    """

    def __init__(self, ucode: Optional[TextIO] = None):
        self.ucoderom = UCodeROM(main_file=ucode)
        # Enums from microcode ROM.
        self.sequencer = Sequencer(self.ucoderom)

        # Control inputs
        self.vec_adr = Signal.like(self.ucoderom.fields.target)

        super().__init__({
            "alu": Out(ALU.ControlSignature),
            "decode": In(Signature({
                "opcode": Out(OpcodeType),
                "requested_op": Out(8),
            })),
            "gp": Out(GPControlSignature),
            "pc": Out(PCControlSignature),
            "csr": Out(CSRControlSignature),
            "mem": Out(Signature({
                "req": Out(MemReq),
                "sel": Out(MemSel),
                "valid": In(1),
                "write": Out(WriteMem),
                "insn_fetch": Out(InsnFetch),
                "extend": Out(MemExtend),
                "latch_data": Out(LatchData),
                "latch_adr": Out(LatchAdr)
            })),
            "route": Out(Signature({
                "a_src": Out(ASrc),
                "b_src": Out(BSrc),
                "latch_a": Out(LatchA),
                "latch_b": Out(LatchB),
                "reg_r_sel": Out(RegRSel),
                "reg_w_sel": Out(RegWSel),
                "csr_sel": Out(CSRSel)
            })),
            "target": Out(Target),
            "exception": In(1),
            "except_ctl": Out(ExceptCtl)
        })

    def elaborate(self, platform):  # noqa: D102
        m = Module()

        m.submodules.ucoderom = self.ucoderom
        m.submodules.sequencer = self.sequencer

        raw_test = Signal()  # Output of test mux.
        test = Signal()  # Possibly-inverted test result.

        # Internally-used microcode signals
        jmp_type = Signal.like(self.ucoderom.fields.jmp_type)
        cond_test = Signal.like(self.ucoderom.fields.cond_test)
        invert_test = Signal.like(self.ucoderom.fields.invert_test)

        # Propogate ucode control signals
        m.d.comb += [
            self.target.eq(self.ucoderom.fields.target),
            jmp_type.eq(self.ucoderom.fields.jmp_type),
            cond_test.eq(self.ucoderom.fields.cond_test),
            invert_test.eq(self.ucoderom.fields.invert_test),
            self.pc.action.eq(self.ucoderom.fields.pc_action),
            self.gp.reg_read.eq(self.ucoderom.fields.reg_read),
            self.gp.reg_write.eq(self.ucoderom.fields.reg_write),
            self.csr.op.eq(self.ucoderom.fields.csr_op),
            self.route.reg_r_sel.eq(self.ucoderom.fields.reg_r_sel),
            self.route.reg_w_sel.eq(self.ucoderom.fields.reg_w_sel),
            self.route.csr_sel.eq(self.ucoderom.fields.csr_sel),
            self.route.a_src.eq(self.ucoderom.fields.a_src),
            self.route.b_src.eq(self.ucoderom.fields.b_src),
            self.route.latch_a.eq(self.ucoderom.fields.latch_a),
            self.route.latch_b.eq(self.ucoderom.fields.latch_b),
            self.alu.op.eq(self.ucoderom.fields.alu_op),
            self.alu.imod.eq(self.ucoderom.fields.alu_i_mod),
            self.alu.omod.eq(self.ucoderom.fields.alu_o_mod),
            self.mem.req.eq(self.ucoderom.fields.mem_req),
            self.mem.sel.eq(self.ucoderom.fields.mem_sel),
            self.mem.latch_adr.eq(self.ucoderom.fields.latch_adr),
            self.mem.latch_data.eq(self.ucoderom.fields.latch_data),
            self.mem.write.eq(self.ucoderom.fields.write_mem),
            self.mem.insn_fetch.eq(self.ucoderom.fields.insn_fetch),
            self.mem.extend.eq(self.ucoderom.fields.mem_extend),
            self.except_ctl.eq(self.ucoderom.fields.except_ctl)
        ]

        # Connect ucode ROM to sequencer
        m.d.comb += [
            self.ucoderom.addr.eq(self.sequencer.adr),
            self.sequencer.target.eq(self.target),
            self.sequencer.jmp_type.eq(jmp_type)
        ]

        # Connect sequencer to Control.
        m.d.comb += [
            self.sequencer.test.eq(test),
            self.sequencer.opcode_adr.eq(self.decode.requested_op),
            self.sequencer.vec_adr.eq(self.vec_adr),
        ]

        # Test mux
        with m.Switch(cond_test):
            with m.Case(CondTest.EXCEPTION):
                m.d.comb += raw_test.eq(self.exception)
            with m.Case(CondTest.CMP_ALU_O_ZERO):
                m.d.comb += raw_test.eq(self.alu.zero)
            with m.Case(CondTest.MEM_VALID):
                m.d.comb += raw_test.eq(self.mem.valid)
            with m.Case(CondTest.TRUE):
                m.d.comb += raw_test.eq(1)

        with m.If(invert_test):
            m.d.comb += test.eq(~raw_test)
        with m.Else():
            m.d.comb += test.eq(raw_test)

        return m


# FIXME: Why is the an Elaboratable again?
class Sequencer(Elaboratable):
    """Microprogram address generation. See :term:`sequencer`.

    :class:`Sequencer` generates the address of the *next*
    :term:`microinstruction` to execute using the semantics explained in
    :class:`~sentinel.ucodefields.JmpType`. It also implicitly contains the
    :term:`microprogram counter (upc) <microprogram counter>`, accessed via
    :attr:`~sentinel.ucodefields.JmpType.CONT`. On reset, the upc is reset to
    ``2``, and *stays* at ``2`` until reset is released.

    .. warning::

        Because the upc has "points to *next-cycle* instruction" semantics, the
        microinstruction driving the CPU is **undefined** for a single clock
        cycle after reset is explicitly asserted (i.e. non-power-on-reset).
        This may result in undesirable side effects that require extra guard
        logic or microcode to quash. Bugs I've found include:

        * ``WB_CYC`` and ``WB_STB`` do not deassert on the first cycle after
          reset (fixed by guard logic).
        * Initial instruction fetch uses address ``4`` instead of ``0``
          (fixed in microcode).

        I have basic tests for flushing out these types of bugs, and to the
        best of my knowledge (1/3/2025), all of the reset bugs I encountered
        have been fixed. But I need to create a verification step to
        characterize all possible reset behavior to flush out other possible
        issues. *For now, if you find a reset bug, please let me know and try
        to reproduce*, as this is the likely cause.

        AFAICT, none of the above applies for
        power-on-reset; your target toolchain should provide
        `logic <https://github.com/amaranth-lang/amaranth/blob/f9da3c0d166dd2be189945dca5a94e781e74afeb/amaranth/hdl/mem.py#L153>`_
        so that the microinstruction at ``2`` is driving the CPU on
        power-on-reset. And even then, a power-on-reset circuit should be
        holding the design in reset for more than 1 clock cycle, which prevents
        at least *some* (all?) of the bad side-effects :).

    Parameters
    ----------
    ucoderom: :class:`~sentinel.ucoderom.UCodeROM`
        Microcode program ROM to which to connect the :class:`Sequencer`.

    Attributes
    ----------
    target : Signal(:data:`~sentinel.ucodefields.Target`)
        Target :term:`microinstruction` address microcode field, used by the
        :term:`sequencer` for :attr:`~sentinel.ucodefields.JmpType.DIRECT` and
        :attr:`~sentinel.ucodefields.JmpType.DIRECT_ZERO`.
    jmp_type : Signal(:class:`~sentinel.ucodefields.JmpType`)
        Select the next :term:`microinstruction` address to place in
        :attr:`adr`. Next addresses are calculated in parallel for all
        possible :attr:`JmpTypes <~sentinel.ucodefields.JmpType>`, and are
        selected/muxed here.
    adr : Signal(:data:`~sentinel.ucodefields.Target`)
        Address of the next :term:`microinstruction` to execute, subject to
        the input :ref:`Signals <amaranth:lang-signals>`.
    opcode_adr : Signal(:data:`~sentinel.ucodefields.Target`)
        Address calculated from :class:`MappingROM`, used for
        :attr:`~sentinel.ucodefields.JmpType.MAP`. It typically contains a
        microprogram address for handling the currently-executing
        :term:`macroinstruction`.
    vec_adr : Signal(:data:`~sentinel.ucodefields.Target`)
        Currently unused signal for possible future expansion.
    test: Signal(1)
        If set, the condition test described by the current value of
        :class:`~sentinel.ucodefields.CondTest` succeeded this cycle. This in
        turn affects :attr:`adr`, depending on :attr:`jmp_type`.
    """  # noqa: RUF100, E501

    def __init__(self, ucoderom):
        # Get info required from ucoderom.
        self.target = Signal.like(ucoderom.fields.target)
        self.jmp_type = Signal.like(ucoderom.fields.jmp_type)

        # upc == 2 is reset; 0 is "do insn fetch". 0 is so important, that
        # it's an implied target in DIRECT_ZERO.
        self.adr = Signal.like(ucoderom.fields.target, init=2)
        self.opcode_adr = Signal.like(self.adr)
        self.vec_adr = Signal.like(self.adr)
        self.next_adr = Signal.like(self.adr)
        self.ice40_rst_guard = Signal(init=1)

        # If test succeeds, branch in target/vec_adr is taken, otherwise
        # next_adr.
        self.test = Signal()

    def elaborate(self, platform):  # noqa: D102
        m = Module()

        m.d.sync += self.next_adr.eq(self.adr + 1)
        m.d.sync += self.ice40_rst_guard.eq(0)

        with m.Switch(self.jmp_type):
            # Also handles JumpType.NOP
            with m.Case(JmpType.CONT):
                m.d.comb += self.adr.eq(self.next_adr)
            with m.Case(JmpType.MAP):
                with m.If(self.test):
                    m.d.comb += self.adr.eq(self.target)
                with m.Else():
                    m.d.comb += self.adr.eq(self.opcode_adr)
            with m.Case(JmpType.DIRECT):
                with m.If(self.test):
                    m.d.comb += self.adr.eq(self.target)
                with m.Else():
                    m.d.comb += self.adr.eq(self.next_adr)
            with m.Case(JmpType.DIRECT_ZERO):
                with m.If(self.test):
                    m.d.comb += self.adr.eq(self.target)
                with m.Else():
                    m.d.comb += self.adr.eq(0)

        # self.adr is combinational, and indirectly gets its value from the
        # read outputs (latches) of the block RAM holding the ucode
        # (particularly the JumpType and CondTest fields); the read latches are
        # reset_less. We don't want self.adr to take on random transient values
        # in read latches after POR because we need address 2 to be the first
        # ucode ROM location read after sync reset ends. Feeding self.adr with
        # the reset value of self.next_adr works fine.
        #
        # In principle these lines are not needed, but iCE40 has a BRAM bug
        # that prevents the intended logic self.adr logic from firing without
        # these lines. Read below for more info.
        #
        # Detailed background:
        #
        # This line is not needed in principle because Amaranth/yosys forces
        # the read value of a block RAM to 0 for the first cycle after POR ends
        # ("plugging in the board", "resetting the board", or otherwise):
        # https://github.com/amaranth-lang/amaranth/blob/f9da3c0d166dd2be189945dca5a94e781e74afeb/amaranth/hdl/mem.py#L153  # noqa: E501
        #
        # 0 in the relevant ucode BRAM field corresponds to JmpType.CONT,
        # which is equivalent to the below code. 0 in the other ucode fields
        # are mostly no-ops as well, and don't affect anything we care about.
        # So on subsequent clock cycles until reset of self.next_adr ends, the
        # block RAM latches will hold the value of ucode address 2, which
        # "conveniently" also sets the relevant ucode field to JumpType.CONT.
        #
        # However, on iCE40 there's a BRAM bug where BRAM doesn't initialize
        # properly until ~3us after internal POR. This will be many clock
        # cycles after POR is released by iCE40. By default, Amaranth will
        # generate a POR circuit that accomodates this behavior by holding the
        # sync domain in rst for 15 us after POR ends. But self.adr feeds
        # back into the ucode BRAM, which in turns feeds the _reset-less_ read
        # latches, without any intermediate storage elements. So Amaranth's POR
        # circuit does not apply to self.adr in all scenarios without some
        # guard logic, as below.
        #
        # Without these lines, observed behavior on iCE40 is interesting; for
        # the first clock cycle after POR ends, self.adr is 2. This is the
        # aforementioned Amaranth/yosys behavior correctly firing.
        # However on subsequent clock cycles until ~3us have passed, the ucode
        # outputs will take on _the values the read-latches had just before an
        # internal POR was triggered_ by e.g. "iceprog -t". Without this line,
        # if the jump_type ucode field from the read latches isn't
        # JmpType.CONT, self.adr will read garbage.
        #
        # Once the iCE40 BRAM initializes properly after ~3us, nothing except
        # self.next_adr holds self.adr at its current position for the
        # remaining ~12us that Amaranth holds the design in reset.
        # Thus, the ucode program will start executing until either:
        #
        # * The ucode program gets stuck waiting for insn memory at address 0.
        # * The jmp_type ucode field of the current insn is JumpType.CONT,
        #   which will stall the program at address 2- provided by Amaranth's
        #   reset value for self.next_adr- until sync reset is released.
        #
        # If the ucode makes it back to address 2, running the ucode program
        # during reset probably has no ill effects. Unfortunately, if we
        # end at address 0, we then skip the initialization ucode that ensures
        # x0 is actually 0, essentially breaking the core.
        #
        # This behavior is not consistent, but happens very often after resets
        # triggered by e.g. "iceprog -t", and not so much for resets triggered
        # by "plugging a board in".
        #
        # Speculation follows...
        #
        # Perhaps "rest values" of read latches are 0, but hysteresis causes
        # initial values to change after POR from "plugging in the board"? The
        # LA traces I've taken makes me believe that the BRAM bug is more
        # correctly described as outputting stale values from the read latches
        # for up to 3us after POR, rather than outputting 0 during those 3us,
        # as the bug is usually described.
        with m.If(self.ice40_rst_guard):
            m.d.comb += self.adr.eq(self.next_adr)

        return m
