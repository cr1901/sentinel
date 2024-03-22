# Instruction class (this file is required to avoid circular imports)

from amaranth import Cat, Value, C, unsigned
from amaranth.lib import enum

from .csr import Quadrant, AccessMode


class Insn:
    """View of all immediately-apparent information in a RISC-V instruction."""

    # "Immediately-apparent" means "I can get this info with Cats, Slices,
    # and Replicates".

    # Does not inherit from View because Layouts are not designed to retrieve
    # non-contiguous bits.

    ECALL = 0b00000000000000000000000001110011
    EBREAK = 0b00000000000100000000000001110011
    MRET = 0b00110000001000000000000001110011
    WFI = 0b00010000010100000000000001110011

    class _Imm:
        def __init__(self, value):
            self.raw = value
            self.sign = self.raw[-1]

        @property
        def I(self):  # noqa: E743
            return Cat(self.raw[20:31], Value.replicate(self.sign, 21))

        @property
        def S(self):
            return Cat(self.raw[7], self.raw[8:12], self.raw[25:31],
                       Value.replicate(self.sign, 21))

        @property
        def B(self):
            return Cat(C(0), self.raw[8:12], self.raw[25:31], self.raw[7],
                       Value.replicate(self.sign, 20))

        @property
        def U(self):
            return Cat(C(0, 12), self.raw[12:20], self.raw[20:31], self.sign)

        @property
        def J(self):
            return Cat(C(0), self.raw[21:25], self.raw[25:31], self.raw[20],
                       self.raw[12:20], Value.replicate(self.sign, 12))

    class _CSR:
        RW = 0b001
        RS = 0b010
        RC = 0b011
        RWI = 0b101
        RSI = 0b110
        RCI = 0b111

        def __init__(self, value):
            self.raw = value[20:]

        @property
        def addr(self):
            return self.raw

        @property
        def quadrant(self):
            return enum.EnumView(Quadrant, self.raw[8:10])

        @property
        def access(self):
            return enum.EnumView(AccessMode, self.raw[10:])

    def __init__(self, value):
        self.raw = value
        self.imm = Insn._Imm(self.raw)
        self.csr = Insn._CSR(self.raw)

    @property
    def opcode(self):
        return OpcodeType(self.raw[2:7])

    @property
    def rd(self):
        return self.raw[7:12]

    @property
    def funct3(self):
        return self.raw[12:15]

    @property
    def rs1(self):
        return self.raw[15:20]

    @property
    def rs2(self):
        return self.raw[20:25]

    @property
    def funct7(self):
        return self.raw[25:]

    @property
    def funct12(self):
        return self.raw[20:]

    @property
    def sign(self):
        return self.raw[-1]


class OpcodeType(enum.Enum, shape=unsigned(5)):
    OP_IMM = 0b00100
    LUI = 0b01101
    AUIPC = 0b00101
    OP = 0b01100
    JAL = 0b11011
    JALR = 0b11001
    BRANCH = 0b11000
    LOAD = 0b00000
    STORE = 0b01000
    CUSTOM_0 = 0b00010
    MISC_MEM = 0b00011
    SYSTEM = 0b11100
