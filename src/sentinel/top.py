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
        self.insn_fetch_curr = Signal()
        self.insn_fetch_next = Signal()

        ###

        self.alu = ALU(32)
        self.control = Control()
        self.ucode = self.control.ucoderom.field_classes
        self.datapath = DataPath(self.ucode)
        self.decode = Decode()

        # ALU
        self.a_input = Signal(32)
        self.b_input = Signal(32)
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

        with m.If(self.control.datapath.gp_action ==
                  self.ucode.RegOp.READ_B_LATCH_A):
            with m.Switch(self.control.a_src):
                with m.Case(self.ASrc.GP):
                    m.d.sync += self.a_input.eq(self.datapath.gp.dat_r)
                with m.Case(self.ASrc.PC):
                    m.d.sync += self.a_input.eq(self.datapath.pc.dat_r)
        with m.Elif(self.control.datapath.gp_action ==
                    self.ucode.RegOp.LATCH_B):
            with m.Switch(self.control.b_src):
                with m.Case(self.BSrc.GP):
                    m.d.sync += self.b_input.eq(self.datapath.gp.dat_r)
                with m.Case(self.BSrc.IMM):
                    m.d.sync += self.b_input.eq(self.decode.imm)
                with m.Case(self.BSrc.TARGET):
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
        m.d.comb += [
            self.req.eq(self.control.mem_req),
            self.insn_fetch.eq(self.control.insn_fetch)
        ]

        # DataPath conns
        connect(m, self.datapath.ctrl, self.control.datapath)
        m.d.comb += [
            self.dat_w.eq(self.datapath.gp.dat_w),
            self.datapath.gp.dat_w.eq(self.alu.data.o),
            self.datapath.gp.adr.eq(self.reg_adr)
        ]

        # DataPath.dat_w constantly has traffic. We only want to latch
        # the address once per mem access, and we want it the address to be
        # valid synchronous with ready assertion.
        with m.If(self.req):
            with m.If(self.insn_fetch_next):
                m.d.comb += [self.adr.eq(self.datapath.pc.dat_r)]
            with m.Else():
                m.d.comb += [self.adr.eq(self.datapath.gp.dat_w)]

        # Decode conns
        m.d.comb += [
            self.decode.insn.eq(self.dat_r),
            # Decode begins automatically.
            self.decode.do_decode.eq(self.insn_fetch & self.ack),
        ]

        with m.If(self.control.datapath.gp_action == self.ucode.RegOp.READ_A):
            m.d.comb += self.reg_adr.eq(self.decode.src_a)
        with m.Elif(self.control.datapath.gp_action ==
                    self.ucode.RegOp.READ_B_LATCH_A):
            m.d.comb += self.reg_adr.eq(self.decode.src_b)
        with m.Elif(self.control.datapath.gp_action ==
                    self.ucode.RegOp.WRITE_DST):
            m.d.comb += self.reg_adr.eq(self.decode.dst)

        return m


class TopMem(Elaboratable):
    def __init__(self):

        self.top = Top()
