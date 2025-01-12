"""Microcode field classes for main microcode file.

This file is used to avoid circular imports and to serve as a single
source of truth for the meaning of microcode fields. Each variable defined in
this modules corresponds to an `m5meta <https://github.com/brouhaha/m5meta>`_
field in the default microcode file.

Microcode field order is determined by the microcode assembly file; order of
fields in this module do not matter. However, for consistency, we try to match
the ``microcode.asm`` order.

The default/main microcode file is stored with the Sentinel package in the same
directory as this file, at ``microcode.asm``.
"""

# TODO: For convenience, the microcode file is reproduced
# :ref:`here <microcode-asm>` in full.

from amaranth import unsigned
from amaranth.lib import enum


#: Jump target supplied by the currently-executing :term:`microinstruction`.
#: Occassionally used to supply a constant value, like in :class:`CSRSel`.
Target = unsigned(8)


class JmpType(enum.Enum, shape=2):
    """Type of jump to perform for this :term:`microinstruction`."""

    #: int: On the next cycle go to the next sequential
    #: :term:`microinstruction` (:term:`upc <Microprogram Counter>` + 1).
    CONT = 0
    #: int: An alias for :attr:`CONT` meant to indicate that the target field
    #: is being used for :attr:`something else <CSRSel.TRG_CSR>`.
    NOP = 0
    #: int: Jump to the address supplied by the
    #: :class:`~sentinel.control.MappingROM` if :class:`condition <CondTest>`
    #: is met. Otherwise, unconditionally jump to the address supplied by
    #: :data:`Target`. This is generally used to jump to code specific to each
    #: :term:`macroinstruction`, or start exception handling on an invalid
    #: instruction.
    MAP = 1
    #: int: If :class:`condition <CondTest>` is met, jump to the address
    #: supplied by :data:`Target`. Otherwise, go to the next sequential
    #: :term:`microinstruction`, as in :attr:`CONT`.
    DIRECT = 2
    #: int: If :class:`condition <CondTest>` is met, jump to the address
    #: supplied by :data:`Target`. Otherwise, go to the
    #: :term:`upc <Microprogram Counter>` address ``0``.
    DIRECT_ZERO = 3


class OpType(enum.Enum):
    """:attr:`ALU operation <sentinel.alu.ALU.op>` to perform this cycle.

    On the next active edge, :attr:`ALU output (O) <sentinel.alu.ALU.o>` will
    be equal to result of the operation performed using its
    :attr:`A <sentinel.alu.ALU.a>` and :attr:`B <sentinel.alu.ALU.b>` inputs.
    """

    #: int: ``O <= A + B``
    ADD = 0
    #: int: ``O <= A - B``
    SUB = 1
    #: int: ``O <= A & B``
    AND = 2
    #: int: ``O <= A | B``
    OR = 3
    #: int: ``O <= A ^ B``
    XOR = 4
    #: int: ``O <= A << 1``
    SLL = 5
    #: int: ``O <= unsigned(A) >> 1``
    SRL = 6
    #: int: ``O <= signed(A) >> 1``
    SRA = 7
    #: int: ``O <= bool(unsigned(A) < unsigned(B))``
    CMP_LTU = 8


class CondTest(enum.Enum):
    """Conditional test to pass through to the :class:`~sentinel.control.Sequencer`."""  # noqa: E501

    #: int: Set if an exception occurred this clock cycle.
    #:
    #: When :data:`InvertTest` is asserted, set if an exception *did not* occur
    #: this clock cycle.
    EXCEPTION = 0

    #: int: Set if the :class:`~sentinel.alu.ALU` output is ``0`` this clock
    #: cycle.
    #:
    #: When :data:`InvertTest` is asserted, set if if the
    #: :class:`~sentinel.alu.ALU` output is *nonzero* this clock cycle.
    CMP_ALU_O_ZERO = 1

    #: int: Set if the contents of the memory bus are valid this cycle.
    #:
    #: When :data:`InvertTest` is asserted, set if if the contents of the
    #: memory bus are *not* valid.
    #:
    #: The memory bus is valid when ``sentinel.top.Top.bus.ack`` in
    #: :class:`~sentinel.top.Top` is asserted.
    MEM_VALID = 2

    #: int: Unconditionally set/asserted. When :data:`InvertTest` is asserted,
    #: the test unconditionally *fails*.
    TRUE = 3


