import pytest

from amaranth import Value
from amaranth.hdl.ast import ValueCastable
from amaranth.sim import Simulator
from amaranth.lib.wiring import Signature


def pytest_addoption(parser):
    parser.addoption(
        "--vcds",
        action="store_true",
        help="generate Value Change Dump (vcds) from simulations",
    )


class SimulatorFixture:
    def __init__(self, req, cfg):
        self.mod = req.node.get_closest_marker("module").args[0]
        self.name = req.node.name
        self.sim = Simulator(self.mod)
        self.vcds = cfg.getoption("vcds")

        for clk in req.node.get_closest_marker("clks").args[0]:
            self.sim.add_clock(clk)

    @property
    def ports(self):
        # Back-compat
        if hasattr(self.mod, "ports"):
            return self.mod.ports()
        # Stolen from Amaranth 33c2246- intended to be "new" way to populate
        # GTKW files.
        elif hasattr(self.mod, "signature") and isinstance(self.mod.signature,
                                                           Signature):
            ports = []
            for path, member, value in self.mod.signature.flatten(self.mod):
                if isinstance(value, ValueCastable):
                    value = value.as_value()
                if isinstance(value, Value):
                    ports.append(value)
            return ports
        else:
            return ()

    def run(self, sync_processes, processes=[]):
        for s in sync_processes:
            self.sim.add_sync_process(s)

        for p in processes:
            self.sim.add_process(p)

        if self.vcds:
            with self.sim.write_vcd(self.name + ".vcd", self.name + ".gtkw",
                                    traces=self.ports):
                self.sim.run()
        else:
            self.sim.run()


@pytest.fixture
def sim_mod(request, pytestconfig):
    simfix = SimulatorFixture(request, pytestconfig)
    return (simfix, simfix.mod)
