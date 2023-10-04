from .ucodefields import OpType

from amaranth import Elaboratable, Signal, Module
from amaranth.lib.wiring import Component, Signature, In, Out


class Unit(Elaboratable):
    def __init__(self, width, op):
        self.a = Signal(width)
        self.b = Signal(width)
        self.o = Signal(width)
        self.op = op

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.o.eq(self.op(self.a, self.b))
        return m


class Adder(Unit):
    def __init__(self, width):
        super().__init__(width, lambda a, b: a + b)


class Subtractor(Unit):
    def __init__(self, width):
        super().__init__(width, lambda a, b: a - b)


class AND(Unit):
    def __init__(self, width):
        super().__init__(width, lambda a, b: a & b)


class OR(Unit):
    def __init__(self, width):
        super().__init__(width, lambda a, b: a | b)


class XOR(Unit):
    def __init__(self, width):
        super().__init__(width, lambda a, b: a ^ b)


class ShiftLogicalLeft(Unit):
    def __init__(self, width):
        super().__init__(width, lambda a, b: a << 1)


class ShiftLogicalRight(Unit):
    def __init__(self, width):
        super().__init__(width, lambda a, b: a >> 1)


class ShiftArithmeticRight(Unit):
    def __init__(self, width):
        super().__init__(width, lambda a, b: a.as_signed() >> 1)


class CompareEqual(Unit):
    def __init__(self, width):
        super().__init__(width, lambda a, b: a == b)


class CompareNotEqual(Unit):
    def __init__(self, width):
        super().__init__(width, lambda a, b: a != b)


class CompareLessThan(Unit):
    def __init__(self, width):
        super().__init__(width, lambda a, b: a.as_signed() < b.as_signed())


class CompareLessThanUnsigned(Unit):
    def __init__(self, width):
        super().__init__(width, lambda a, b: a < b)


class CompareGreaterThanEqual(Unit):
    def __init__(self, width):
        super().__init__(width, lambda a, b: a.as_signed() >= b.as_signed())


class CompareGreaterThanEqualUnsigned(Unit):
    def __init__(self, width):
        super().__init__(width, lambda a, b: a >= b)


AluCtrlSignature = Signature({
    "op": Out(OpType, reset=OpType.NOP),
})


def alu_data_signature(width):
    return Signature({
        "a": Out(width),
        "b": Out(width),
        "o": In(width)
    })


def alu_signature(width):
    return Signature({
        "ctrl": In(AluCtrlSignature),
        "data": In(alu_data_signature(width))
    })


class ALU(Component):
    @property
    def signature(self):
        return alu_signature(self.width)

    # Assumes: op is held steady for duration of op.
    def __init__(self, width: int):
        self.width = width
        super().__init__()

        ###

        self.o_mux = Signal(width)

        self.add = Adder(width)
        self.sub = Subtractor(width)
        self.and_ = AND(width)
        self.or_ = OR(width)
        self.xor = XOR(width)
        self.sll = ShiftLogicalLeft(width)
        self.srl = ShiftLogicalRight(width)
        self.sar = ShiftArithmeticRight(width)
        self.cmp_equal = CompareEqual(width)
        self.cmp_not_equal = CompareNotEqual(width)
        self.cmp_lt = CompareLessThan(width)
        self.cmp_ltu = CompareLessThanUnsigned(width)
        self.cmp_gte = CompareGreaterThanEqual(width)
        self.cmp_gteu = CompareGreaterThanEqualUnsigned(width)

    def elaborate(self, platform):
        m = Module()
        m.submodules.add = self.add
        m.submodules.sub = self.sub
        m.submodules.and_ = self.and_
        m.submodules.or_ = self.or_
        m.submodules.xor = self.xor
        m.submodules.sll = self.sll
        m.submodules.srl = self.srl
        m.submodules.sal = self.sar
        m.submodules.cmp_equal = self.cmp_equal
        m.submodules.cmp_not_equal = self.cmp_not_equal
        m.submodules.cmp_lt = self.cmp_lt
        m.submodules.cmp_ltu = self.cmp_ltu
        m.submodules.cmp_gte = self.cmp_gte
        m.submodules.cmp_gteu = self.cmp_gteu

        for submod in [self.add, self.sub, self.and_, self.or_, self.xor,
                       self.sll, self.srl, self.sar, self.cmp_equal,
                       self.cmp_not_equal, self.cmp_lt, self.cmp_ltu,
                       self.cmp_gte, self.cmp_gteu]:
            m.d.comb += [
                submod.a.eq(self.data.a),
                submod.b.eq(self.data.b),
            ]

        with m.Switch(self.ctrl.op):
            with m.Case(OpType.ADD):
                m.d.comb += self.o_mux.eq(self.add.o),
            with m.Case(OpType.SUB):
                m.d.comb += self.o_mux.eq(self.sub.o),
            with m.Case(OpType.AND):
                m.d.comb += self.o_mux.eq(self.and_.o),
            with m.Case(OpType.OR):
                m.d.comb += self.o_mux.eq(self.or_.o),
            with m.Case(OpType.XOR):
                m.d.comb += self.o_mux.eq(self.xor.o),
            with m.Case(OpType.SLL):
                m.d.comb += self.o_mux.eq(self.sll.o),
            with m.Case(OpType.SRL):
                m.d.comb += self.o_mux.eq(self.srl.o),
            with m.Case(OpType.SRA):
                m.d.comb += self.o_mux.eq(self.sar.o),
            with m.Case(OpType.CMP_EQ):
                m.d.comb += self.o_mux.eq(self.cmp_equal.o),
            with m.Case(OpType.CMP_NE):
                m.d.comb += self.o_mux.eq(self.cmp_not_equal.o),
            with m.Case(OpType.CMP_LT):
                m.d.comb += self.o_mux.eq(self.cmp_lt.o),
            with m.Case(OpType.CMP_LTU):
                m.d.comb += self.o_mux.eq(self.cmp_ltu.o),
            with m.Case(OpType.CMP_GE):
                m.d.comb += self.o_mux.eq(self.cmp_gte.o),
            with m.Case(OpType.CMP_GEU):
                m.d.comb += self.o_mux.eq(self.cmp_gteu.o),

        m.d.sync += [
            self.data.o.eq(self.o_mux),
        ]
        return m