#: If set, invert the result of the conditional test on the output of
#: :class:`CondTest` this clock cycle.
InvertTest = unsigned(1)


class PcAction(enum.Enum):
    """Perform an action on the RISC-V :class:`Program Counter <sentinel.datapath.ProgramCounter>` this cycle."""  # noqa: E501

    #: int: Do not change the Program Counter; hold the current value.
    HOLD = 0
    #: int: Increment the Program Counter by ``4`` bytes (``1`` 32-bit word).
    INC = 1
    #: int: Set the Program Counter to the value currently on the
    #: :attr:`ALU output <sentinel.alu.ALU.o>`.
    LOAD_ALU_O = 2


#: If set, latch the :attr:`selected <sentinel.alu.ASrcMux.sel>`
#: :class:`~sentinel.alu.ASrcMux` input to its output.
LatchA = unsigned(1)

#: If set, latch the :attr:`selected <sentinel.alu.BSrcMux.sel>`
#: :class:`~sentinel.alu.BSrcMux` input to its output.
LatchB = unsigned(1)


class ASrc(enum.Enum):
    """Select the source for the :attr:`ALU A input <sentinel.alu.ALU.a>`.

    The ALU A input is provided by the latched output of
    :class:`~sentinel.alu.ASrcMux`; this field is qualified by
    :data:`~sentinel.ucodefields.LatchA`.
    """

    #: int: Select general purpose register that was read from the reg file
    #: last cycle.
    GP = 0
    #: int: Select the decoded Immediate from the current instruction.
    IMM = 1
    #: int: Feed back the :attr:`ALU output <sentinel.alu.ALU.o>` into the
    #: input. Intended to facilitate chaining ALU ops together.
    ALU_O = 2
    #: int: Supply the literal constant ``C(0, 32)``.
    ZERO = 3
    #: int: Supply the literal constant ``C(4, 32)``.
    FOUR = 4
    #: int: Supply the literal constant ``C(-1, 32)``, i.e. "all ones".
    NEG_ONE = 5
    #: int: Supply the literal constant ``C(31, 32)``.
    THIRTY_ONE = 6


class BSrc(enum.Enum):
    """Select the source for the :attr:`ALU B input <sentinel.alu.ALU.b>`.

    The ALU B input is provided by the latched output of
    :class:`~sentinel.alu.BSrcMux`; this field is qualified by
    :data:`~sentinel.ucodefields.LatchB`.
    """

    #: int: Select General Purpose register that was read from the
    #: :class:`reg file <sentinel.datapath.RegFile>` last cycle.
    GP = 0
    #: int: Select the
    #: :class:`Program Counter <sentinel.datapath.ProgramCounter>` register.
    PC = 1
    #: int: Select the decoded Immediate from the current instruction.
    IMM = 2
    #: int: Supply the literal constant ``C(1, 32)``.
    ONE = 3
    #: int: Select the *unregistered* Wishbone read data bus value. The read
    #: data bus is only valid when indicated by
    #: :attr:`~CondTest.MEM_VALID`.
    DAT_R = 4
    #: int: Some RISC-V CSR instructions have an Immediate field that differs
    #: from :attr:`~BSrc.IMM`; select the CSR Immediate
    #: field instead.
    CSR_IMM = 5
    #: int: Select CSR register that was read from the
    #: :class:`CSR reg file <sentinel.datapath.CSRFile>` last cycle.
    CSR = 6
    #: int: Select the current value of the
    #: :attr:`MCAUSE latch <sentinel.exception.ExceptionRouter.out>`.
    MCAUSE_LATCH = 7


