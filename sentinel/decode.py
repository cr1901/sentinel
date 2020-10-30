import enum

from nmigen import *

class ImmediateGenerator(Elaboratable):
    def __init__(self):
        self.insn = Signal(32)
        self.imm_type = Signal(InsnImmFormat)
        self.imm = Signal(32)

        self.sign = Signal()

    def elaborate(self, platform):
        m = Module()

        m.d.comb += [self.sign.eq(self.insn[31])]

        with m.Switch(self.imm_type):
            with m.Case(InsnImmFormat.I):
                m.d.comb += self.imm.eq(Cat(self.insn[20:31], Repl(self.sign, 21)))
            with m.Case(InsnImmFormat.S):
                m.d.comb += self.imm.eq(Cat(self.insn[7], self.insn[8:12], self.insn[25:31], Repl(self.sign, 21)))
            with m.Case(InsnImmFormat.B):
                m.d.comb += self.imm.eq(Cat(C(0), self.insn[8:12], self.insn[25:31], self.insn[7], Repl(self.sign, 20)))
            with m.Case(InsnImmFormat.U):
                m.d.comb += self.imm.eq(Cat(C(0, 12), self.insn[12:20], self.insn[20:30], self.sign))
            with m.Case(InsnImmFormat.J):
                m.d.comb += self.imm.eq(Cat(C(0), self.insn[21:25], self.insn[25:31], self.insn[20], self.insn[12:20], Repl(self.sign, 12)))

        return m

    def ports(self):
        return [self.insn, self.imm_type, self.imm]

    def sim_hooks(self, sim):
        pass


class OpcodeType(enum.Enum):
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


class InsnImmFormat(enum.Enum):
    R = 0
    I = 1
    S = 2
    B = 3 # Accepted in place of S.
    U = 4
    J = 5 # Accepted in place of U.


