import pytest

from enum import Enum, auto

from sentinel.top import Top
from tests.conftest import Memory


# Generate prettier names by not bothering to parameterize on these.
@pytest.fixture(scope="function")
def mod():
    return Top()


@pytest.fixture(scope="module")
def clks():
    return 1.0 / 12e6


# Special memory fixture to load the upstream tests.
@pytest.fixture
def memory(request):
    rootdir = request.config.rootdir
    test_name = rootdir / "tests" / "upstream" / "binaries" / request.param

    with open(test_name, "rb") as fp:
        bytebin = fp.read()

    mem = Memory(0, 4096)

    for adr in range(0, len(bytebin) // 4):
        mem[adr] = int.from_bytes(bytebin[4 * adr:4 * adr + 4],
                                  byteorder="little")

    return mem


async def wfhw_inner(mod, ctx):
    class HOST_STATE(Enum):
        WAITING_FIRST = auto()
        FIRST_ACCESS_ACK = auto()
        WAITING_SECOND = auto()
        SECOND_ACCESS_ACK = auto()
        DONE = auto()
        TIMEOUT = auto()

    m = mod
    i = 0
    state = HOST_STATE.WAITING_FIRST
    val = 0xdeadbeef

    while True:
        stims = [m.bus.cyc & m.bus.stb, m.bus.adr, m.bus.dat_w, m.bus.we,
                    m.bus.sel]
        *_, wb_cyc, addr, dat_w, we, sel = await ctx.tick().sample(*stims)

        i += 1
        if i > 65535:
            state = HOST_STATE.TIMEOUT

        match state:
            case HOST_STATE.WAITING_FIRST:
                if (addr == 0x4000000 >> 2) and (sel == 0b1111) and \
                        wb_cyc and we:
                    ctx.set(m.bus.ack, 1)
                    state = HOST_STATE.FIRST_ACCESS_ACK
            case HOST_STATE.FIRST_ACCESS_ACK:
                val = dat_w
                ctx.set(m.bus.ack, 0)
                state = HOST_STATE.WAITING_SECOND
            case HOST_STATE.WAITING_SECOND:
                if addr == ((0x4000000 + 4) >> 2) and (sel == 0b1111) and \
                        wb_cyc and we:
                    ctx.set(m.bus.ack, 1)
                    state = HOST_STATE.SECOND_ACCESS_ACK
            case HOST_STATE.SECOND_ACCESS_ACK:
                val |= (dat_w << 32)
                ctx.set(m.bus.ack, 0)
                state = HOST_STATE.DONE
            case HOST_STATE.DONE:
                break
            case HOST_STATE.TIMEOUT:
                raise AssertionError("CPU (but not microcode) probably "
                                        "stuck in infinite loop")

    return val


@pytest.fixture
def wait_for_host_write(mod, request):
    # TODO: Convert into SoC module (use wishbone.Decoder and friends)?
    async def wait_for_host_write(ctx):
        val = await wfhw_inner(mod, ctx)
        assert (val >> 1, val & 1) == (0, 1)

    return wait_for_host_write


RV32UI_TESTS = [
    "add", "addi", "and", "andi", "auipc", "beq", "bge", "bgeu", "blt",
    "bltu", "bne",
    pytest.param("fence_i", marks=pytest.mark.xfail(reason="Zifencei not implemented")),  # noqa: E501
    "jal", "jalr", "lb", "lbu", "lh", "lhu",
    "lui", "lw",
    pytest.param("ma_data", marks=pytest.mark.xfail(reason="misaligned access are traps")),  # noqa: E501
    "or", "ori", "sb", "sh", "simple", "sll", "slli",
    "slt", "slti", "sltiu", "sltu", "sra", "srai", "srl", "srli", "sub", "sw",
    "xor", "xori"
]


@pytest.mark.parametrize("memory", RV32UI_TESTS, indirect=True)
def test_rv32ui(sim, ucode_panic, wait_for_host_write, memory_process):
    sim.run(testbenches=[wait_for_host_write], processes=[ucode_panic,
                                                          memory_process])


RV32MI_TESTS = [
    "csr", "illegal", "lh-misaligned", "lw-misaligned", "ma_addr",
    "ma_fetch",
    pytest.param("mcsr", marks=pytest.mark.xfail(reason="writable misa not implemented")),  # noqa: E501
    "sbreak", "scall", "sh-misaligned", "shamt", "sw-misaligned",
    pytest.param("zicntr", marks=pytest.mark.xfail(reason="Zicntr not implemented"))  # noqa: E501
]


@pytest.mark.parametrize("memory", RV32MI_TESTS, indirect=True)
def test_rv32mi(sim, ucode_panic, wait_for_host_write, memory_process):
    sim.run(testbenches=[wait_for_host_write], processes=[ucode_panic,
                                                          memory_process])
