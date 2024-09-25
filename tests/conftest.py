import functools
import pytest

from amaranth import Value
from amaranth.hdl import ValueCastable
from amaranth.sim import Simulator, Passive, Tick
from amaranth.lib.wiring import Signature


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


class SimulatorFixture:
    def __init__(self, req, cfg):
        mod = req.node.get_closest_marker("module").args[0]
        # FIXME: Depending on module contents, some amaranth code, such as
        # amaranth_soc.csr classes don't interact well with elaborating
        # the same object multiple times. This happens during parametrized
        # tests. Therefore, provide an escape hatch to create a fresh object
        # for all arguments of a parameterized test.
        #
        # Ideally, I should figure out the exact conditions under where it's
        # safe to reuse an already-elaborated object (if ever); the tests
        # didn't break until I started using amaranth_soc.csr. But this will
        # do for now.
        if isinstance(mod, functools.partial):
            self.mod = mod()
        else:
            self.mod = mod

        self.name = req.node.name
        self.vcds = cfg.getoption("vcds")
        self.clks = req.node.get_closest_marker("clks").args[0]

    @property
    def ports(self):
        if hasattr(self, "_ports"):
            return self._ports
        else:
            # Back-compat
            if hasattr(self.mod, "ports"):
                return self.mod.ports()
            # Stolen from Amaranth 33c2246- intended to be "new" way to
            # populate GTKW files.
            elif hasattr(self.mod, "signature") and \
                    isinstance(self.mod.signature, Signature):
                ports = []
                for path, member, value in self.mod.signature.flatten(self.mod):  # noqa: E501
                    if isinstance(value, ValueCastable):
                        value = value.as_value()
                    if isinstance(value, Value):
                        ports.append(value)
                return ports
            else:
                return ()

    @ports.setter
    def ports(self, ports):
        self._ports = ports

    def run(self, testbenches=[], sync_processes=[], comb_processes=[]):
        # Don't elaborate until we're ready to sim. This causes weird
        # behaviors if you modify the object after elaboration. For instance,
        # changing a Memory's init file after elaboration causes memory
        # contents to not what's on the bus according to the Python Simulator.
        sim = Simulator(self.mod)

        for c in self.clks:
            sim.add_clock(c)

        for t in testbenches:
            sim.add_testbench(t)

        for s in sync_processes:
            sim.add_process(s)

        for p in comb_processes:
            sim.add_process(p)

        if self.vcds:
            with sim.write_vcd(self.name + ".vcd", self.name + ".gtkw",
                               traces=self.ports):
                sim.run()
        else:
            sim.run()


@pytest.fixture
def sim_mod(request, pytestconfig):
    simfix = SimulatorFixture(request, pytestconfig)
    return (simfix, simfix.mod)


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
