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
    CMP_LTU = 9
    CMP_GEU = 10
    NOP = 11
    PASSTHRU = 12


class CondTest(enum.Enum):
    INTR = 0
    EXCEPTION = 1
    CMP_OKAY = 2
    CMP_ZERO = 3
    MEM_VALID = 4
    TRUE = 5


class PcAction(enum.Enum):
    HOLD = 0
    INC = 1
    LOAD_ALU_O = 2


class SrcOp(enum.Enum):
    NONE = 0
    LATCH_A = 1
    LATCH_B = 2
    LATCH_A_B = 3


class ASrc(enum.Enum):
    GP = 0
    PC = 1
    CSR = 2
    IMM = 3
    TARGET = 4
    ALU_O = 5
    ZERO = 6


class BSrc(enum.Enum):
    GP = 0
    PC = 1
    CSR = 2
    IMM = 3
    TARGET = 4
    ONE = 5


class ALUMod(enum.Enum):
    NONE = 0
    INV_MSB_A_B = 1
    INV_LSB_O = 2
    TWOS_COMP_B = 3


class RegSet(enum.Enum):
    GP = 0
    SCRATCH = 1


class RegRSel(enum.Enum):
    INSN_RS1 = 0
    INSN_RS2 = 1
    UCODE0 = 2
    UCODE1 = 3


class RegWSel(enum.Enum):
    INSN_RD = 0
    UCODE0 = 2
    UCODE1 = 3
