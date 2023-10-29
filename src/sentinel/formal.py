from amaranth import Signal, Module, Cat, C
from amaranth.lib.wiring import Component, Signature, Out, In, connect, \
    flipped
from amaranth_soc import wishbone

from .top import Top
from .alu import ALU
from .control import Control
from .csr import MCause
from .datapath import DataPath
from .decode import Decode
from .ucodefields import ASrc, BSrc, RegRSel, RegWSel, MemSel, \
    PcAction, MemExtend, CSRSel, CSROp, ExceptCtl


RVFISignature = Signature({
    "valid": Out(1),
    "order": Out(64),
    "insn": Out(32),
    "trap": Out(1),
    "halt": Out(1),
    "intr":  Out(1),
    "mode": Out(2),
    "ixl": Out(2),
    "rs1_addr": Out(5),
    "rs2_addr": Out(5),
    "rs1_rdata": Out(32),
    "rs2_rdata": Out(32),
    "rd_addr": Out(5),
    "rd_wdata": Out(32),
    "pc_rdata": Out(32),
    "pc_wdata": Out(32),
    "mem_addr": Out(32),
    "mem_rmask": Out(4),
    "mem_wmask": Out(4),
    "mem_rdata": Out(32),
    "mem_wdata": Out(32)
})


class FormalTop(Component):
    CHECK_INT_ADDR = 1
    EXCEPTION_HANDLER_ADDR = 240

    @property
    def signature(self):
        return Signature({
            "bus": Out(wishbone.Signature(addr_width=30, data_width=32,
                                          granularity=8)),
            "rvfi": Out(RVFISignature),
            "irq": In(1)
        })

    def __init__(self):
        super().__init__()
        self.cpu = Top(formal=True)

    def elaborate(self, plat):
        m = Module()

        m.submodules.cpu = self.cpu

        connect(m, self.cpu.bus, flipped(self.bus))
        m.d.comb += self.irq.eq(self.cpu.irq)

        # rvfi_valid
        curr_upc = Signal.like(self.cpu.control.ucoderom.addr)
        prev_upc = Signal.like(curr_upc)

        # In general, if there's an insn_fetch and ACK, by the next cycle,
        # the insn has been retired. Handle exceptions to this rule on a
        # case-by-case basis.
        m.d.sync += [
            curr_upc.eq(self.cpu.control.ucoderom.addr),
            prev_upc.eq(curr_upc),
        ]

        # rvfi_insn/trap/rs1_addr/rs2_addr/rd_addr/rd_wdata/pc_rdata/
        # valid/order/rs1_data/rs2_data/pc_wdata/mem_addr/mem_rmask/
        # mem_wmask/mem_rdata/mem_wdata
        m.submodules.rvfi_rs1 = rs1_port = self.cpu.datapath.regfile.mem.read_port()  # noqa: E501
        m.submodules.rvfi_rs2 = rs2_port = self.cpu.datapath.regfile.mem.read_port()  # noqa: E501

        first_insn = Signal(1, reset=1)
        insn_temp = Signal.like(self.cpu.decode.insn)
        rd_temp = Signal.like(self.cpu.decode.dst)

        m.d.sync += self.rvfi.trap.eq(self.cpu.rvfi.exception)

        with m.FSM():
            # There is nothing to pipeline/interleave, so wait for first
            # insn to be fetched.
            # The CHECK_INT_ADDR line is meant to only latch the last insn
            # that is ACK'd before moving to upc == 1, since the solver
            # will happily ignore wishbone timing.
            with m.State("FIRST_INSN"):
                with m.If(self.cpu.control.insn_fetch & self.cpu.bus.ack &
                          (self.cpu.control.ucoderom.addr ==
                           self.CHECK_INT_ADDR)):
                    m.d.sync += self.rvfi.trap.eq(0)
                    m.next = "VALID_LATCH_DECODER"

            with m.State("VALID_LATCH_DECODER"):
                m.d.comb += [
                    self.rvfi.valid.eq(1),
                ]
                m.d.sync += [
                    self.rvfi.insn.eq(insn_temp),
                    self.rvfi.order.eq(self.rvfi.order + 1),
                    self.rvfi.rs1_addr.eq(self.cpu.decode.src_a),
                    self.rvfi.rs2_addr.eq(self.cpu.decode.src_b),
                    # We have access to RD now, but RVFI mandates zero if
                    # no write. So wait until we know for sure.
                    self.rvfi.rd_addr.eq(0),
                    # Ditto.
                    self.rvfi.rd_wdata.eq(0),
                    self.rvfi.pc_rdata.eq(self.cpu.datapath.pc.dat_r << 2),
                ]

                with m.If(first_insn):
                    m.d.comb += self.rvfi.valid.eq(0)
                    m.d.sync += [
                        self.rvfi.order.eq(0),
                        first_insn.eq(0),
                    ]

                # Prepare to read register file.
                m.d.comb += [
                    rs1_port.addr.eq(self.cpu.decode.rs1),
                    rs2_port.addr.eq(self.cpu.decode.rs2)
                ]

                m.next = "WAIT_FOR_ACK"

            with m.State("WAIT_FOR_ACK"):
                # Hold addresses in case we're here for a bit.
                m.d.comb += [
                    rs1_port.addr.eq(self.cpu.decode.rs1),
                    rs2_port.addr.eq(self.cpu.decode.rs2)
                ]

                m.d.sync += [
                    self.rvfi.rs1_rdata.eq(rs1_port.data),
                    self.rvfi.rs2_rdata.eq(rs2_port.data),
                    rd_temp.eq(self.cpu.decode.dst)
                ]

                # And latch write data if there's a write.
                with m.If(self.cpu.datapath.gp.ctrl.reg_write):
                    m.d.sync += self.rvfi.rd_addr.eq(rd_temp)
                    with m.If(rd_temp != 0):
                        m.d.sync += self.rvfi.rd_wdata.eq(
                            self.cpu.datapath.gp.dat_w)

                # FIXME: Turn into a "peek" action for the PC reg, rather
                # than duplicating PC logic here.
                with m.If(self.cpu.datapath.pc.ctrl.action == PcAction.INC):
                    m.d.sync += self.rvfi.pc_wdata.eq(
                        (self.cpu.datapath.pc.dat_r + 1) << 2)
                with m.Elif(self.cpu.datapath.pc.ctrl.action ==
                            PcAction.LOAD_ALU_O):
                    m.d.sync += self.rvfi.pc_wdata.eq(
                        self.cpu.datapath.pc.dat_w << 2)

                with m.If(~self.cpu.control.insn_fetch & self.cpu.bus.ack):
                    m.d.sync += [
                        self.rvfi.mem_addr.eq(self.cpu.bus.adr << 2),
                        self.rvfi.mem_rdata.eq(self.cpu.bus.dat_r),
                        self.rvfi.mem_wdata.eq(self.cpu.bus.dat_w),
                    ]

                    with m.If(self.cpu.bus.we):
                        m.d.sync += [
                            self.rvfi.mem_rmask.eq(0),
                            self.rvfi.mem_wmask.eq(self.cpu.bus.sel)
                        ]
                    with m.Else():
                        m.d.sync += [
                            self.rvfi.mem_rmask.eq(self.cpu.bus.sel),
                            self.rvfi.mem_wmask.eq(0)
                        ]

                with m.If(self.cpu.control.insn_fetch & self.cpu.bus.ack &
                          (self.cpu.control.ucoderom.addr ==
                           self.CHECK_INT_ADDR)):
                    m.d.sync += insn_temp.eq(self.cpu.decode.insn)
                    m.d.sync += self.rvfi.trap.eq(0)
                    m.next = "VALID_LATCH_DECODER"

        # rvfi_intr
        with m.If(self.rvfi.valid):
            m.d.sync += self.rvfi.intr.eq(0)

        # FIXME: Imprecise/needs work.
        with m.If(curr_upc == self.EXCEPTION_HANDLER_ADDR):
            m.d.sync += self.rvfi.intr.eq(1)

        # rvfi_halt
        m.d.comb += self.rvfi.halt.eq(0)

        # rvfi_mode
        m.d.comb += self.rvfi.mode.eq(2)

        # rvfi_ixl
        m.d.comb += self.rvfi.ixl.eq(1)

        return m
