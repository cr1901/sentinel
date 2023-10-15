
import pytest

from dataclasses import dataclass

from sentinel.soc import AttoSoC


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


@pytest.fixture
def test_bin(sim_mod, request):
    _, m = sim_mod
    rootdir = request.config.rootdir
    test_name = rootdir / "tests" / "upstream" / "binaries" / request.param

    with open(test_name, "rb") as fp:
        bytebin = fp.read()

    m.rom = bytebin


RV32UI_TESTS = [
    "add", "addi", "and",  "andi", "auipc", "beq",  "bge",  "bgeu", "blt",
    "bltu", "bne", "fence_i", "jal",  "jalr", "lb", "lbu", "lh",  "lhu",
    "lui", "lw", "ma_data", "or", "ori", "sb", "sh", "simple", "sll", "slli",
    "slt", "slti", "sltiu", "sltu", "sra", "srai", "srl", "srli", "sub", "sw",
    "xor", "xori"
]


@pytest.mark.module(AttoSoC(sim=True, depth=4096))
@pytest.mark.clks((1.0 / 12e6,))
@pytest.mark.parametrize("test_bin", RV32UI_TESTS, indirect=True)
def test_rv32ui(sim_mod, ucode_panic, test_bin):
    sim, m = sim_mod

    def wait_for_ecall_proc():
        i = 0
        for _ in range(65536):
            if (((yield m.cpu.bus.dat_r) == 0x00000073) and
                    (yield m.cpu.bus.cyc) and
                    (yield m.cpu.bus.stb) and
                    (yield m.cpu.bus.ack)):
                yield
                regs = yield from RV32Regs.from_top_module(m)
                assert (regs.R3, regs.R10, regs.R17) == (1, 0, 93)
                break
            else:
                yield

            i += 1
        else:
            raise AssertionError("CPU (but not microcode) probably stuck "
                                 "in infinite loop")

    sim.run(sync_processes=[wait_for_ecall_proc, ucode_panic])
