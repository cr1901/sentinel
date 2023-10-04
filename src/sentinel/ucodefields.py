# Microcode field classes (this file is required to avoid circular imports)

import enum


class JmpType(enum.Enum):
    CONT = 0
    NOP = 0
    MAP = 1
    DIRECT = 2
    MAP_FUNCT = 3
    DIRECT_ZERO = 4


class OpType(enum.Enum):
    ADD = 0
    SUB = 1
    AND = 2
    OR = 3
    XOR = 4
    SLL = 5
    SRL = 6
    SRA = 7
    CMP_EQ = 8
    CMP_NE = 9
    CMP_LT = 10
    CMP_LTU = 11
    CMP_GE = 12
    CMP_GEU = 13
    NOP = 14


class CondTest(enum.Enum):
    FALSE = 0
    INTR = 1
    EXCEPTION = 2
    CMP_OKAY = 3
    MEM_VALID = 4
    TRUE = 5


class PcAction(enum.Enum):
    HOLD = 0
    INC = 1
    LOAD = 2


class ASrc(enum.Enum):
    GP = 0
    PC = 1


class BSrc(enum.Enum):
    GP = 0
    IMM = 1
    TARGET = 2


class RegOp(enum.Enum):
    NONE = 0
    READ_A = 1
    READ_B_LATCH_A = 2
    LATCH_B = 3
    WRITE_DST = 4
