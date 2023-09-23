import enum

from amaranth import *

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


class Logical(Elaboratable):
    def __init__(self, width):
        self.a   = Signal(width)
        self.b   = Signal(width)
        self.o   = Signal(width)
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
        self.a   = Signal(width)
        self.b   = Signal(width)
        self.o   = Signal(width)
        self.do_shift = Signal()
        self.shift_done = Signal()
        self.op = Signal(OpType)

        self.cnt = Signal(5)
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


class ALU(Elaboratable):
    # Assumes: op is held steady for duration of op.
    def __init__(self, width):
        self.op  = Signal(OpType, reset=OpType.NOP)
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

        for submod in [self.add, self.sub, self.logical, self.shift, self.cmp_equal,
            self.cmp_not_equal, self.cmp_lt, self.cmp_ltu, self.cmp_gte,
            self.cmp_gteu]:
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

    def ports(self):
        return [self.op, self.a, self.b, self.o, self.ready]

    def sim_hooks(self, sim):
        def out_proc():
            def expect_prev_op(op_type, o=None, *, ready=True, signed=False):
                assert OpType((yield self.op)) == op_type
                yield
                assert (yield self.ready) == ready
                if o:
                    if signed:
                        assert (yield self.o.as_signed()) == o
                    else:
                        assert (yield self.o) == o

            def expect_delayed_curr_op(num_cycles, op_type, o=None, *, ready=True, signed=False):
                # From previous op
                assert OpType((yield self.op)) == op_type
                assert (yield self.ready) == ready

                # Last delay will be provided by expect_prev_op.
                for _ in range(num_cycles):
                    yield
                    assert not (yield self.ready)

                yield from expect_prev_op(op_type, o, ready=True, signed=signed)
                yield # Multicycle ops aren't pipelined; need extra cycle
                      # to send new op.


            # Start conditions
            assert OpType((yield self.op)) == OpType.NOP
            assert not (yield self.ready)
            yield from expect_prev_op(OpType.NOP, 0, ready=False)

            yield from expect_prev_op(OpType.ADD, 254)

            yield from expect_prev_op(OpType.SUB, 256)

            yield from expect_prev_op(OpType.AND, 255)

            yield from expect_prev_op(OpType.NOP, ready=False)

            yield from expect_prev_op(OpType.OR, -1, signed=True)

            yield from expect_prev_op(OpType.XOR, 0xffffff00)

            yield from expect_prev_op(OpType.NOP, ready=False)
            yield from expect_delayed_curr_op(4, OpType.SLL, (255 << 3), ready=False)

            yield from expect_prev_op(OpType.NOP, ready=False)
            yield from expect_delayed_curr_op(4, OpType.SRL, (255 >> 3), ready=False)

            yield from expect_prev_op(OpType.NOP, ready=False)
            yield from expect_delayed_curr_op(4, OpType.SRA, -0x10000000, signed=True, ready=False)

            yield from expect_prev_op(OpType.CMP_EQ, 0)

            yield from expect_prev_op(OpType.CMP_NE, 1)

            yield from expect_prev_op(OpType.CMP_LT, 1)

            yield from expect_prev_op(OpType.CMP_LTU, 0)

            yield from expect_prev_op(OpType.CMP_GE, 0)

            yield from expect_prev_op(OpType.CMP_GEU, 1)

            yield from expect_prev_op(OpType.NOP, ready=False)


        def in_proc():
            def start_op(op_type, a=None, b=None):
                yield self.op.eq(op_type)
                if a:
                    yield self.a.eq(a)
                if b:
                    yield self.b.eq(b)
                yield

            def delay_until_ready():
                # Unknown if we will be ready or not.
                # assert (yield self.ready)

                yield
                # assert not (yield self.ready)

                while not (yield self.ready):
                    yield

            yield from start_op(OpType.ADD, 255, -1)

            # The ALU can be pipelined- starting a new op before the old
            # is ready, but we should wait until ready asserts in the actual
            # core (1 cycle latency from rdy assert to a new op).
            #
            # FIXME: 1-cycle op ready is meaningless, since results will be
            # overwritten on next cycle if inputs change. Only if inputs are
            # kept constant are outputs preserved.
            # Multicycle ops hold their results if inputs besides OpType
            # changes. The ALU can't tell the difference between "previous
            # results still needed" and "the same computation is occurring
            # twice in a row". The distinction matters for the shifting ops,
            # which have state/are multicycle (holding previous results is
            # easier :)).
            yield from start_op(OpType.SUB)

            yield from start_op(OpType.AND)

            yield from start_op(OpType.NOP)

            yield from start_op(OpType.OR)

            yield from start_op(OpType.XOR)

            # Shifts must always begin with a non-shift OpType to indicate the
            # difference between a previous shift op and new shift op.
            yield from start_op(OpType.NOP)
            yield from start_op(OpType.SLL, b=3)
            yield from delay_until_ready()

            yield from start_op(OpType.NOP)
            yield from start_op(OpType.SRL)
            yield from delay_until_ready()

            yield from start_op(OpType.NOP)
            yield from start_op(OpType.SRA, a=0x80000000)
            yield from delay_until_ready()

            yield from start_op(OpType.CMP_EQ, a=0, b=1)

            yield from start_op(OpType.CMP_NE)

            yield from start_op(OpType.CMP_LT, a=0x80000000, b=0x7fffffff)

            yield from start_op(OpType.CMP_LTU)

            yield from start_op(OpType.CMP_GE)

            yield from start_op(OpType.CMP_GEU)

            yield from start_op(OpType.NOP)

            # yield from start_op(OpType.SRA, a=0x80000000, b = 5)
            # yield from delay_until_ready()
            #
            # yield from start_op(OpType.SRA, a=0x80000000, b=1)
            # yield from delay_until_ready()

        sim.add_sync_process(in_proc)
        sim.add_sync_process(out_proc)
