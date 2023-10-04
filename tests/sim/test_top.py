import pytest

from dataclasses import dataclass
from itertools import repeat, chain
from amaranth.sim import Passive
from bronzebeard.asm import assemble

from sentinel.top import Top


@dataclass
class RV32Regs:
    @classmethod
    def from_top_module(cls, m):
        gpregs = []
        for r_id in range(32):
            gpregs.append((yield m.datapath.regfile.mem[r_id]))

        return cls(*gpregs, PC=(yield m.datapath.pc.dat_r))

    R0: int = 0
    R1: int = 0
    R2: int = 0
    R3: int = 0
    R4: int = 0
    R5: int = 0
    R6: int = 0
    R7: int = 0
    R8: int = 0
    R9: int = 0
    R10: int = 0
    R11: int = 0
    R12: int = 0
    R13: int = 0
    R14: int = 0
    R15: int = 0
    R16: int = 0
    R17: int = 0
    R18: int = 0
    R19: int = 0
    R20: int = 0
    R21: int = 0
    R22: int = 0
    R23: int = 0
    R24: int = 0
    R25: int = 0
    R26: int = 0
    R27: int = 0
    R28: int = 0
    R29: int = 0
    R30: int = 0
    R31: int = 0
    PC: int = 0


@pytest.mark.module(Top())
@pytest.mark.clks((1.0 / 12e6,))
def test_top(sim_mod):
    sim, m = sim_mod

    # Reserved for fine-grained testing. Ignores address lines.
    def mem_proc_aux(insn_mem, *, wait_states=repeat(0), irqs=repeat(False)):
        yield Passive()

        for curr_regs, ws, irq in zip(regs, wait_states, irqs):
            # Wait for memory
            while not (yield m.req):
                yield

            # Wait state
            for _ in range(ws):
                yield

            # Send insn to CPU
            adr = (yield m.adr)
            yield m.dat_r.eq(int.from_bytes(insns[adr:adr+4],
                                            byteorder="little"))
            yield (m.ack.eq(1))
            yield
            yield (m.ack.eq(0))
            yield

    def cpu_proc_aux(regs):
        def check_regs(curr):
            expected_regs = curr
            actual_regs = yield from RV32Regs.from_top_module(m)
            assert expected_regs == actual_regs

        for curr in regs:
            # Wait for insn.
            while not (yield m.req):
                yield

            # Wait for memory to respond.
            while not (yield m.ack):
                yield

            # When ACK is asserted, we should always be going to uinsn
            # "check_int".
            assert (yield m.control.sequencer.adr) == 2 or \
                (yield m.control.sequencer.adr) == 1
            yield

            # Check results as new insn begins (i.e. prev results).
            yield from check_regs(curr)

    insns = assemble("""
        addi x0, x0, 0
        addi x1, x0, 1
        slli x1, x1, 3
        add  x2, x1, x1
    """)

    regs = [
        RV32Regs(),
        RV32Regs(PC=4),
        RV32Regs(R1=1, PC=8),
        RV32Regs(R1=8, PC=0xC),
        RV32Regs(R1=8, R2=16, PC=0x10)
    ]

    def mem_proc():
        yield from mem_proc_aux(insns, wait_states=chain([1], repeat(0)))

    def cpu_proc():
        yield from cpu_proc_aux(regs)

    sim.run(sync_processes=[mem_proc, cpu_proc])
