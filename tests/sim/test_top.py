from dataclasses import astuple, dataclass, field
from pathlib import Path
from typing import Union
from amaranth import Signal
import pytest

from itertools import repeat, chain, islice
from functools import reduce
from amaranth.sim import Passive, Tick
from bronzebeard.asm import assemble
from elftools.elf.elffile import ELFFile


# FIXME: Eventually drop the need for SoC and simulate memory purely with
# a process like in RISCOF tests? This will be pretty invasive.
from examples.attosoc import AttoSoC
from sentinel.top import Top

from conftest import RV32Regs, CSRRegs


def make_cpu_tb(mod, sim_mem, regs, mem, csrs):
    m = mod

    async def cpu_testbench(ctx):
        def check_regs(curr):
            expected_regs = curr
            actual_regs = RV32Regs.from_top_module(m, ctx)
            assert expected_regs == actual_regs

        def check_mem(mem):
            if mem:
                for m_adr, m_dat in mem.items():
                    assert sim_mem[m_adr] == m_dat

        def check_csrs(curr):
            expected_regs = curr
            actual_regs = CSRRegs.from_top_module(m, ctx)
            assert expected_regs == actual_regs

        for curr_r, curr_m, curr_c in zip(regs, mem, csrs):
            # Wait for insn.
            await ctx.tick().until(m.bus.cyc & m.bus.stb & \
                                   m.control.insn_fetch)

            while ctx.get(~m.bus.ack):
                await ctx.tick()
            # Wait for memory to respond.
            # await ctx.tick().until(m.bus.ack)

            # When ACK is asserted, we should always be going to uinsn
            # "check_int".
            # TODO: I don't think "2" (ucode reset vector) should be possible.
            # But I don't remember what past-me was thinking. Do some research.
            assert ctx.get(m.control.sequencer.adr) == 2 or \
                ctx.get(m.control.sequencer.adr) == 1
            await ctx.tick()

            # Check results as new insn begins (i.e. prev results).
            check_regs(curr_r)
            check_mem(curr_m)
            check_csrs(curr_c)

    return cpu_testbench


@dataclass
class MemoryArgs:
    start: int = 0
    size: int = 400
    init: Union[str, bytes, bytearray, list[int]] = field(default_factory=list)


class Memory(list):
    def __init__(self, start, size):
        super().__init__([0] * size)
        self.range = range(start, start + size)


