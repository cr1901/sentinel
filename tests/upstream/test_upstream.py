
import pytest

from dataclasses import dataclass
from enum import Enum, auto

from sentinel.soc import AttoSoC


@pytest.fixture
def test_bin(sim_mod, request):
    _, m = sim_mod
    rootdir = request.config.rootdir
    test_name = rootdir / "tests" / "upstream" / "binaries" / request.param

    with open(test_name, "rb") as fp:
        bytebin = fp.read()

    m.rom = bytebin


@pytest.fixture
def wait_for_host_write(sim_mod):
    class HOST_STATE(Enum):
        WAITING_FIRST = auto()
        FIRST_ACCESS_ACK = auto()
        WAITING_SECOND = auto()
        SECOND_ACCESS_ACK = auto()
        DONE = auto()
        TIMEOUT = auto()

    _, m = sim_mod

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

    return wait_for_host_write


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


@pytest.mark.module(AttoSoC(sim=True, depth=4096))
@pytest.mark.clks((1.0 / 12e6,))
@pytest.mark.parametrize("test_bin", RV32UI_TESTS, indirect=True)
def test_rv32ui(sim_mod, ucode_panic, test_bin, wait_for_host_write):
    sim, m = sim_mod
    sim.run(sync_processes=[wait_for_host_write, ucode_panic])


RV32MI_TESTS = [
    "csr", "illegal", "lh-misaligned", "lw-misaligned", "ma_addr", "ma_fetch",
    "mcsr", "sbreak", "scall", "sh-misaligned", "shamt", "sw-misaligned",
    "zicntr"
]


@pytest.mark.module(AttoSoC(sim=True, depth=4096))
@pytest.mark.clks((1.0 / 12e6,))
@pytest.mark.parametrize("test_bin", RV32MI_TESTS, indirect=True)
def test_rv32mi(sim_mod, ucode_panic, test_bin, wait_for_host_write):
    sim, m = sim_mod
    sim.run(sync_processes=[wait_for_host_write, ucode_panic])