class Decode(Elaboratable):
    def __init__(self):
        # Shared with data bus- use do_decode to ignore.
        self.do_decode = Signal()
        self.insn = Signal(32)
        self.src_a = Signal(5)
        self.src_b = Signal(5)
        self.reg_or_imm = Signal()
        self.imm = Signal(32)
        self.dst = Signal(5)
        self.shift = Signal()
        self.illegal = Signal()
        self.width = Signal()
        self.e_type = Signal()
        self.custom = Signal()

        # Map from funct3, and funct7, and funct12 bits to a 4-bit ID based on
        # major opcode.
        # * For OP/OP_IMM, use a direct concatenation of funct3 and funct7.
        # * For ECALL/EBREAK, only the low bit of funct12 is used.
        self.requested_op = Signal(4)

        ###

        self.opcode = Signal(OpcodeType, reset=0)
        self.rd = Signal(5)
        self.funct3 = Signal(3)
        self.rs1 = Signal(5)
        self.rs2 = Signal(5)
        self.funct7 = Signal(7)
        self.funct12 = Signal(12)

        self.definitely_illegal = Signal()
        self.probably_illegal = Signal()

        self.immgen = ImmediateGenerator()

    def elaborate(self, platform):
        m = Module()

        m.submodules.immgen = self.immgen

        m.d.comb += [
            self.immgen.insn.eq(self.insn),
            self.definitely_illegal.eq(self.insn.all() | ~self.insn.any() | (self.insn[0:2] != 0b11)),
            # Helpers
            self.opcode.eq(self.insn[2:7]),
            self.rd.eq(self.insn[7:12]),
            self.funct3.eq(self.insn[12:15]),
            self.rs1.eq(self.insn[15:20]),
            self.rs2.eq(self.insn[20:25]),
            self.funct7.eq(self.insn[25:32]),
            self.funct12.eq(self.insn[20:32])
        ]

        with m.If(self.do_decode):
            m.d.sync += [
                self.illegal.eq(self.definitely_illegal | self.probably_illegal),
                self.imm.eq(self.immgen.imm)
            ]

            # TODO: Might be worth hoisting comb statements out of m.If?
            with m.Switch(self.opcode):
                with m.Case(OpcodeType.OP_IMM):
                    m.d.sync += [
                        self.src_a.eq(self.rs1),
                        self.src_b.eq(self.rs2),
                        self.dst.eq(self.rd)
                    ]

                    m.d.comb += self.immgen.imm_type.eq(InsnImmFormat.I)

                    with m.If((self.funct3 == 1) | (self.funct3 == 5)):
                        with m.If(self.funct3 == 1):
                            with m.If(self.funct7 != 0):
                                m.d.comb += self.probably_illegal.eq(1)
                        with m.Else():
                            with m.If((self.funct7 != 0) & (self.funct7 != 0b0100000)):
                                m.d.comb += self.probably_illegal.eq(1)
                        m.d.sync += self.requested_op.eq(Cat(self.funct3, self.funct7[-2]))
                    with m.Else():
                        m.d.sync += self.requested_op.eq(Cat(self.funct3, C(0)))

                with m.Case(OpcodeType.LUI):
                    m.d.comb += self.immgen.imm_type.eq(InsnImmFormat.U)

                with m.Case(OpcodeType.AUIPC):
                    m.d.comb += self.immgen.imm_type.eq(InsnImmFormat.U)

                with m.Case(OpcodeType.OP):
                    with m.If((self.funct3 == 0) | (self.funct3 == 5)):
                        with m.If((self.funct7 != 0) & (self.funct7 != 0b0100000)):
                            m.d.comb += self.probably_illegal.eq(1)
                        m.d.sync += self.requested_op.eq(Cat(self.funct3, self.funct7[-2]))
                    with m.Else():
                        with m.If(self.funct7 != 0):
                            m.d.comb += self.probably_illegal.eq(1)
                        m.d.sync += self.requested_op.eq(Cat(self.funct3, C(0)))

                with m.Case(OpcodeType.JAL):
                    m.d.comb += self.immgen.imm_type.eq(InsnImmFormat.J)

                with m.Case(OpcodeType.JALR):
                    m.d.comb += self.immgen.imm_type.eq(InsnImmFormat.I)

                    with m.If(self.funct3 != 0):
                        m.d.comb += self.probably_illegal.eq(1)

                with m.Case(OpcodeType.BRANCH):
                    m.d.comb += self.immgen.imm_type.eq(InsnImmFormat.B)

                    with m.If((self.funct3 == 2) | (self.funct3 == 3)):
                        m.d.comb += self.probably_illegal.eq(1)

                with m.Case(OpcodeType.LOAD):
                    m.d.comb += self.immgen.imm_type.eq(InsnImmFormat.I)

                    with m.If((self.funct3 == 3) | (self.funct3 == 6) | (self.funct3 == 7)):
                        m.d.comb += self.probably_illegal.eq(1)

                with m.Case(OpcodeType.STORE):
                    m.d.comb += self.immgen.imm_type.eq(InsnImmFormat.S)

                    with m.If(self.funct3 >= 3):
                        m.d.comb += self.probably_illegal.eq(1)

                with m.Case(OpcodeType.CUSTOM_0):
                    m.d.comb += self.probably_illegal.eq(1)

                with m.Case(OpcodeType.MISC_MEM):
                    # RS1 and RD should be ignored for FENCE insn in a base impl.

                    with m.If(self.funct3 != 0):
                        m.d.comb += self.probably_illegal.eq(1)

                with m.Case(OpcodeType.SYSTEM):
                    m.d.comb += self.e_type.eq(self.funct12[0])

                    with m.If((self.funct12[1:] != 0) | (self.rs1 != 0) | (self.rd != 0) | (self.funct3 != 0)):
                        m.d.comb += self.probably_illegal.eq(1)

                with m.Case():
                    m.d.comb += self.probably_illegal.eq(1)

        return m

    def ports(self):
        return [self.insn, self.do_decode, self.src_a, self.src_b,
                self.reg_or_imm, self.imm, self.dst, self.illegal,
                self.width, self.custom, self.opcode]

    def sim_hooks(self, sim):
        pass



class MinorOpcodeMapper(Elaboratable):
    def __init__(self):
        pass