class ALUIMod(enum.Enum):
    """Modify ALU inputs before performing :class:`ALU op <OpType>`.

    This field modifies the ALU inputs :attr:`A <sentinel.alu.ALU.a>` and
    :attr:`B <sentinel.alu.ALU.b>` *just before* they are sent to the to ALU.
    Set this field to value besides :attr:`NONE` on the same cycle
    as when an :class:`ALU op <OpType>` you wish to modify is taking place. The
    :attr:`ALU output (O) <sentinel.alu.ALU.o>`, modified or otherwise, will be
    available on the next active edge.

    Modifying the inputs are useful to implement additional ALU operations,
    such as signed compare using an unsigned comparator.
    """

    #: Pass through ``A`` and ``B`` to the ALU unchanged.
    NONE = 0
    #: Invert the most-significant bit of ``A`` and ``B`` before performing
    #: ``OP``.
    INV_MSB_A_B = 1


class ALUOMod(enum.Enum):
    """Modify the result of the currently-executing :class:`ALU op <OpType>`.

    This field modifies the raw ALU result *just before* storing the result in
    :attr:`O <sentinel.alu.ALU.o>` on the next active edge. In other words,
    this field *must* be set on the same cycle as when the
    :class:`ALU op <OpType>` you wish to modify is taking place.

    Modifying the output is useful for synthesizing additional ALU operations,
    such as "compare-greater-than-or-equal" or
    :attr:`~sentinel.insn.OpcodeType.JALR` targets.
    """

    #: int: Do not modify ``O``.
    NONE = 0
    #: int: Invert the least-significant bit of ``O``.
    INV_LSB_O = 1
    #: int: Clear the least-significant bit of ``O``.
    CLEAR_LSB_O = 2


#: If set, read from the :class:`register file <sentinel.datapath.RegFile>`
#: this cycle. The results will be valid and available on the read port on the
#: next active edge. The read value will *stay* valid on the read port until
#: the subsequent active edge where :data:`RegRead` is asserted *or*
#: :class:`CSROp` is not :attr:`~CSROp.NONE`.
#:
#: ..
#:     either:
#:
#:     * :data:`RegRead` is asserted.
#:     * :data:`RegWrite` is asserted and we are writing to the same address.
#:
#: The register file is
#: :meth:`transparent <amaranth:amaranth.lib.memory.Memory.read_port>`; a
#: write and read to/from the same address on the same cycle will use the
#: value to-be-written on the read port on the next active edge.
#:
#: This field has no effect if :class:`CSROp` is *not* :attr:`~CSROp.NONE`.
#:
#:   .. todo::
#:
#:      I need to verify what happens when we :data:`RegWrite` to the same
#:      address with deasserted read-enable. Will it "blow away" the current
#:      read port value?
#:
#: ..
#:   .. todo::
#:
#:      Check to make sure there are no surprises with how transparency
#:      interacts with deasserted read-enable.
#:
RegRead = unsigned(1)


#: If set, write to the :class:`register file <sentinel.datapath.RegFile>` this
#: cycle. The write will be valid on the next active edge.
#:
#: This field has no effect if :class:`CSROp` is *not* :attr:`~CSROp.NONE`.
RegWrite = unsigned(1)


class RegRSel(enum.Enum):
    """Select register to be read to :class:`register file <sentinel.datapath.RegFile>`.

    This field has no effect if :class:`CSROp` is *not* :attr:`~CSROp.NONE`.
    """  # noqa: E501

    #: int: Read from the register specified in the
    #: :attr:`~sentinel.insn.Insn.rs1` field of the current instruction.
    INSN_RS1 = 0
    #: int: Read from the register specified in the
    #: :attr:`~sentinel.insn.Insn.rs2` field of the current instruction.
    INSN_RS2 = 1


