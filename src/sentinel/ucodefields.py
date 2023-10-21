# Microcode field classes (this file is required to avoid circular imports)

import enum


class JmpType(enum.Enum):
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
    EXCEPTION = 0
    CMP_ALU_O_5_LSBS_ZERO = 1
    CMP_ALU_O_ZERO = 2
    MEM_VALID = 3
    TRUE = 4


class PcAction(enum.Enum):
    HOLD = 0
    INC = 1
    LOAD_ALU_O = 2


class ASrc(enum.Enum):
    GP = 0
    IMM = 1
    ALU_O = 2
    ZERO = 3
    FOUR = 4


class BSrc(enum.Enum):
    GP = 0
    PC = 1
    IMM = 2
    ONE = 3
    DAT_R = 4


class ALUIMod(enum.Enum):
    NONE = 0
    INV_MSB_A_B = 1


class ALUOMod(enum.Enum):
    NONE = 0
    INV_LSB_O = 1
    CLEAR_LSB_O = 2


class RegRSel(enum.Enum):
    INSN_RS1 = 0
    INSN_RS2 = 1


class RegWSel(enum.Enum):
    INSN_RD = 0
    ZERO = 1


class MemSel(enum.Enum):
    AUTO = 0
    BYTE = 1
    HWORD = 2
    WORD = 3


class MemExtend(enum.Enum):
    ZERO = 0
    SIGN = 1
