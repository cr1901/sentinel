from typing import Union
import pytest

from dataclasses import astuple, dataclass, field
from bronzebeard.asm import assemble


def pytest_addoption(parser):
    parser.addoption(
        "--runbench", action="store_true", default=False, help="run benchmarks"
    )
    parser.addoption(
        "--runsoc", action="store_true", default=False,
        help="run SoC simulation"
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--runbench"):
        skip_bench = pytest.mark.skip(reason="need --runbench option to run")
        for item in items:
            if "bench" in item.keywords:
                item.add_marker(skip_bench)

    if not config.getoption("--runsoc"):
        skip_soc = pytest.mark.skip(reason="need --runsoc option to run")
        for item in items:
            if "soc" in item.keywords:
                item.add_marker(skip_soc)


@pytest.fixture
def ucode_panic(mod):
    m = mod

    async def ucode_panic(ctx):
        addr = 0
        prev_addr = 2
        count = 0
        async for *_, addr in ctx.tick().sample(m.control.ucoderom.addr):
            if addr == 255:
                raise AssertionError("microcode panic (not implemented)")

            if prev_addr == addr:
                count += 1
                if count > 100:
                    raise AssertionError("microcode probably stuck in "
                                         "infinite loop")
            else:
                count = 0

            prev_addr = addr

    return ucode_panic


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


async def mproc_inner(mod, ctx, memory):
    m = mod

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


@pytest.fixture
def memory_process(mod, memory):
    m = mod

    async def memory_process(ctx):
        await mproc_inner(m, ctx, memory)

    return memory_process