class RegWSel(enum.Enum):
    """Select register to be written to :class:`register file <sentinel.datapath.RegFile>`.

    This field has no effect if :class:`CSROp` is *not* :attr:`~CSROp.NONE`.
    """  # noqa: E501

    #: int: Write to the register specified in the
    #: :attr:`~sentinel.insn.Insn.rd` field of the current instruction.
    INSN_RD = 0
    #: int: Write ``x0``, the zero register. For space reasons, there is no
    #: hardcoded zero register. Microcode initialization *must* write ``0``
    #: to the reg file when this option is selected, otherwise Undefined
    #: Behavior will result pretty quickly.
    ZERO = 1


class CSROp(enum.Enum):
    """Select operation on :class:`CSR file <sentinel.datapath.CSRFile>`."""

    #: int: Do a read and/or write to the
    #: :class:`register file <sentinel.datapath.RegFile>` this cycle.
    #:
    #: This variant qualifies :data:`RegRead`, :data:`RegWrite`,
    #: :class:`RegRSel`, and :class:`RegWSel`; :class:`CSRSel` has no effect
    #: when this variant is selected.
    NONE = 0
    #: int: Read from the :class:`CSR file <sentinel.datapath.CSRFile>` this
    #: cycle. The read will be valid on the next active edge. As in
    #: :data:`RegRead`, reads are transparent.
    READ_CSR = 1
    #: int: Write to the :class:`CSR file <sentinel.datapath.CSRFile>` this
    #: cycle. The write will be valid on the next active edge.
    WRITE_CSR = 2


class CSRSel(enum.Enum):
    """Select register from :class:`CSR file <sentinel.datapath.CSRFile>` to read or write.

    This field has no effect if :class:`CSROp` is :attr:`~CSROp.NONE`.
    """  # noqa: E501

    #: int: Select the CSR register specified by the
    #: :ref:`compressed CSR address <mapping-details>`, derived from the
    #: current instruction.
    #:
    #: ..
    #:   This in turn is derived
    #:   from the :attr:`~sentinel.insn.Insn.funct12` field of the current
    #:   instruction.
    INSN_CSR = 0
    #: int: Select the CSR register specified by :data:`Target`, using the
    #: :ref:`compressed address encoding <mapping-details>`.
    TRG_CSR = 1


#: If set, set Wishbone ``CYC_O`` and ``STB_O`` to the asserted state,
#: indicating that a memory transfer is imminent. This signal also qualifies
#: :class:`~sentinel.align.AddressAlign` outputs.
#:
#: As per the Wishbone spec, since Sentinel does not use wait states,
#: tying ``CYC_O`` and ``STB_O`` to the same signal is sound. See Permission
#: 3.40.
MemReq = unsigned(1)


class MemSel(enum.Enum):
    """Select memory transfer type in progress.

    This field indirectly controls the the Wishbone ``SEL_O``, ``DAT_I``
    (for reads/loads that are *not* instruction fetches), and ``DAT_O`` lines
    (writes/stores). See :mod:`sentinel.align` for more information.
    """

    #: int: Memory access is instruction fetch or none at all- data width and
    #: ``SEL_O`` is determined automatically.
    AUTO = 0
    #: int: Memory access is 8-bit; only one of bit ``0``, ``1``, ``2``, and
    #: ``3`` of ``SEL_O`` is asserted. Read and write data will be shifted
    #: appropriately.
    BYTE = 1
    #: int: Memory access is 16-bit; either bits ``0`` and ``1`` or ``2`` and
    #: ``3`` of ``SEL_O`` are asserted. Read and write data will be shifted
    #: appropriately.
    HWORD = 2
    #: int: Memory access is 32-bit; all bits of ``SEL_O`` asserted.
    WORD = 3


