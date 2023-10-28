import pytest

from amaranth import Value
from amaranth.hdl.ast import ValueCastable
from amaranth.sim import Simulator, Passive
from amaranth.lib.wiring import Signature


def pytest_addoption(parser):
    parser.addoption(
        "--vcds",
        action="store_true",
        help="generate Value Change Dump (vcds) from simulations",
    )
    parser.addoption(
        "--runbench", action="store_true", default=False, help="run benchmarks"
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runbench"):
        # --runslow given in cli: do not skip slow tests
        return
    skip_bench = pytest.mark.skip(reason="need --runbench option to run")
    for item in items:
        if "bench" in item.keywords:
            item.add_marker(skip_bench)


class SimulatorFixture:
    def __init__(self, req, cfg):
        self.mod = req.node.get_closest_marker("module").args[0]
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

    def run(self, sync_processes, processes=[]):
        # Don't elaborate until we're ready to sim. This causes weird
        # behaviors if you modify the object after elaboration. For instance,
        # changing a Memory's init file after elaboration causes memory
        # contents to not what's on the bus according to the Python Simulator.
        sim = Simulator(self.mod)

        for c in self.clks:
            sim.add_clock(c)

        for s in sync_processes:
            sim.add_sync_process(s)

        for p in processes:
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
def ucode_panic(sim_mod):
    _, m = sim_mod

    def ucode_panic():
        yield Passive()

        addr = 0
        prev_addr = 0
        count = 0
        while True:
            yield

            if (yield m.cpu.control.ucoderom.addr == 255):
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
