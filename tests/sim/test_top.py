import pytest

from dataclasses import dataclass
from itertools import repeat, chain
from amaranth import Module, Memory, Elaboratable, Signal
from amaranth.lib.wiring import Component, Signature, In, Out, connect
from amaranth.sim import Passive
from amaranth_soc import wishbone
from bronzebeard.asm import assemble

from sentinel.top import Top


@dataclass
class RV32Regs:
    @classmethod
    def from_top_module(cls, m):
        gpregs = []
        for r_id in range(32):
            gpregs.append((yield m.cpu.datapath.regfile.mem[r_id]))

        return cls(*gpregs, PC=(yield m.cpu.datapath.pc.dat_r))

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


class WBMemory(Component):
    bus: In(wishbone.Signature(addr_width=30, data_width=32, granularity=8))
    ctrl: Out(Signature({
        "force_ws": Out(1)  # noqa: F821
    }))

    def __init__(self):
        super().__init__()
        self.mem = Memory(width=32, depth=0x400)

    @property
    def init_mem(self):
        return self.mem.init

    @init_mem.setter
    def init_mem(self, mem):
        self.mem.init = mem

    def elaborate(self, plat):
        m = Module()
        m.submodules.rdport = rdport = self.mem.read_port(transparent=True)
        m.submodules.wrport = wrport = self.mem.write_port(granularity=8)

        m.d.comb += [
            rdport.addr.eq(self.bus.adr),
            wrport.addr.eq(self.bus.adr),
            self.bus.dat_r.eq(rdport.data),
            wrport.data.eq(self.bus.dat_w),
            rdport.en.eq(self.bus.stb & self.bus.cyc & ~self.bus.we),
        ]

        with m.If(self.bus.stb & self.bus.cyc & self.bus.we):
            m.d.comb += wrport.en.eq(self.bus.sel)

        with m.If(self.bus.stb & self.bus.cyc & ~self.bus.ack &
                  ~self.ctrl.force_ws):
            m.d.sync += self.bus.ack.eq(1)
        with m.Else():
            m.d.sync += self.bus.ack.eq(0)

        return m


class CPUWithMem(Elaboratable):
    def __init__(self):
        self.cpu = Top()
        self.mem = WBMemory()

    def elaborate(self, plat):
        m = Module()

        dummy = Signal()

        m.submodules.cpu = self.cpu
        m.submodules.mem = self.mem

        connect(m, self.cpu.bus, self.mem.bus)

        # Make sure clk/rst show up in top-level sim module.
        m.d.sync += dummy.eq(dummy)

        return m


@pytest.fixture
def ucode_panic(sim_mod):
    sim, m = sim_mod

    def ucode_panic():
        yield Passive()

        addr = 0
        prev_addr = 0
        count = 0
        while True:
            yield

            if (yield m.cpu.control.ucoderom.addr == 248):
                raise AssertionError("microcode panic (not implemented)")

            prev_addr = addr
            addr = (yield m.cpu.control.ucoderom.addr)
            if prev_addr == addr:
                count += 1
                if count > 100:
                    raise AssertionError("microcode probably stuck in "
                                         "infinite loop")
            else:
                count = 0

    return ucode_panic


# This test is a handwritten exercise of going through all RV32I insns. If
# this test fails, than surely all other, more thorough tests will fail.
@pytest.mark.module(CPUWithMem())
@pytest.mark.clks((1.0 / 12e6,))
def test_seq(sim_mod, ucode_panic):
    sim, m = sim_mod

    def bus_proc_aux(wait_states=repeat(0), irqs=repeat(False)):
        yield Passive()

        for ws, irq in zip(wait_states, irqs):
            # Wait for memory
            while not ((yield m.cpu.bus.cyc) and (yield m.cpu.bus.stb) and
                       (yield m.cpu.control.insn_fetch)):
                yield

            # Wait state
            # FIXME: Need add_comb_process. Wait states probably work fine
            # anyway.
            for _ in range(ws):
                yield

            yield

    def cpu_proc_aux(regs, mem):
        def check_regs(curr):
            expected_regs = curr
            actual_regs = yield from RV32Regs.from_top_module(m)
            assert expected_regs == actual_regs

        def check_mem(mem):
            if mem:
                for m_adr, m_dat in mem.items():
                    assert (yield m.mem.mem[m_adr]) == m_dat

        for curr_r, curr_m in zip(regs, mem):
            # Wait for insn.
            while not ((yield m.cpu.bus.cyc) and (yield m.cpu.bus.stb) and
                       (yield m.cpu.control.insn_fetch)):
                yield

            # Wait for memory to respond.
            while not (yield m.cpu.bus.ack):
                yield

            # When ACK is asserted, we should always be going to uinsn
            # "check_int".
            assert (yield m.cpu.control.sequencer.adr) == 2 or \
                (yield m.cpu.control.sequencer.adr) == 1
            yield

            # Check results as new insn begins (i.e. prev results).
            yield from check_regs(curr_r)
            yield from check_mem(curr_m)

    insns = assemble("""
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
""")

    regs = [
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
    ]

    ram = [
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
    ]

    m.mem.init_mem = [int.from_bytes(insns[adr:adr+4], byteorder="little")
                      for adr in range(0, len(insns), 4)]

    def bus_proc():
        yield from bus_proc_aux(wait_states=chain([1], repeat(0)))

    def cpu_proc():
        yield from cpu_proc_aux(regs, ram)

    sim.run(sync_processes=[bus_proc, cpu_proc, ucode_panic])


@pytest.mark.module(CPUWithMem())
@pytest.mark.clks((1.0 / 12e6,))
def test_primes(sim_mod, ucode_panic):
    sim, m = sim_mod

    # This is a prime-counting program. It is provided with/disassembled from
    # nextpnr-ice40's examples (https://github.com/YosysHQ/nextpnr/tree/master/ice40/smoketest/attosoc),  # noqa: E501
    # but I don't know about its origins otherwise.
    # I have modified a hardcoded delay from 360000 to 2, as well as stopping
    # after 17 for simulation speed.
    insns = assemble("""
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
""")

    def io_proc():
        primes = [3, 5, 7, 11, 13, 17, 2]
                  # 19, 23, 29, 31, 37, 41, 43, 47, 53,
                  # 59, 61, 67, 71, 73, 79, 83, 89, 97, 101, 103, 107, 109,
                  # 113, 127, 131, 137, 139, 149, 151, 157, 163, 167, 173, 179,
                  # 181, 191, 193, 197, 199, 211, 223, 227, 229, 233, 239, 241,
                  # 251, 2]

        for p in primes:
            for _ in range(65536):
                if ((yield m.cpu.bus.adr == 0x2000000 >> 2) and
                        (yield m.cpu.bus.cyc) and
                        (yield m.cpu.bus.stb) and
                        (yield m.cpu.bus.ack)):
                    assert (yield m.cpu.bus.dat_w) == p
                    break
                else:
                    yield
            else:
                raise AssertionError("CPU (but not microcode) probably stuck "
                                     "in infinite loop")
            yield

    m.mem.init_mem = [int.from_bytes(insns[adr:adr+4], byteorder="little")
                      for adr in range(0, len(insns), 4)]

    sim.run(sync_processes=[io_proc, ucode_panic])
