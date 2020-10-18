import enum

from nmigen import *

class Unit(Elaboratable):
    def __init__(self, width, op):
        self.a   = Signal(width)
        self.b   = Signal(width)
        self.o   = Signal(width)
        self.op = op

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.o.eq(self.op(self.a, self.b))
        return m


class Shifter(Elaboratable):
    def __init__(self, width, op):
        self.a   = Signal(width)
        self.b   = Signal(width)
        self.o   = Signal(width)
        self.do_shift = Signal()
        self.shift_done = Signal()
        self.op = op

        self.cnt = Signal.like(self.b)
        self.do_shift_rose = Signal()
        self.do_shift_prev = Signal()

    def elaborate(self, platform):
        m = Module()

        m.d.sync += self.do_shift_prev.eq(self.do_shift)
        m.d.comb += self.do_shift_rose.eq(~(self.do_shift_prev) & self.do_shift)

        with m.If(self.do_shift):
            with m.If(self.do_shift_rose):
                m.d.sync += [
                    self.cnt.eq(self.b),
                    self.o.eq(self.a)
                ]
            with m.Else():
                with m.If(self.cnt > 0):
                    m.d.sync += [
                        self.o.eq(self.op(self.o)),
                        self.cnt.eq(self.cnt - 1)
                    ]
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


class ShiftLeft(Shifter):
    def __init__(self, width):
        super().__init__(width, lambda s: s.shift_left(1))


class LogicalShiftRight(Shifter):
    def __init__(self, width):
        super().__init__(width, lambda s: s >> 1)


class ArithmeticShiftRight(Shifter):
    def __init__(self, width):
        super().__init__(width, lambda s: s.as_signed() >> 1)


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


class ALU(Elaboratable):
    # Assumes: op is held steady for duration of op.
    def __init__(self, width):
        self.op  = Signal(OpType)
        self.ready = Signal()
        self.a   = Signal(width)
        self.b   = Signal(width)
        self.o   = Signal(width)

        ###

        # Unregistered ready.
        self.ready_next = Signal()
        self.o_mux = Signal(width)

        self.add = Adder(width)
        self.sub = Subtractor(width)
        self.bitand = AND(width)
        self.bitor = OR(width)
        self.bitxor = XOR(width)
        self.sl = ShiftLeft(width)
        self.lsl = LogicalShiftRight(width)
        self.asl = ArithmeticShiftRight(width)
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
        m.submodules.bitand = self.bitand
        m.submodules.bitor = self.bitor
        m.submodules.bitxor = self.bitxor
        m.submodules.sl = self.sl
        m.submodules.lsl = self.lsl
        m.submodules.asl = self.asl
        m.submodules.cmp_equal = self.cmp_equal
        m.submodules.cmp_not_equal = self.cmp_not_equal
        m.submodules.cmp_lt = self.cmp_lt
        m.submodules.cmp_ltu = self.cmp_ltu
        m.submodules.cmp_gte = self.cmp_gte
        m.submodules.cmp_gteu = self.cmp_gteu

        for submod in [self.add, self.sub, self.bitand, self.bitor,
            self.bitxor, self.sl, self.lsl, self.asl, self.cmp_equal,
            self.cmp_not_equal, self.cmp_lt, self.cmp_ltu, self.cmp_gte,
            self.cmp_gteu]:
            m.d.comb += [
                submod.a.eq(self.a),
                submod.b.eq(self.b),
            ]

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
                    self.o_mux.eq(self.bitand.o),
                    self.ready_next.eq(1)
                ]
            with m.Case(OpType.OR):
                m.d.comb += [
                    self.o_mux.eq(self.bitor.o),
                    self.ready_next.eq(1)
                ]
            with m.Case(OpType.XOR):
                m.d.comb += [
                    self.o_mux.eq(self.bitxor.o),
                    self.ready_next.eq(1)
                ]
            with m.Case(OpType.SLL):
                m.d.comb += [
                    self.o_mux.eq(self.sl.o),
                    self.ready_next.eq(self.sl.shift_done),
                    self.sl.do_shift.eq(1)
                ]
            with m.Case(OpType.SRL):
                m.d.comb += [
                    self.o_mux.eq(self.lsl.o),
                    self.ready_next.eq(self.lsl.shift_done),
                    self.lsl.do_shift.eq(1)
                ]
            with m.Case(OpType.SRA):
                m.d.comb += [
                    self.o_mux.eq(self.asl.o),
                    self.ready_next.eq(self.asl.shift_done),
                    self.asl.do_shift.eq(1)
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

        m.d.sync += [
            self.o.eq(self.o_mux),
            self.ready.eq(self.ready_next)
        ]
        return m

    def ports(self):
        return [self.op, self.a, self.b, self.o, self.ready]

    def sim_hooks(self, sim):
        pass
