from nmigen import *

from .alu import ALU
from .control import Control
from .datapath import DataPath
from .decode import Decode

class Top(Elaboratable):
    def __init__(self):
        self.dat_w = Signal(32)
        self.dat_r = Signal(32)
        self.adr = Signal(32)
        self.we = Signal(32)
        # Hold bus until this signal asserts.
        self.rdy = Signal()

        self.alu = ALU(32)
        self.control = Control()
        self.datapath = DataPath()
        self.decode = Decode()

    def elaborate(self, platform):
        m = Module()

        m.submodules.alu = self.alu
        m.submodules.control = self.control
        m.submodules.datapath = self.datapath
        m.submodules.decode = self.decode

        # Plumbing
        m.d.comb += [
            self.datapath.dat_w.eq(self.alu.o),
            self.decode.insn.eq(self.dat_r)
        ]

        # Control

        return m

    def ports(self):
        return [self.dat_w, self.dat_r, self.adr, self.we]

    def sim_hooks(self, sim):
        pass
