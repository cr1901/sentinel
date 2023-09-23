import pytest

from itertools import repeat, chain
from amaranth import Cat, C
from amaranth.sim import Passive

from sentinel.top import Top
from sentinel.decode import OpcodeType


@pytest.mark.module(Top())
@pytest.mark.clks((1.0 / 12e6,))
# @pytest.mark.xfail
def test_top(sim_mod):
    sim, m = sim_mod

    # Reserved for fine-grained testing. Ignores address lines.
    def mem_proc_aux(insns, *, wait_states=repeat(0), irqs=repeat(False)):
        yield Passive()

        for insn, curr_regs, ws, irq in zip(insns, regs, wait_states, irqs):
            # Wait for memory
            while not (yield m.req):
                yield

            # Wait state
            for _ in range(ws):
                yield

            # Send insn to CPU
            yield m.dat_r.eq(insn)
            yield (m.ack.eq(1))
            yield
            yield (m.ack.eq(0))
            yield

    def cpu_proc_aux(regs):
        def check_regs(curr):
            # GP registers
            for r_id in range(32):
                # print((r_id, (yield m.datapath.regfile.mem[r_id]), curr[r_id]))
                assert (yield m.datapath.regfile.mem[r_id]) == (curr[r_id])

            # Program Counter
            # print((yield m.datapath.pc), curr[-1])
            assert (yield m.datapath.pc) == curr[-1]

        for curr in regs:
            # Wait for insn.
            while not (yield m.req):
                yield

            # Check results as new insn begins (i.e. prev results).
            yield from check_regs(curr)

            # Wait for memory to respond.
            while not (yield m.ack):
                yield
            yield

    insns = [
        Cat(C(0b11), OpcodeType.OP_IMM, C(0, 25)),
        Cat(C(0b11), OpcodeType.OP_IMM, C(1, 5), C(0, 3), C(0, 5), C(1, 12)),
        Cat(C(0b11), OpcodeType.OP_IMM, C(1, 5), C(1, 3), C(1, 5), C(3, 12))
    ]

    regs = [
        [0]*32 + [0],
        [0]*32 + [4],
        [0, 1] + [0]*30 + [8],
        [0, 8] + [0]*30 + [0x0c]
    ]

    mem_proc = lambda: (yield from mem_proc_aux(insns, wait_states=chain([1], repeat(0))))
    cpu_proc = lambda: (yield from cpu_proc_aux(regs))

    sim.run(sync_processes=[mem_proc, cpu_proc])
