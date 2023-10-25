import pytest
import enum

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
@pytest.mark.module(UCodeROM(main_file=StringIO(M5META_TEST_FILE),
                             enum_map={"bar": Bar}))
@pytest.mark.clks((1.0 / 12e6,))
def test_ucode_layout_gen(sim_mod):
    _, m = sim_mod
    m.elaborate(None)


@pytest.mark.module(UCodeROM(main_file=StringIO(M5META_TEST_FILE),
                             enum_map={"bar": Bar}))
@pytest.mark.clks((1.0 / 12e6,))
@pytest.mark.parametrize("dummy", [1, 2])
@pytest.mark.skip(reason="Not yet implemented.")
def test_twice_init(sim_mod, dummy):
    sim, m = sim_mod

    def ucode_proc():
        yield m.addr.eq(0)
        yield
        yield m.addr.eq(1)
        yield

    sim.run(sync_processes=[ucode_proc])
