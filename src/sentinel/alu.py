import enum

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


class Logical(Elaboratable):
    def __init__(self, width):
        self.a = Signal(width)
        self.b = Signal(width)
        self.o = Signal(width)
        self.op = Signal(OpType)

    def elaborate(self, platform):
        m = Module()

        with m.Switch(self.op):
            with m.Case(OpType.AND):
                m.d.comb += self.o.eq(self.a & self.b)
            with m.Case(OpType.OR):
                m.d.comb += self.o.eq(self.a | self.b)
            with m.Case(OpType.XOR):
                m.d.comb += self.o.eq(self.a ^ self.b)

        return m


class Shifter(Elaboratable):
    def __init__(self, width):
        self.a = Signal(width)
        self.b = Signal(width)
        self.o = Signal(width)
        self.do_shift = Signal()
        self.shift_done = Signal()
        self.op = Signal(OpType)

        self.cnt = Signal(5)
        self.do_shift_rose = Signal()
        self.do_shift_prev = Signal()

    def elaborate(self, platform):
        m = Module()

        m.d.sync += self.do_shift_prev.eq(self.do_shift)
        m.d.comb += self.do_shift_rose.eq(~(self.do_shift_prev) &
                                          self.do_shift)

        with m.If(self.do_shift):
            with m.If(self.do_shift_rose):
                m.d.sync += [
                    self.cnt.eq(self.b),
                    self.o.eq(self.a)
                ]
            with m.Else():
                with m.If(self.cnt > 0):
                    with m.Switch(self.op):
                        with m.Case(OpType.SLL):
                            m.d.sync += self.o.eq(self.o.shift_left(1))
                        with m.Case(OpType.SRL):
                            m.d.sync += self.o.eq(self.o.shift_right(1))
                        with m.Case(OpType.SRA):
                            m.d.sync += self.o.eq(self.o.as_signed() >> 1)

                    m.d.sync += self.cnt.eq(self.cnt - 1)
                with m.Else():
                    with m.If(self.do_shift):
                        m.d.comb += self.shift_done.eq(1)

        return m


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


def alu_signature(width):
    return Signature({
        "op": Out(OpType),
        "ready": In(1),
        "a": Out(width),
        "b": Out(width),
        "o": In(width)
    })


class ALUControlGasket(Component):
    signature = Signature({
        "ready": Out(1)
    })

    def __init__(self, alu):
        self.alu = alu
        super().__init__()

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.ready.eq(self.alu.ready)


class ALU(Component):
    @property
    def signature(self):
        return alu_signature(self.width).flip()

    # Assumes: op is held steady for duration of op.
    def __init__(self, width: int):
        self.width = width
        super().__init__()

        self.op.reset = OpType.NOP

        ###

        # Unregistered ready.
        self.ready_next = Signal()
        self.o_mux = Signal(width)

        self.add = Adder(width)
        self.sub = Subtractor(width)
        self.logical = Logical(width)
        self.shift = Shifter(width)
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
        m.submodules.logical = self.logical
        m.submodules.shift = self.shift
        m.submodules.cmp_equal = self.cmp_equal
        m.submodules.cmp_not_equal = self.cmp_not_equal
        m.submodules.cmp_lt = self.cmp_lt
        m.submodules.cmp_ltu = self.cmp_ltu
        m.submodules.cmp_gte = self.cmp_gte
        m.submodules.cmp_gteu = self.cmp_gteu

        for submod in [self.add, self.sub, self.logical, self.shift,
                       self.cmp_equal, self.cmp_not_equal, self.cmp_lt,
                       self.cmp_ltu, self.cmp_gte, self.cmp_gteu]:
            m.d.comb += [
                submod.a.eq(self.a),
                submod.b.eq(self.b),
            ]

        m.d.comb += self.logical.op.eq(self.op)
        m.d.comb += self.shift.op.eq(self.op)

        with m.Switch(self.op):
            with m.Case(OpType.ADD):
                m.d.comb += [
                    self.o_mux.eq(self.add.o),
                    self.ready_next.eq(1)
                ]
            with m.Case(OpType.SUB):
                m.d.comb += [
                    self.o_mux.eq(self.sub.o),
                    self.ready_next.eq(1)
                ]
            with m.Case(OpType.AND):
                m.d.comb += [
                    self.o_mux.eq(self.logical.o),
                    self.ready_next.eq(1)
                ]
            with m.Case(OpType.OR):
                m.d.comb += [
                    self.o_mux.eq(self.logical.o),
                    self.ready_next.eq(1)
                ]
            with m.Case(OpType.XOR):
                m.d.comb += [
                    self.o_mux.eq(self.logical.o),
                    self.ready_next.eq(1)
                ]
            with m.Case(OpType.SLL):
                m.d.comb += [
                    self.o_mux.eq(self.shift.o),
                    self.ready_next.eq(self.shift.shift_done),
                    self.shift.do_shift.eq(1)
                ]
            with m.Case(OpType.SRL):
                m.d.comb += [
                    self.o_mux.eq(self.shift.o),
                    self.ready_next.eq(self.shift.shift_done),
                    self.shift.do_shift.eq(1)
                ]
            with m.Case(OpType.SRA):
                m.d.comb += [
                    self.o_mux.eq(self.shift.o),
                    self.ready_next.eq(self.shift.shift_done),
                    self.shift.do_shift.eq(1)
                ]
            with m.Case(OpType.CMP_EQ):
                m.d.comb += [
                    self.o_mux.eq(self.cmp_equal.o),
                    self.ready_next.eq(1)
                ]
            with m.Case(OpType.CMP_NE):
                m.d.comb += [
                    self.o_mux.eq(self.cmp_not_equal.o),
                    self.ready_next.eq(1)
                ]
            with m.Case(OpType.CMP_LT):
                m.d.comb += [
                    self.o_mux.eq(self.cmp_lt.o),
                    self.ready_next.eq(1)
                ]
            with m.Case(OpType.CMP_LTU):
                m.d.comb += [
                    self.o_mux.eq(self.cmp_ltu.o),
                    self.ready_next.eq(1)
                ]
            with m.Case(OpType.CMP_GE):
                m.d.comb += [
                    self.o_mux.eq(self.cmp_gte.o),
                    self.ready_next.eq(1)
                ]
            with m.Case(OpType.CMP_GEU):
                m.d.comb += [
                    self.o_mux.eq(self.cmp_gteu.o),
                    self.ready_next.eq(1)
                ]
            with m.Case():
                m.d.comb += [
                    self.ready_next.eq(0)
                ]

        m.d.sync += [
            self.o.eq(self.o_mux),
            self.ready.eq(self.ready_next)
        ]
        return m
