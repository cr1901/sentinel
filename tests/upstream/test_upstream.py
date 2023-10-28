
import pytest

from dataclasses import dataclass
from enum import Enum, auto

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
    "bltu", "bne",
    pytest.param("fence_i", marks=pytest.mark.xfail(reason="Zifencei not implemented")),  # noqa: E501
    "jal",  "jalr", "lb", "lbu", "lh",  "lhu",
    "lui", "lw",
    pytest.param("ma_data", marks=pytest.mark.xfail(reason="misaligned access not yet implemented")),  # noqa: E501
    "or", "ori", "sb", "sh", "simple", "sll", "slli",
    "slt", "slti", "sltiu", "sltu", "sra", "srai", "srl", "srli", "sub", "sw",
    "xor", "xori"
]


class HOST_STATE(Enum):
    WAITING_FIRST = auto()
    FIRST_ACCESS_ACK = auto()
    WAITING_SECOND = auto()
    SECOND_ACCESS_ACK = auto()
    DONE = auto()
    TIMEOUT = auto()


@pytest.mark.module(AttoSoC(sim=True, depth=4096))
@pytest.mark.clks((1.0 / 12e6,))
@pytest.mark.parametrize("test_bin", RV32UI_TESTS, indirect=True)
def test_rv32ui(sim_mod, ucode_panic, test_bin):
    sim, m = sim_mod

    # TODO: Convert into SoC module (use wishbone.Decoder and friends)?
    def wait_for_host_write():
        i = 0
        state = HOST_STATE.WAITING_FIRST
        val = None

        while True:
            match state:
                case HOST_STATE.WAITING_FIRST:
                    if ((yield m.cpu.bus.adr) == 0x4000000 >> 2) and \
                            (yield m.cpu.bus.sel == 0b1111) and \
                            (yield m.cpu.bus.cyc) and (yield m.cpu.bus.stb):
                        yield m.cpu.bus.ack.eq(1)
                        state = HOST_STATE.FIRST_ACCESS_ACK
                case HOST_STATE.FIRST_ACCESS_ACK:
                    val = (yield m.cpu.bus.dat_w)
                    yield m.cpu.bus.ack.eq(0)
                    state = HOST_STATE.WAITING_SECOND
                case HOST_STATE.WAITING_SECOND:
                    if (yield m.cpu.bus.adr) == ((0x4000000 + 4) >> 2) and \
                            (yield m.cpu.bus.sel == 0b1111) and \
                            (yield m.cpu.bus.cyc) and (yield m.cpu.bus.stb):
                        yield m.cpu.bus.ack.eq(1)
                        state = HOST_STATE.SECOND_ACCESS_ACK
                case HOST_STATE.SECOND_ACCESS_ACK:
                    val |= ((yield m.cpu.bus.dat_w) << 32)
                    yield m.cpu.bus.ack.eq(0)
                    state = HOST_STATE.DONE
                case HOST_STATE.DONE:
                    assert (val >> 1, val & 1) == (0, 1)
                    break
                case HOST_STATE.TIMEOUT:
                    raise AssertionError("CPU (but not microcode) probably "
                                         "stuck in infinite loop")

            yield
            i += 1
            if i > 65535:
                state = HOST_STATE.TIMEOUT

    sim.run(sync_processes=[wait_for_host_write, ucode_panic])