class MemExtend(enum.Enum):
    """Extend read data to :attr:`~MemSel.WORD` width.

    Sentinel CPU directly reads the ``DAT_I`` Wishbone signal when performing
    instruction fetches and loads. Fetches are always :attr:`~MemSel.WORD`
    sized, but loads can be variable-sized. RISC-V specifies that loads less
    than :attr:`~MemSel.WORD` width should have the unused bits filled/extended
    with either ``0`` (unsigned/signed) or ``1`` (signed).

    This field will make sure :attr:`~MemSel.BYTE` and :attr:`~MemSel.HWORD`
    loads are properly extended before
    :attr:`latching data <sentinel.alu.BSrcMux.dat_r>` for further use by
    Sentinel. It has no effect for :attr:`~MemSel.WORD` or
    :attr:`~MemSel.AUTO` loads.
    """

    #: int: Sign-extend ``DAT_I`` to :attr:`~MemSel.WORD` width; bits
    #: ``8``-``31`` are zero for :attr:`~MemSel.BYTE` loads and bits
    #: ``16``-``31`` are zero for :attr:`~MemSel.HWORD` loads.
    ZERO = 0
    #: int: Sign-extend ``DAT_I`` to :attr:`~MemSel.WORD` width, using bit
    #: ``7`` for :attr:`~MemSel.BYTE` loads and, bit ``15`` for
    #: :attr:`~MemSel.HWORD` loads.
    SIGN = 1


#: If set, latch the :attr:`ALU output <sentinel.alu.ALU.o>` into an internal
#: register representing the raw byte address for an upcoming Wishbone memory
#: transaction. This internal register indirectly controls the Wishbone
#: ``ADR_O`` and ``SEL_O`` lines via :class:`~sentinel.align.AddressAlign`.
#: Used for both Wishbone reads and writes.
LatchAdr = unsigned(1)


#: If set, latch :attr:`write data <sentinel.align.WriteDataAlign.wb_dat_w>`
#: into an internal register which directly drives the Wisbone signal
#: ``DAT_O``. The data will be appropriately aligned for an upcoming Wishbone
#: write, based upon the contents of the internal address register controlled
#: by :data:`LatchAdr`. Used only for Wishbone writes.
LatchData = unsigned(1)


#: If set, set Wishbone ``WE_O`` to the asserted state, indicating a Wishbone
#: write. Not used by other core components.
WriteMem = unsigned(1)


#: If set, indicate that the current Wishbone transaction is an instruction
#: fetch. Currently, this signal overrides
#: :class:`address alignment <sentinel.align.AddressAlign>` behavior so that
#: instruction fetches will succeed. In the future,
#: this signal will also be used for a Wishbone tag of some sort.
#:
#: Instruction decode begins automatically upon receipt of Wishbone ``ACK_I``.
InsnFetch = unsigned(1)


class ExceptCtl(enum.Enum):
    """Perform a variety of exception-handling related tasks."""

    #: int: Do nothing this cycle.
    NONE = 0
    #: int: Check :class:`~sentinel.decode.Decode` for exceptions and latch
    #: results into :class:`~sentinel.exception.ExceptionRouter` this cycle.
    LATCH_DECODER = 1
    #: int: Use :class:`~sentinel.exception.ExceptionRouter` to check whether a
    #: ``JAL`` triggered alignment exceptions this cycle. Valid only when the
    #: current instruction is in fact a ``JAL``.
    LATCH_JAL = 2
    #: int: Use :class:`~sentinel.exception.ExceptionRouter` to check whether a
    #: store triggered alignment exceptions this cycle. Valid only when the
    #: current instruction is in fact a store.
    LATCH_STORE_ADR = 3
    #: int: Use :class:`~sentinel.exception.ExceptionRouter` to check whether a
    #: load triggered alignment exceptions this cycle. Valid only when the
    #: current instruction is in fact a load.
    LATCH_LOAD_ADR = 4
    #: int: Move ``MIE`` to ``MPIE``, set ``MIE`` to ``0`` this cycle. See
    #: :class:`~sentinel.datapath.CSRFile` for implementation.
    ENTER_INT = 5
    #: int: Move ``MPIE`` to ``MIE``, set ``MPIE`` to ``1`` this cycle. See
    #: :class:`~sentinel.datapath.CSRFile` for implementation.
    LEAVE_INT = 6
