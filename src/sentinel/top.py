from itertools import repeat, chain

from amaranth import *
from amaranth.sim import Passive

from .alu import ALU
from .control import Control
from .datapath import DataPath
from .decode import Decode, OpcodeType

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
        self.insn_fetch = Signal()
        self.insn_fetch_next = Signal()

        ###

        self.alu = ALU(32)
        self.control = Control()
        self.datapath = DataPath()
        self.decode = Decode()

        # ALU
        self.a_input = Signal(32)
        self.b_input = Signal(32)
        self.RegOp = self.control.ucoderom.fields.reg_op
        self.ASrc = self.control.ucoderom.fields.a_src
        self.BSrc = self.control.ucoderom.fields.b_src

        # Decode
        self.reg_adr = Signal(5)

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
            self.alu.op.eq(self.control.alu_op),
            self.control.alu_ready.eq(self.alu.ready)
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
            self.datapath.dat_w.eq(self.alu.o),
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

    def ports(self):
        return [self.dat_w, self.dat_r, self.adr, self.we, self.req, self.ack, self.insn_fetch]


class TopMem(Elaboratable):
    def __init__(self):

        self.top = Top()
