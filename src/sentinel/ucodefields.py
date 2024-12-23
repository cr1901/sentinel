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


#: Jump target supplied by the currently-executing microinstruction.
Target = unsigned(8)


class JmpType(enum.Enum, shape=2):
    CONT = 0
    NOP = 0
    MAP = 1
    DIRECT = 2
    DIRECT_ZERO = 3


class OpType(enum.Enum):
    ADD = 0
    SUB = 1
    AND = 2
    OR = 3
    XOR = 4
    SLL = 5
    SRL = 6
    SRA = 7
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
    #: int: Increment the Program Counter by ``4``.
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
    #: int: Feed back the :attr:`ALU output <sentinel.alu.ALU.o` into the
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
    #: :attr:`MCAUSE latch <sentinel.exception.ExceptionControl.out>`.
    MCAUSE_LATCH = 7


class ALUIMod(enum.Enum):
    NONE = 0
    INV_MSB_A_B = 1


class ALUOMod(enum.Enum):
    NONE = 0
    INV_LSB_O = 1
    CLEAR_LSB_O = 2


RegRead = unsigned(1)


RegWrite = unsigned(1)


class RegRSel(enum.Enum):
    INSN_RS1 = 0
    INSN_RS2 = 1


class RegWSel(enum.Enum):
    INSN_RD = 0
    ZERO = 1


class CSROp(enum.Enum):
    NONE = 0
    READ_CSR = 1
    WRITE_CSR = 2


class CSRSel(enum.Enum):
    INSN_CSR = 0
    TRG_CSR = 1


MemReq = unsigned(1)


class MemSel(enum.Enum):
    AUTO = 0
    BYTE = 1
    HWORD = 2
    WORD = 3


class MemExtend(enum.Enum):
    ZERO = 0
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
#: write.
WriteMem = unsigned(1)


#: If set, indicate that the current Wishbone transaction is an instruction
#: fetch. In the future, this will be used for a Wishbone tag of some sort.
InsnFetch = unsigned(1)


class ExceptCtl(enum.Enum):
    NONE = 0
    LATCH_DECODER = 1
    LATCH_JAL = 2
    LATCH_STORE_ADR = 3
    LATCH_LOAD_ADR = 4
    ENTER_INT = 5
    LEAVE_INT = 6
