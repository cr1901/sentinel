import pytest

from sentinel.alu import ALU, OpType


@pytest.mark.module(ALU(32))
@pytest.mark.clks((1.0 / 12e6,))
@pytest.mark.skip(reason="New tests required, not ready.")
def test_alu(sim_mod):
    sim, m = sim_mod

    def out_proc():
        def expect_prev_op(op_type, o=None, *, ready=True, signed=False):
            assert OpType((yield m.op)) == op_type
            yield
            assert (yield m.ready) == ready
            if o:
                if signed:
                    assert (yield m.o.as_signed()) == o
                else:
                    assert (yield m.o) == o

        def expect_delayed_curr_op(num_cycles, op_type, o=None, *, ready=True,
                                   signed=False):
            # From previous op
            assert OpType((yield m.op)) == op_type
            assert (yield m.ready) == ready

            # Last delay will be provided by expect_prev_op.
            for _ in range(num_cycles):
                yield
                assert not (yield m.ready)

            yield from expect_prev_op(op_type, o, ready=True, signed=signed)
            yield   # Multicycle ops aren't pipelined; need extra cycle
            # to send new op.

        # Start conditions
        assert OpType((yield m.op)) == OpType.NOP
        assert not (yield m.ready)
        yield from expect_prev_op(OpType.NOP, 0, ready=False)

        yield from expect_prev_op(OpType.ADD, 254)

        yield from expect_prev_op(OpType.SUB, 256)

        yield from expect_prev_op(OpType.AND, 255)

        yield from expect_prev_op(OpType.NOP, ready=False)

        yield from expect_prev_op(OpType.OR, -1, signed=True)

        yield from expect_prev_op(OpType.XOR, 0xffffff00)

        yield from expect_prev_op(OpType.NOP, ready=False)
        yield from expect_delayed_curr_op(4, OpType.SLL, (255 << 3),
                                          ready=False)

        yield from expect_prev_op(OpType.NOP, ready=False)
        yield from expect_delayed_curr_op(4, OpType.SRL, (255 >> 3),
                                          ready=False)

        yield from expect_prev_op(OpType.NOP, ready=False)
        yield from expect_delayed_curr_op(4, OpType.SRA, -0x10000000,
                                          signed=True, ready=False)

        yield from expect_prev_op(OpType.CMP_EQ, 0)

        yield from expect_prev_op(OpType.CMP_NE, 1)

        yield from expect_prev_op(OpType.CMP_LT, 1)

        yield from expect_prev_op(OpType.CMP_LTU, 0)

        yield from expect_prev_op(OpType.CMP_GE, 0)

        yield from expect_prev_op(OpType.CMP_GEU, 1)

        yield from expect_prev_op(OpType.NOP, ready=False)

    def in_proc():
        def start_op(op_type, a=None, b=None):
            yield m.op.eq(op_type)
            if a:
                yield m.a.eq(a)
            if b:
                yield m.b.eq(b)
            yield

        def delay_until_ready():
            # Unknown if we will be ready or not.
            # assert (yield m.ready)

            yield
            # assert not (yield m.ready)

            while not (yield m.ready):
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

    sim.run(sync_processes=[in_proc, out_proc])
