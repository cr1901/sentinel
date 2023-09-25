from amaranth import Signal, Elaboratable, Module
from amaranth.lib.wiring import Component, Signature, Out, In, connect

from .alu import ALU
from .control import Control
from .datapath import DataPath
from .decode import Decode


class Top(Component):
    signature = Signature({
        "dat_w": Out(32),
        "dat_r": In(32),
        # Registered.
        "adr": Out(32),
        "we": Out(1),
        # Ask bus to send or recv data.
        "req": Out(1),
        # Hold bus until this signal asserts.
        "ack": In(1),
        "insn_fetch": Out(1)
    })

    def __init__(self):
        super().__init__()

        self.req_next = Signal()
        self.insn_fetch_next = Signal()

        ###

        self.alu = ALU(32)
        self.control = Control()
        self.datapath = DataPath()
        self.decode = Decode()

        # ALU
        self.a_input = Signal(32)
        self.b_input = Signal(32)
        self.RegOp = self.control.ucoderom.fields.shape()["reg_op"].shape
        self.ASrc = self.control.ucoderom.fields.shape()["a_src"].shape
        self.BSrc = self.control.ucoderom.fields.shape()["b_src"].shape

        # Decode
        self.reg_adr = Signal(5)

    def elaborate(self, platform):
        m = Module()

        m.submodules.alu = self.alu
        m.submodules.control = self.control
        m.submodules.datapath = self.datapath
        m.submodules.decode = self.decode

        # ALU conns
        connect(m, self.alu.ctrl, self.control.alu)

        # ALU conns
        m.d.comb += [
            self.alu.data.a.eq(self.a_input),
            self.alu.data.b.eq(self.b_input),
        ]

        with m.If(self.control.reg_op == self.RegOp.read_b_latch_a):
            with m.Switch(self.control.a_src):
                with m.Case(self.ASrc.gp):
                    m.d.sync += self.a_input.eq(self.datapath.dat_r)
                with m.Case(self.ASrc.pc):
                    m.d.sync += self.a_input.eq(self.datapath.pc)
        with m.Elif(self.control.reg_op == self.RegOp.latch_b):
            with m.Switch(self.control.b_src):
                with m.Case(self.BSrc.gp):
                    m.d.sync += self.b_input.eq(self.datapath.dat_r)
                with m.Case(self.BSrc.imm):
                    m.d.sync += self.b_input.eq(self.decode.imm)
                with m.Case(self.BSrc.target):
                    m.d.sync += self.b_input.eq(self.decode.dst)

        # Control conns
        m.d.comb += [
            self.control.opcode.eq(self.decode.opcode),
            self.control.requested_op.eq(self.decode.requested_op),
            self.control.e_type.eq(self.decode.e_type),
            self.req_next.eq(self.control.mem_req),
            self.insn_fetch_next.eq(self.control.insn_fetch),
            self.control.mem_valid.eq(self.ack),

            # TODO: Spin out into a register of exception sources.
            self.control.exception.eq(self.decode.illegal)
        ]

        # An ACK stops the request b/c the microcode's to avoid a 1-cycle delay
        # due to registered REQ/FETCH signal.
        m.d.sync += [
            self.req.eq(~self.ack & self.req_next),
            self.insn_fetch.eq(~self.ack & self.insn_fetch_next)
        ]

        # DataPath conns
        m.d.comb += [
            self.datapath.we.eq(self.control.reg_op == self.RegOp.write_dst),
            self.dat_w.eq(self.datapath.dat_w),
            self.datapath.dat_w.eq(self.alu.data.o),
            self.datapath.pc_action.eq(self.control.pc_action),
            self.datapath.reg_adr.eq(self.reg_adr)
        ]

        # DataPath.dat_w constantly has traffic. We only want to latch
        # the address once per mem access, and we want it the address to be
        # valid synchronous with ready assertion.
        with m.If(~self.req & self.req_next):
            with m.If(self.insn_fetch_next):
                m.d.sync += [self.adr.eq(self.datapath.pc)]
            with m.Else():
                m.d.sync += [self.adr.eq(self.datapath.dat_w)]

        # Decode conns
        m.d.comb += [
            self.decode.insn.eq(self.dat_r),
            # Decode begins automatically.
            # self.decode.do_decode.eq(self.insn_fetch & self.ack),
        ]

        with m.If(self.control.reg_op == self.RegOp.read_a):
            m.d.comb += self.reg_adr.eq(self.decode.src_a)
        with m.Elif(self.control.reg_op == self.RegOp.read_b_latch_a):
            m.d.comb += self.reg_adr.eq(self.decode.src_b)
        with m.Elif(self.control.reg_op == self.RegOp.write_dst):
            m.d.comb += self.reg_adr.eq(self.decode.dst)

        return m


class TopMem(Elaboratable):
    def __init__(self):

        self.top = Top()
