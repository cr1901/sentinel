from .ucodefields import OpType, ALUTmp, ALUMod

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


class CompareLessThanUnsigned(Unit):
    def __init__(self, width):
        super().__init__(width, lambda a, b: a < b)


class CompareGreaterThanEqualUnsigned(Unit):
    def __init__(self, width):
        super().__init__(width, lambda a, b: a >= b)


AluCtrlSignature = Signature({
    "op": Out(OpType, reset=OpType.NOP),
    "tmp": Out(ALUTmp),
    "mod": Out(ALUMod),
    "cmp": In(1),
    "zero": In(1)
})


def alu_data_signature(width):
    return Signature({
        "a": Out(width),
        "b": Out(width),
        "o": In(width),
        "c": In(width),
        "d": In(width),
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
        self.and_ = AND(width)
        self.or_ = OR(width)
        self.xor = XOR(width)
        self.sll = ShiftLogicalLeft(width)
        self.srl = ShiftLogicalRight(width)
        self.sar = ShiftArithmeticRight(width)
        self.cmp_equal = CompareEqual(width)
        self.cmp_ltu = CompareLessThanUnsigned(width)
        self.cmp_gteu = CompareGreaterThanEqualUnsigned(width)

    def elaborate(self, platform):
        m = Module()
        m.submodules.add = self.add
        m.submodules.and_ = self.and_
        m.submodules.or_ = self.or_
        m.submodules.xor = self.xor
        m.submodules.sll = self.sll
        m.submodules.srl = self.srl
        m.submodules.sal = self.sar
        m.submodules.cmp_equal = self.cmp_equal
        m.submodules.cmp_ltu = self.cmp_ltu
        m.submodules.cmp_gteu = self.cmp_gteu

        mod_a = Signal.like(self.data.a)
        mod_b = Signal.like(self.data.b)

        with m.Switch(self.ctrl.mod):
            with m.Case(ALUMod.NONE):
                m.d.comb += [
                    mod_a.eq(self.data.a),
                    mod_b.eq(self.data.b)
                ]
            with m.Case(ALUMod.INV_MSB_A_B):
                m.d.comb += [
                    mod_a.eq(self.data.a),
                    mod_b.eq(self.data.b),
                    mod_a[-1].eq(~self.data.a[-1]),
                    mod_b[-1].eq(~self.data.b[-1]),
                ]
            with m.Case(ALUMod.TWOS_COMP_B):
                m.d.comb += [
                    mod_a.eq(self.data.a),
                    mod_b.eq(-self.data.b)
                ]

        for submod in [self.add, self.and_, self.or_, self.xor,
                       self.sll, self.srl, self.sar, self.cmp_equal,
                       self.cmp_ltu, self.cmp_gteu]:
            m.d.comb += [
                submod.a.eq(mod_a),
                submod.b.eq(mod_b),
            ]

        with m.Switch(self.ctrl.op):
            with m.Case(OpType.ADD):
                m.d.comb += self.o_mux.eq(self.add.o)
            with m.Case(OpType.AND):
                m.d.comb += self.o_mux.eq(self.and_.o)
            with m.Case(OpType.OR):
                m.d.comb += self.o_mux.eq(self.or_.o)
            with m.Case(OpType.XOR):
                m.d.comb += self.o_mux.eq(self.xor.o)
            with m.Case(OpType.SLL):
                m.d.comb += self.o_mux.eq(self.sll.o)
            with m.Case(OpType.SRL):
                m.d.comb += self.o_mux.eq(self.srl.o)
            with m.Case(OpType.SRA):
                m.d.comb += self.o_mux.eq(self.sar.o)
            with m.Case(OpType.CMP_EQ):
                m.d.comb += self.o_mux.eq(self.cmp_equal.o)
            with m.Case(OpType.CMP_LTU):
                m.d.comb += self.o_mux.eq(self.cmp_ltu.o)
            with m.Case(OpType.CMP_GEU):
                m.d.comb += self.o_mux.eq(self.cmp_gteu.o)

        m.d.sync += self.data.o.eq(self.o_mux)
        with m.If(self.ctrl.mod == ALUMod.INV_LSB_O):
            m.d.sync += self.data.o[0].eq(~self.o_mux[0])

        m.d.comb += self.ctrl.cmp.eq(self.data.o[0])
        m.d.comb += self.ctrl.zero.eq(self.data.o == 0)

        with m.Switch(self.ctrl.tmp):
            with m.Case(ALUTmp.WRITE_C):
                m.d.sync += self.data.c.eq(self.o_mux)
            with m.Case(ALUTmp.WRITE_D):
                m.d.sync += self.data.d.eq(self.o_mux)

        return m
