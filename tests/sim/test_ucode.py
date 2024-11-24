import pytest
import enum

from amaranth import Fragment, unsigned
from io import StringIO

from sentinel.ucoderom import UCodeROM


M5META_TEST_FILE = """
space block_ram: width 32, size 256;

space block_ram;
origin 0;

fields block_ram: {
  foo: width 8, origin 0, default 0;
  bar: enum { a = 0; b = 0; c = 1; }, default a;
  baz: bool, origin 12, default 0;
};

foo => 0, bar => c, baz => true;
foo => 1, bar => b, baz => false;
"""


class Bar(enum.Enum):
    A = 0
    B = 0
    C = 1


# This is a test by itself because creating the signature from the microcode
# assembly file can be tricky.
def test_ucode_layout_gen():
    m = UCodeROM(main_file=StringIO(M5META_TEST_FILE),
                 field_map={"foo": unsigned(8),
                            "bar": Bar,
                            "baz": unsigned(1)})
    # Use Fragment.get to ensure the Module is marked as used.
    Fragment.get(m, None)


@pytest.mark.parametrize("mod,clks", [
                         (UCodeROM(main_file=StringIO(M5META_TEST_FILE),
                                   field_map={"foo": unsigned(8),
                                              "bar": Bar,
                                              "baz": unsigned(1)}),
                          1.0 / 12e6)])
@pytest.mark.parametrize("dummy", [1, 2])
@pytest.mark.skip(reason="Not yet implemented.")
def test_twice_init(sim, mod, dummy):
    m = mod

    async def ucode_tb(ctx):
        ctx.set(m.addr, 0)
        ctx.tick()
        ctx.set(m.addr, 1)
        ctx.tick()

    sim.run(processes=[ucode_tb])
