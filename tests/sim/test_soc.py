from pathlib import Path
import pytest

from itertools import islice
from functools import reduce
from elftools.elf.elffile import ELFFile


# FIXME: Eventually drop the need for SoC and simulate memory purely with
# a process like in RISCOF tests? This will be pretty invasive.
from examples.attosoc import AttoSoC


# Fixture overrides for SoC tests.
# Required because we have to initialize memory before passing to sim fixture.
# Otherwise amaranth 0.5 will throw an "AlreadyElaborated" error.
@pytest.fixture
def mod(request):
    m = AttoSoC(num_bytes=0x1000)

    firmware_dir = request.config.rootdir / \
        Path("target/riscv32i-unknown-none-elf/release/examples")
    firmware_bin = firmware_dir / "attosoc"

    if not firmware_bin.isfile():
        pytest.skip("attosoc binary not present")

    with open(firmware_bin, "rb") as fp:  # noqa: E501
        def append_bytes(a, b):
            return a + b

        def seg_data(seg):
            return seg.data()

        segs = ELFFile(fp).iter_segments()
        text_ro_and_data_segs = islice(segs, 2)
        m.rom = reduce(append_bytes,
                       map(seg_data, text_ro_and_data_segs),
                       b"")

    return m


@pytest.fixture
def ucode_panic(mod):
    m = mod

    async def ucode_panic(ctx):
        addr = 0
        prev_addr = 2
        count = 0
        async for *_, addr in ctx.tick().sample(m.cpu.control.ucoderom.addr):
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


# Infrequently-used test mostly for testing address decoding. Should not cause
# failure if user does not have Rust installed.
@pytest.mark.parametrize("clks", [(1.0 / 12e6)])
@pytest.mark.soc
def test_rust(sim, mod, ucode_panic):
    m = mod

    async def io_tb(ctx):
        *_, tx = await ctx.tick().sample(m.serial.tx).repeat(2000)
        assert tx == 0

    sim.run(testbenches=[io_tb], processes=[ucode_panic])
