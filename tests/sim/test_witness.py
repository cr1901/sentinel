import pytest
from amaranth import Elaboratable, Module, Signal
from sentinel.top import Top

from conftest import RV32Regs, CSRRegs


# Semi-autogenerated (script not provided b/c it's a one-off) from a yosys
# witness file for a failed reg_ch0 test at around f3d3e315b7.
#
# While looking at why the trace failed, which was a bug in my formal harness,
# I found _another_ bug that is a legitimate bug in Sentinel.
# Specifically, none of the sim tests before this altered dat_r in the middle
# of an instruction, which seems to hide a few bugs. This particular set
# of dat_r and acks is _intended_ to perform the following insns:
#
# csrrc x8, mstatus, x4
# andi x1, x8, 40
#
# which writes to the nonexistant CSR with address 0b0001.
#
# The witness file is provided for reference; eventually the goal is to
# autogenerate TBs from witness files (and allow the TBs to evolve
# independent of the witness files as Sentinel changes).
@pytest.fixture
def csrrc_bad_rd_process(mod):
    m = mod

    async def proc(ctx):
        await ctx.tick()

        ctx.set(m.bus.ack, 0b0)
        ctx.set(m.bus.dat_r, 0b0)
        await ctx.tick()
        ctx.set(m.bus.ack, 0b0)
        ctx.set(m.bus.dat_r, 0b110000000011111111111111111111)
        await ctx.tick()
        ctx.set(m.bus.ack, 0b0)
        ctx.set(m.bus.dat_r, 0b110000000011111111111111111111)
        await ctx.tick()
        ctx.set(m.bus.ack, 0b0)
        ctx.set(m.bus.dat_r, 0b110000000111111111111111111111)
        await ctx.tick()
        ctx.set(m.bus.ack, 0b0)
        ctx.set(m.bus.dat_r, 0b110000000111111111111111111111)
        await ctx.tick()
        ctx.set(m.bus.ack, 0b0)
        ctx.set(m.bus.dat_r, 0b11110100010000100111111111111111)
        await ctx.tick()
        ctx.set(m.bus.ack, 0b1)
        ctx.set(m.bus.dat_r, 0b110000000000100011010001110011)
        await ctx.tick()
        ctx.set(m.bus.ack, 0b0)
        ctx.set(m.bus.dat_r, 0b10000001110011)
        await ctx.tick()
        ctx.set(m.bus.ack, 0b1)
        ctx.set(m.bus.dat_r, 0b110010000100010010001001110011)
        await ctx.tick()
        ctx.set(m.bus.ack, 0b0)
        ctx.set(m.bus.dat_r, 0b110000100000010100000000010011)
        await ctx.tick()
        ctx.set(m.bus.ack, 0b0)
        ctx.set(m.bus.dat_r, 0b100100011011010100110011)
        await ctx.tick()
        ctx.set(m.bus.ack, 0b0)
        ctx.set(m.bus.dat_r, 0b110100001011000000000110100011)
        await ctx.tick()
        ctx.set(m.bus.ack, 0b0)
        ctx.set(m.bus.dat_r, 0b110100000010011010000101110011)
        await ctx.tick()
        ctx.set(m.bus.ack, 0b0)
        ctx.set(m.bus.dat_r, 0b10010000000011)
        await ctx.tick()
        ctx.set(m.bus.ack, 0b0)
        ctx.set(m.bus.dat_r, 0b110000001000000000000001101111)
        await ctx.tick()
        ctx.set(m.bus.ack, 0b0)
        ctx.set(m.bus.dat_r, 0b100001110000111110011)
        await ctx.tick()

        assert ctx.get(m.datapath.csr.adr) == 0b0000

        ctx.set(m.bus.ack, 0b0)
        ctx.set(m.bus.dat_r, 0b1000100001000000101001101100011)
        await ctx.tick()
        ctx.set(m.bus.ack, 0b1)
        ctx.set(m.bus.dat_r, 0b10100001000111000010010011)
        await ctx.tick()
        ctx.set(m.bus.ack, 0b0)
        ctx.set(m.bus.dat_r, 0b10110000001000001001011111101111)
        await ctx.tick()
        ctx.set(m.bus.ack, 0b1)
        ctx.set(m.bus.dat_r, 0b100001001101000010010100)
        await ctx.tick()
        ctx.set(m.bus.ack, 0b0)
        ctx.set(m.bus.dat_r, 0b110000010000001000000100001111)
        await ctx.tick()
        ctx.set(m.bus.ack, 0b0)
        ctx.set(m.bus.dat_r, 0b11001000001000010110111)
        await ctx.tick()
        ctx.set(m.bus.ack, 0b0)
        ctx.set(m.bus.dat_r, 0b11111110110110000011000010011100)
        await ctx.tick()
        ctx.set(m.bus.ack, 0b0)
        ctx.set(m.bus.dat_r, 0b11011101010100101000111110010011)
        await ctx.tick()
        ctx.set(m.bus.ack, 0b0)
        ctx.set(m.bus.dat_r, 0b10000010100111000000001101101)
        await ctx.tick()
        ctx.set(m.bus.ack, 0b1)
        ctx.set(m.bus.dat_r, 0b0)
        await ctx.tick()

        expected_regs = RV32Regs(R8=0x00001800, PC=8 >> 2)
        actual_regs = RV32Regs.from_top_module(m, ctx)
        assert expected_regs == actual_regs

        expected_regs = CSRRegs()
        actual_regs = CSRRegs.from_top_module(m, ctx)
        assert expected_regs == actual_regs

    return proc


# class WitnessTop(Elaboratable):
#     def __init__(self):
#         self.cpu = Top()

#     def elaborate(self, plat):
#         m = Module()
#         m.submodules.cpu = self.cpu

#         dummy = Signal()
#         m.d.sync += dummy.eq(dummy)

#         return m


@pytest.mark.parametrize("mod,clks", [(Top(), 1.0 / 12e6)])
def test_csrrc_bad_rd(sim, csrrc_bad_rd_process, ucode_panic):
    sim.run(testbenches=[csrrc_bad_rd_process],
            processes=[ucode_panic])
