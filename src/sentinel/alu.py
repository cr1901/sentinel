from .ucodefields import OpType, ALUIMod, ALUOMod

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
        super().__init__(width, lambda a, _: a << 1)


class ShiftLogicalRight(Unit):
    def __init__(self, width):
        super().__init__(width, lambda a, _: a >> 1)


class ShiftArithmeticRight(Unit):
    def __init__(self, width):
        super().__init__(width, lambda a, _: a.as_signed() >> 1)


AluCtrlSignature = Signature({
    "op": Out(OpType),
    "imod": Out(ALUIMod),
    "omod": Out(ALUOMod),
    "lsbs_5_zero": In(1),
    "zero": In(1)
})


def alu_data_signature(width):
    return Signature({
        "a": Out(width),
        "b": Out(width),
        "o": In(width),
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
        self.sub = Subtractor(width + 1)
        self.and_ = AND(width)
        self.or_ = OR(width)
        self.xor = XOR(width)
        self.sll = ShiftLogicalLeft(width)
        self.srl = ShiftLogicalRight(width)
        self.sar = ShiftArithmeticRight(width)

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

        mod_a = Signal.like(self.data.a)
        mod_b = Signal.like(self.data.b)

        m.d.comb += [
            mod_a.eq(self.data.a),
            mod_b.eq(self.data.b)
        ]

        with m.If(self.ctrl.imod == ALUIMod.INV_MSB_A_B):
            m.d.comb += [
                mod_a[-1].eq(~self.data.a[-1]),
                mod_b[-1].eq(~self.data.b[-1]),
            ]

        for submod in [self.add, self.sub, self.and_, self.or_, self.xor,
                       self.sll, self.srl, self.sar]:
            m.d.comb += [
                submod.a.eq(mod_a),
                submod.b.eq(mod_b),
            ]

        with m.Switch(self.ctrl.op):
            with m.Case(OpType.ADD):
                m.d.comb += self.o_mux.eq(self.add.o)
            with m.Case(OpType.SUB):
                m.d.comb += self.o_mux.eq(self.sub.o)
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
            with m.Case(OpType.CMP_LTU):
                m.d.comb += self.o_mux.eq(self.sub.o[32])

        m.d.sync += self.data.o.eq(self.o_mux)
        with m.If(self.ctrl.omod == ALUOMod.INV_LSB_O):
            m.d.sync += self.data.o[0].eq(~self.o_mux[0])
        with m.Elif(self.ctrl.omod == ALUOMod.CLEAR_LSB_O):
            m.d.sync += self.data.o[0].eq(0)

        # TODO: LSBS_2_ZERO for JALR/JAL misaligned exceptions?
        m.d.comb += self.ctrl.zero.eq(self.data.o == 0)

        return m
