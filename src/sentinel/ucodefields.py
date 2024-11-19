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
    #: The memory bus is valid when :attr:`~sentinel.top.Top.bus.ack` in
    #: :class:`~sentinel.top.Top` is asserted.
    MEM_VALID = 2

    #: Unconditionally set/asserted. When :data:`InvertTest` is asserted,
    #: the test unconditionally *fails*.
    TRUE = 3


#: If set, invert the result of the conditional test on the output of
#: :class:`CondTest` this clock cycle.
InvertTest = unsigned(1)


class PcAction(enum.Enum):
    """Perform an action on the RISC-V Program Counter this cycle."""

    #: int: Do not change the Program Counter; hold the current value.
    HOLD = 0
    #: int: Increment the Program Counter by ``4``.
    INC = 1
    #: int: Set the Program Counter to the value currently on the
    #: :class:`~sentinel.alu.ALU` :attr:`output <sentinel.alu.ALU.o>`.
    LOAD_ALU_O = 2


#: If set, latch the :attr:`A input <sentinel.alu.ALU.a>` to the
#: :class:`~sentinel.alu.ALU` from the :class:`~sentinel.alu.ASrcMux`.
LatchA = unsigned(1)

#: If set, latch the :attr:`B input <sentinel.alu.ALU.b>` to the
#: :class:`~sentinel.alu.ALU` from the :class:`~sentinel.alu.BSrcMux`.
LatchB = unsigned(1)


class ASrc(enum.Enum):
    GP = 0
    IMM = 1
    ALU_O = 2
    ZERO = 3
    FOUR = 4
    NEG_ONE = 5
    THIRTY_ONE = 6


class BSrc(enum.Enum):
    GP = 0
    PC = 1
    IMM = 2
    ONE = 3
    DAT_R = 4
    CSR_IMM = 5
    CSR = 6
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


LatchAdr = unsigned(1)


LatchData = unsigned(1)


WriteMem = unsigned(1)


InsnFetch = unsigned(1)


class ExceptCtl(enum.Enum):
    NONE = 0
    LATCH_DECODER = 1
    LATCH_JAL = 2
    LATCH_STORE_ADR = 3
    LATCH_LOAD_ADR = 4
    ENTER_INT = 5
    LEAVE_INT = 6
