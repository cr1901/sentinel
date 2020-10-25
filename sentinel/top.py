from nmigen import *

from .alu import ALU
from .control import Control
from .datapath import DataPath
from .decode import Decode

class Top(Elaboratable):
    def __init__(self):
        self.dat_w = Signal(32)
        self.dat_r = Signal(32)
        # Registered.
        self.adr = Signal(32)
        self.we = Signal(4)
        # Ask bus to send or recv data.
        self.req = Signal()
        self.req_next = Signal()
        # Hold bus until this signal asserts.
        self.ack = Signal()

        ###

        self.alu = ALU(32)
        self.control = Control()
        self.datapath = DataPath()
        self.decode = Decode()

        # ALU
        self.a_input = Signal(32)
        self.b_input = Signal(32)
        self.ReadReg = self.control.ucoderom.fields["read_reg"]
        self.ASrc = self.control.ucoderom.fields["a_src"]
        self.BSrc = self.control.ucoderom.fields["b_src"]

    def elaborate(self, platform):
        m = Module()

        m.submodules.alu = self.alu
        m.submodules.control = self.control
        m.submodules.datapath = self.datapath
        m.submodules.decode = self.decode

        # ALU conns
        m.d.comb += [
            self.alu.a.eq(self.a_input),
            self.alu.b.eq(self.b_input),
            self.control.alu_ready.eq(self.alu.ready)
        ]

        with m.If(self.control.read_reg == self.ReadReg.a_src):
            with m.Switch(self.control.a_src):
                with m.Case(self.ASrc.gp):
                    m.d.sync += self.a_input.eq(self.datapath.dat_r)
                with m.Case(self.ASrc.pc):
                    m.d.sync += self.a_input.eq(self.datapath.pc)

        with m.If(self.control.read_reg == self.ReadReg.b_src):
            with m.Switch(self.control.b_src):
                with m.Case(self.BSrc.gp):
                    m.d.sync += self.b_input.eq(self.datapath.dat_r)
                with m.Case(self.BSrc.imm):
                    m.d.sync += self.b_input.eq(self.decode.imm)
                with m.Case(self.BSrc.target):
                    m.d.sync += self.b_input.eq(self.decode.dst)

        # Plumbing
        m.d.comb += [
            self.dat_w.eq(self.datapath.dat_w),
            self.datapath.dat_w.eq(self.alu.o),
            self.decode.insn.eq(self.dat_r)
        ]

        # Control
        m.d.sync += self.req.eq(self.req_next)

        # DataPath.dat_w constantly has traffic. We only want to latch
        # the address once per mem access, and we want it the address to be
        # valid synchronous with ready assertion.
        with m.If(~self.req & self.req_next):
            m.d.sync += [self.adr.eq(self.datapath.dat_w)]

        return m

    def ports(self):
        return [self.dat_w, self.dat_r, self.adr, self.we, self.req, self.ack]

    def sim_hooks(self, sim):
        pass