@pytest.fixture
def memory(request):
    (start, size, source_or_list) = astuple(request.param)
    mem = Memory(start, size)

    if isinstance(source_or_list, str):
        insns = assemble(source_or_list)
        for adr in range(0, len(insns) // 4):
            mem[adr] = int.from_bytes(insns[4 * adr:4 * adr + 4],
                                      byteorder="little")
    elif isinstance(source_or_list, (bytes, bytearray)):
        for adr in range(0, len(source_or_list) // 4):
            mem[adr] = int.from_bytes(source_or_list[4 * adr:4 * adr + 4],
                                      byteorder="little")
    else:
        for adr in range(0, len(source_or_list)):
            mem[adr] = source_or_list[adr]

    return mem


@pytest.fixture
def memory_process(mod, memory):
    m = mod

    async def memory_process(ctx):
        stims = [m.bus.cyc & m.bus.stb, m.bus.adr, m.bus.dat_w, m.bus.we,
                 m.bus.sel]

        while True:
            clk_hit, rst_active, wb_cyc, addr, dat_w, we, sel = \
                await ctx.tick().sample(*stims)

            if rst_active:
                pass
            elif clk_hit and wb_cyc and addr in memory.range:
                if we:
                    dat_r = memory[addr - memory.range.start]

                    if sel & 0x1:
                        dat_r = (dat_r & 0xffffff00) | (dat_w & 0x000000ff)
                    if sel & 0x2:
                        dat_r = (dat_r & 0xffff00ff) | (dat_w & 0x0000ff00)
                    if sel & 0x4:
                        dat_r = (dat_r & 0xff00ffff) | (dat_w & 0x00ff0000)
                    if sel & 0x8:
                        dat_r = (dat_r & 0x00ffffff) | (dat_w & 0xff000000)

                    memory[addr] = dat_r
                else:
                    # TODO: Some memories will dup byte/half data on the
                    # inactive lines. Worth adding?
                    ctx.set(m.bus.dat_r, memory[addr - memory.range.start])
                ctx.set(m.bus.ack, 1)
                # TODO: Wait states? See bus_proc_aux in previous versions for
                # inspiration.
                await ctx.tick()
                ctx.set(m.bus.ack, 0)

    return memory_process


@dataclass
class SeqArgs:
    program: str
    regs: list[RV32Regs]
    ram: list[Union[dict, None]]
    csrs: list[CSRRegs]


# This test is a handwritten exercise of going through all RV32I insns. If
# this test fails, than surely all other, more thorough tests will fail.
HANDWRITTEN = SeqArgs(
    program="""
        addi x0, x0, 0  # 0
        addi x1, x0, 1
        slli x1, x1, 0
        slli x1, x1, 3
        addi x2, x0, -2047  # 0x10
        add  x2, x1, x2
        slt  x3, x2, x1
        slti x4, x2, (-2046 + 8)
        sltiu x4, x2, 2047  # 0x20
        sltu  x3, x2, x1
        xori x5, x0, -1
        xor  x1, x5, x1
        ori  x6, x0, -1  # 0x30
        or   x1, x1, x6
        andi x1, x1, 1
        and  x2, x0, x2
        sub  x6, x1, x6  # 0x40
        lui  x6, 0x80000
        srai x7, x6, 2
        srli x8, x6, 2
        li x2, 4 + (1024 - 32)  # 0x50
        sll x3, x1, x2
        sra x4, x7, x3
        srl x9, x7, x3
        fence  # 0x60
        auipc x10, -1
        jal jal_dst
        nop
jal_dst:
        sb x1, x2, 513  # 0x70
        lb x11, x1, 513
        lbu x11, x1, 513
        jalr x12, x3, jalr_dst - 16
        nop  # 0x80
jalr_dst:
        beq x0, x13, beq_dst
        nop
beq_dst:
        bne x0, x13, bne_dst
        blt x10, x11, blt_dst  # 0x90
bne_dst:
        nop
blt_dst:
        bltu x10, x11, bltu_dst
        bge x10, x11, bge_dst
bltu_dst:
        bgeu x10, x11, bgeu_dst1  # 0xA0
bge_dst:
        nop
bgeu_dst1:
        bge x0, x13, bgeu_dst2
        nop
bgeu_dst2:
        sh x1, x2, 514  # 0xB0
        sw x1, x4, 516
        lh x13, x1, 518
        lhu x13, x1, 518
        sb x1, x0, 512  # 0xC0
        lw x14, x1, 512
""",

    regs=[
        RV32Regs(),
        RV32Regs(PC=4 >> 2),
        RV32Regs(R1=1, PC=8 >> 2),
        RV32Regs(R1=1, PC=0xC >> 2),
        RV32Regs(R1=8, PC=0x10 >> 2),
        RV32Regs(R2=2**32 - 2047, R1=8, PC=0x14 >> 2),
        RV32Regs(R2=(2**32 - 2047) + 8, R1=8, PC=0x18 >> 2),
        RV32Regs(R3=1, R2=(2**32 - 2047) + 8, R1=8, PC=0x1C >> 2),
        RV32Regs(R4=1, R3=1, R2=(2**32 - 2047) + 8, R1=8, PC=0x20 >> 2),
        RV32Regs(R4=0, R3=1, R2=(2**32 - 2047) + 8, R1=8, PC=0x24 >> 2),
        RV32Regs(R2=(2**32 - 2047) + 8, R1=8, PC=0x28 >> 2),
        RV32Regs(R5=2**32 - 1, R2=(2**32 - 2047) + 8, R1=8, PC=0x2C >> 2),
        RV32Regs(R5=2**32 - 1, R2=(2**32 - 2047) + 8, R1=0xfffffff7,
                 PC=0x30 >> 2),
        RV32Regs(R6=2**32 - 1, R5=2**32 - 1, R2=(2**32 - 2047) + 8,
                 R1=0xfffffff7, PC=0x34 >> 2),
        RV32Regs(R6=2**32 - 1, R5=2**32 - 1, R2=(2**32 - 2047) + 8,
                 R1=2**32 - 1, PC=0x38 >> 2),
        RV32Regs(R6=2**32 - 1, R5=2**32 - 1, R2=(2**32 - 2047) + 8,
                 R1=1, PC=0x3C >> 2),
        RV32Regs(R6=2**32 - 1, R5=2**32 - 1, R1=1, PC=0x40 >> 2),
        RV32Regs(R6=2, R5=2**32 - 1, R1=1, PC=0x44 >> 2),
        RV32Regs(R6=0x80000000, R5=2**32 - 1, R1=1, PC=0x48 >> 2),
        RV32Regs(R7=0xE0000000, R6=0x80000000, R5=2**32 - 1, R1=1,
                 PC=0x4C >> 2),
        RV32Regs(R8=0x20000000, R7=0xE0000000, R6=0x80000000, R5=2**32 - 1,
                 R1=1, PC=0x50 >> 2),
        RV32Regs(R8=0x20000000, R7=0xE0000000, R6=0x80000000, R5=2**32 - 1,
                 R2=0x3E4, R1=1, PC=0x54 >> 2),
        RV32Regs(R8=0x20000000, R7=0xE0000000, R6=0x80000000, R5=2**32 - 1,
                 R3=16, R2=0x3E4, R1=1, PC=0x58 >> 2),
        RV32Regs(R8=0x20000000, R7=0xE0000000, R6=0x80000000, R5=2**32 - 1,
                 R4=0xFFFFE000, R3=16, R2=0x3E4, R1=1, PC=0x5C >> 2),
        RV32Regs(R9=0x0000E000, R8=0x20000000, R7=0xE0000000, R6=0x80000000,
                 R5=2**32 - 1, R4=0xFFFFE000, R3=16, R2=0x3E4, R1=1,
                 PC=0x60 >> 2),
        RV32Regs(R9=0x0000E000, R8=0x20000000, R7=0xE0000000, R6=0x80000000,
                 R5=2**32 - 1, R4=0xFFFFE000, R3=16, R2=0x3E4, R1=1,
                 PC=0x64 >> 2),
        RV32Regs(R10=(2**32 - 4096) + 100, R9=0x0000E000, R8=0x20000000,
                 R7=0xE0000000, R6=0x80000000, R5=2**32 - 1, R4=0xFFFFE000,
                 R3=16, R2=0x3E4, R1=1,
                 PC=0x68 >> 2),
        RV32Regs(R10=(2**32 - 4096) + 100, R9=0x0000E000, R8=0x20000000,
                 R7=0xE0000000, R6=0x80000000, R5=2**32 - 1, R4=0xFFFFE000,
                 R3=16, R2=0x3E4, R1=0x6C,
                 PC=0x70 >> 2),
        RV32Regs(R10=(2**32 - 4096) + 100, R9=0x0000E000, R8=0x20000000,
                 R7=0xE0000000, R6=0x80000000, R5=2**32 - 1, R4=0xFFFFE000,
                 R3=16, R2=0x3E4, R1=0x6C,
                 PC=0x74 >> 2),
        RV32Regs(R11=0xFFFFFFE4, R10=(2**32 - 4096) + 100, R9=0x0000E000,
                 R8=0x20000000, R7=0xE0000000, R6=0x80000000, R5=2**32 - 1,
                 R4=0xFFFFE000, R3=16, R2=0x3E4, R1=0x6C, PC=0x78 >> 2),
        RV32Regs(R11=0xE4, R10=(2**32 - 4096) + 100, R9=0x0000E000,
                 R8=0x20000000, R7=0xE0000000, R6=0x80000000, R5=2**32 - 1,
                 R4=0xFFFFE000, R3=16, R2=0x3E4, R1=0x6C, PC=0x7C >> 2),
        RV32Regs(R12=0x80, R11=0xE4, R10=(2**32 - 4096) + 100, R9=0x0000E000,
                 R8=0x20000000, R7=0xE0000000, R6=0x80000000, R5=2**32 - 1,
                 R4=0xFFFFE000, R3=16, R2=0x3E4, R1=0x6C, PC=0x84 >> 2),
        RV32Regs(R12=0x80, R11=0xE4, R10=(2**32 - 4096) + 100, R9=0x0000E000,
                 R8=0x20000000, R7=0xE0000000, R6=0x80000000, R5=2**32 - 1,
                 R4=0xFFFFE000, R3=16, R2=0x3E4, R1=0x6C, PC=0x8C >> 2),
        RV32Regs(R12=0x80, R11=0xE4, R10=(2**32 - 4096) + 100, R9=0x0000E000,
                 R8=0x20000000, R7=0xE0000000, R6=0x80000000, R5=2**32 - 1,
                 R4=0xFFFFE000, R3=16, R2=0x3E4, R1=0x6C, PC=0x90 >> 2),
        RV32Regs(R12=0x80, R11=0xE4, R10=(2**32 - 4096) + 100, R9=0x0000E000,
                 R8=0x20000000, R7=0xE0000000, R6=0x80000000, R5=2**32 - 1,
                 R4=0xFFFFE000, R3=16, R2=0x3E4, R1=0x6C, PC=0x98 >> 2),
        RV32Regs(R12=0x80, R11=0xE4, R10=(2**32 - 4096) + 100, R9=0x0000E000,
                 R8=0x20000000, R7=0xE0000000, R6=0x80000000, R5=2**32 - 1,
                 R4=0xFFFFE000, R3=16, R2=0x3E4, R1=0x6C, PC=0x9C >> 2),
        RV32Regs(R12=0x80, R11=0xE4, R10=(2**32 - 4096) + 100, R9=0x0000E000,
                 R8=0x20000000, R7=0xE0000000, R6=0x80000000, R5=2**32 - 1,
                 R4=0xFFFFE000, R3=16, R2=0x3E4, R1=0x6C, PC=0xA0 >> 2),
        RV32Regs(R12=0x80, R11=0xE4, R10=(2**32 - 4096) + 100, R9=0x0000E000,
                 R8=0x20000000, R7=0xE0000000, R6=0x80000000, R5=2**32 - 1,
                 R4=0xFFFFE000, R3=16, R2=0x3E4, R1=0x6C, PC=0xA8 >> 2),
        RV32Regs(R12=0x80, R11=0xE4, R10=(2**32 - 4096) + 100, R9=0x0000E000,
                 R8=0x20000000, R7=0xE0000000, R6=0x80000000, R5=2**32 - 1,
                 R4=0xFFFFE000, R3=16, R2=0x3E4, R1=0x6C, PC=0xB0 >> 2),
        RV32Regs(R12=0x80, R11=0xE4, R10=(2**32 - 4096) + 100, R9=0x0000E000,
                 R8=0x20000000, R7=0xE0000000, R6=0x80000000, R5=2**32 - 1,
                 R4=0xFFFFE000, R3=16, R2=0x3E4, R1=0x6C, PC=0xB4 >> 2),
        RV32Regs(R12=0x80, R11=0xE4, R10=(2**32 - 4096) + 100, R9=0x0000E000,
                 R8=0x20000000, R7=0xE0000000, R6=0x80000000, R5=2**32 - 1,
                 R4=0xFFFFE000, R3=16, R2=0x3E4, R1=0x6C, PC=0xB8 >> 2),
        RV32Regs(R13=0xFFFFFFFF, R12=0x80, R11=0xE4, R10=(2**32 - 4096) + 100,
                 R9=0x0000E000, R8=0x20000000, R7=0xE0000000, R6=0x80000000,
                 R5=2**32 - 1, R4=0xFFFFE000, R3=16, R2=0x3E4, R1=0x6C,
                 PC=0xBC >> 2),
        RV32Regs(R13=0x0000FFFF, R12=0x80, R11=0xE4, R10=(2**32 - 4096) + 100,
                 R9=0x0000E000, R8=0x20000000, R7=0xE0000000, R6=0x80000000,
                 R5=2**32 - 1, R4=0xFFFFE000, R3=16, R2=0x3E4, R1=0x6C,
                 PC=0xC0 >> 2),
        RV32Regs(R13=0x0000FFFF, R12=0x80, R11=0xE4, R10=(2**32 - 4096) + 100,
                 R9=0x0000E000, R8=0x20000000, R7=0xE0000000, R6=0x80000000,
                 R5=2**32 - 1, R4=0xFFFFE000, R3=16, R2=0x3E4, R1=0x6C,
                 PC=0xC4 >> 2),
        RV32Regs(R14=0x03e4e400, R13=0x0000FFFF, R12=0x80, R11=0xE4,
                 R10=(2**32 - 4096) + 100, R9=0x0000E000, R8=0x20000000,
                 R7=0xE0000000, R6=0x80000000, R5=2**32 - 1, R4=0xFFFFE000,
                 R3=16, R2=0x3E4, R1=0x6C, PC=0xC8 >> 2),
    ],

    ram=[
        None,  # 0x0
        None, None, None, None, None, None, None, None,  # 0x20
        None, None, None, None, None, None, None, None,  # 0x40
        None, None, None, None, None, None, None, None,  # 0x60
        None, None, None,  # 0x70
        {0x26C >> 2: 0xe4 << 8}, {0x26C >> 2: 0xe4 << 8},
        {0x26C >> 2: 0xe4 << 8}, {0x26C >> 2: 0xe4 << 8},  # 0x84

        {0x26C >> 2: 0xe4 << 8}, {0x26C >> 2: 0xe4 << 8},  # 0x90

        {0x26C >> 2: 0xe4 << 8}, {0x26C >> 2: 0xe4 << 8},
        {0x26C >> 2: 0xe4 << 8},  # 0xA0

        {0x26C >> 2: 0xe4 << 8}, {0x26C >> 2: 0xe4 << 8},  # 0xB0

        {0x26C >> 2: 0x03e4e4 << 8},
        {0x26C >> 2: 0x03e4e4 << 8, 0x270 >> 2: 0xFFFFE000},
        {0x26C >> 2: 0x03e4e4 << 8, 0x270 >> 2: 0xFFFFE000},
        {0x26C >> 2: 0x03e4e4 << 8, 0x270 >> 2: 0xFFFFE000},  # 0xC0

        {0x26C >> 2: 0x03e4e400, 0x270 >> 2: 0xFFFFE000},
        {0x26C >> 2: 0x03e4e400, 0x270 >> 2: 0xFFFFE000},
    ],

    csrs=[CSRRegs()] * 50
)

CSR_R0 = SeqArgs(
    program="""
        addi x1, x0, 1  # 0
        csrrs x1, x0, -0xEF  # mvendorid
""",

    regs=[
        RV32Regs(),
        RV32Regs(R1=1, PC=4 >> 2),
        RV32Regs(R1=0, PC=8 >> 2),
    ],

    ram=[
        None,  # 0x0
        None,
        None
    ],

    csrs=[CSRRegs()] * 3
)


CSRW = SeqArgs(
    program="""
        csrrwi x0, 31, 0x340   # mscratch  # 0x00
        csrrwi x1, 17, 0x340   # mscratch
        csrrci x2,  1, 0x340   # mscratch
        csrrwi x0,  8, 0x300   # mstatus
        csrrwi x3,  9, 0x300   # mstatus  # 0x10
        csrrsi x4,  1, 0x340   # mscratch
        csrrsi x0,  2, 0x340   # mscratch
        csrrci x0,  2, 0x340   # mscratch
        csrrci x5,  0, 0x340   # mscratch  # 0x20
        csrrsi x1,  0, 0x300   # mstatus
        csrrw x0,  x3, 0x340   # mscratch
        csrrw x2,  x4, 0x340   # mscratch
        xori  x2, x0, -1  # 0x30
        csrrw x0, x2, 0x340  # mscratch
        csrrc x4, x4, 0x340  # mscratch
        csrrc x2, x0, 0x340  # mscratch
        csrrs x2, x0, 0x300   # mstatus  # 0x40
        slli  x2, x2, 1
        csrrs x3, x2, 0x340 # mscratch
""",

    regs=[
        RV32Regs(),
        RV32Regs(PC=4 >> 2),
        RV32Regs(R1=31, PC=8 >> 2),
        RV32Regs(R2=17, R1=31, PC=0xC >> 2),
        RV32Regs(R2=17, R1=31, PC=0x10 >> 2),
        RV32Regs(R3=0b11000_0000_1000, R2=17, R1=31, PC=0x14 >> 2),
        RV32Regs(R4=16, R3=0b11000_0000_1000, R2=17, R1=31, PC=0x18 >> 2),
        RV32Regs(R4=16, R3=0b11000_0000_1000, R2=17, R1=31, PC=0x1C >> 2),
        RV32Regs(R4=16, R3=0b11000_0000_1000, R2=17, R1=31, PC=0x20 >> 2),
        RV32Regs(R5=17, R4=16, R3=0b11000_0000_1000, R2=17, R1=31,
                 PC=0x24 >> 2),
        RV32Regs(R5=17, R4=16, R3=0b11000_0000_1000, R2=17,
                 R1=0b11000_0000_1000, PC=0x28 >> 2),
        RV32Regs(R5=17, R4=16, R3=0b11000_0000_1000, R2=17,
                 R1=0b11000_0000_1000, PC=0x2C >> 2),
        RV32Regs(R5=17, R4=16, R3=0b11000_0000_1000, R2=0b11000_0000_1000,
                 R1=0b11000_0000_1000, PC=0x30 >> 2),
        RV32Regs(R5=17, R4=16, R3=0b11000_0000_1000, R2=0xffffffff,
                 R1=0b11000_0000_1000, PC=0x34 >> 2),
        RV32Regs(R5=17, R4=16, R3=0b11000_0000_1000, R2=0xffffffff,
                 R1=0b11000_0000_1000, PC=0x38 >> 2),
        RV32Regs(R5=17, R4=0xffffffff, R3=0b11000_0000_1000, R2=0xffffffff,
                 R1=0b11000_0000_1000, PC=0x3C >> 2),
        RV32Regs(R5=17, R4=0xffffffff, R3=0b11000_0000_1000, R2=0xffffffef,
                 R1=0b11000_0000_1000, PC=0x40 >> 2),
        RV32Regs(R5=17, R4=0xffffffff, R3=0b11000_0000_1000,
                 R2=0b11000_0000_1000, R1=0b11000_0000_1000, PC=0x44 >> 2),
        RV32Regs(R5=17, R4=0xffffffff, R3=0b11000_0000_1000,
                 R2=0b11_0000_0001_0000,
                 R1=0b11000_0000_1000, PC=0x48 >> 2),
        RV32Regs(R5=17, R4=0xffffffff, R3=0xffffffef, R2=0b11_0000_0001_0000,
                 R1=0b11000_0000_1000, PC=0x4C >> 2),
    ],

    ram=[None] * 20,

    csrs=[
        CSRRegs(),  # 0x0
        CSRRegs(MSCRATCH=31),
        CSRRegs(MSCRATCH=17),
        CSRRegs(MSCRATCH=16),
        CSRRegs(MSCRATCH=16, MSTATUS=0b11000_0000_1000),  # 0x10
        CSRRegs(MSCRATCH=16, MSTATUS=0b11000_0000_1000),
        CSRRegs(MSCRATCH=17, MSTATUS=0b11000_0000_1000),
        CSRRegs(MSCRATCH=19, MSTATUS=0b11000_0000_1000),
        CSRRegs(MSCRATCH=17, MSTATUS=0b11000_0000_1000),  # 0x20
        CSRRegs(MSCRATCH=17, MSTATUS=0b11000_0000_1000),
        CSRRegs(MSCRATCH=17, MSTATUS=0b11000_0000_1000),
        CSRRegs(MSCRATCH=0b11000_0000_1000, MSTATUS=0b11000_0000_1000),
        CSRRegs(MSCRATCH=16, MSTATUS=0b11000_0000_1000),  # 0x30
        CSRRegs(MSCRATCH=16, MSTATUS=0b11000_0000_1000),
        CSRRegs(MSCRATCH=0xffffffff, MSTATUS=0b11000_0000_1000),
        CSRRegs(MSCRATCH=0xffffffef, MSTATUS=0b11000_0000_1000),
        CSRRegs(MSCRATCH=0xffffffef, MSTATUS=0b11000_0000_1000),  # 0x40
        CSRRegs(MSCRATCH=0xffffffef, MSTATUS=0b11000_0000_1000),
        CSRRegs(MSCRATCH=0xffffffef, MSTATUS=0b11000_0000_1000),
        CSRRegs(MSCRATCH=0xffffffff, MSTATUS=0b11000_0000_1000),
    ]
)


EXCEPTION = SeqArgs(
    # ECALL sets xEPC to the ECALL insn, not the following one!
    program="""
         csrrwi x0, 16, 0x305  # mtvec
         ecall
         nop
         nop
handler:
         dw 0b00110000001000000000000001110011  # mret
""",

    regs=[
        RV32Regs(),
        RV32Regs(PC=4 >> 2),
        RV32Regs(PC=0x10 >> 2),
        RV32Regs(PC=4 >> 2),
    ],

    ram=[None] * 4,

    csrs=[
        CSRRegs(),  # 0x0
        CSRRegs(MTVEC=0x10),
        CSRRegs(MTVEC=0x10, MCAUSE=11, MEPC=0x4),
        CSRRegs(MSTATUS=0b11000_1000_0000, MTVEC=0x10, MCAUSE=11, MEPC=0x4),
    ]
)


@pytest.mark.parametrize("mod,clks,memory,program_state",
                         [
                             pytest.param(
                                 Top(), 1.0 / 12e6,
                                 MemoryArgs(init=HANDWRITTEN.program),
                                 HANDWRITTEN, id="handwritten"),
                             pytest.param(
                                 Top(), 1.0 / 12e6,
                                 MemoryArgs(init=CSR_R0.program),
                                 CSR_R0, id="csr_r0"),
                             pytest.param(
                                 Top(), 1.0 / 12e6,
                                 MemoryArgs(init=CSRW.program),
                                 CSRW, id="csrw"),
                             pytest.param(
                                 Top(), 1.0 / 12e6,
                                 MemoryArgs(init=EXCEPTION.program),
                                 EXCEPTION, id="exception"),
                         ], indirect=["memory"])
def test_seq(sim, mod, memory, ucode_panic, memory_process, program_state):
    sim.run(testbenches=[make_cpu_tb(mod, memory, program_state.regs,
                                     program_state.ram, program_state.csrs)],
            processes=[ucode_panic, memory_process])


# This is a prime-counting program. It is provided with/disassembled from
# nextpnr-ice40's examples (https://github.com/YosysHQ/nextpnr/tree/master/ice40/smoketest/attosoc),  # noqa: E501
# but I don't know about its origins otherwise.
# I have modified a hardcoded delay from 360000 to 2, as well as stopping
# after 17 for simulation speed.
PRIMES = """
        li      s0,2
        lui     s1,0x2000  # IO port at 0x2000000
        li      s3,18  #  Originally 256
outer:
        addi    s0,s0,1
        blt     s0,s3,noinit
        li      s0,2
noinit:
        li      s2,2
next_int:
        bge     s2,s0,write_io
        mv      a0,s0
        mv      a1,s2
        call    prime?
        beqz    a0,not_prime
        addi    s2,s2,1
        j       next_int
write_io:
        sw      s0,0(s1)
        call    delay
not_prime:
        j       outer
prime?:
        li      t0,1
submore:
        sub     a0,a0,a1
        bge     a0,t0,submore
        ret
delay:
        li      t0,2  # Originally 360000
countdown:
        addi    t0,t0,-1
        bnez    t0,countdown
        ret
"""


@pytest.mark.parametrize("mod,clks,memory",
                         [pytest.param(Top(), 1.0 / 12e6,
                                       MemoryArgs(init=PRIMES),
                                       id="default")],
                         indirect=["memory"])
def test_primes(sim, mod, memory_process, ucode_panic):
    m = mod

    restart_timeout = Signal(1)

    async def timeout_process(ctx):
        while True:
            for _ in range(65536):
                *_, restart_ack = await ctx.tick().sample(restart_timeout)
                if restart_ack:
                    break
            else:
                raise AssertionError("CPU (but not microcode) probably stuck "
                                     "in infinite loop")

    async def io_tb(ctx):
        primes = [3, 5, 7, 11, 13, 17, 2]
        # 19, 23, 29, 31, 37, 41, 43, 47, 53,
        # 59, 61, 67, 71, 73, 79, 83, 89, 97, 101, 103, 107, 109,
        # 113, 127, 131, 137, 139, 149, 151, 157, 163, 167, 173, 179,
        # 181, 191, 193, 197, 199, 211, 223, 227, 229, 233, 239, 241,
        # 251, 2]

        for p in primes:
            *_, dat_w = await ctx.tick().sample(m.bus.dat_w).until(
                (m.bus.adr == 0x2000000 >> 2) & m.bus.cyc & \
                m.bus.stb)

            ctx.set(m.bus.ack, 1)
            assert dat_w == p
            ctx.set(restart_timeout, 1)

            await ctx.tick()
            ctx.set(m.bus.ack, 0)
            ctx.set(restart_timeout, 0)

    sim.run(testbenches=[io_tb], processes=[ucode_panic, memory_process,
                                            timeout_process])
