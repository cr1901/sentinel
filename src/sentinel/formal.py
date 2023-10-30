from amaranth import Signal, Module, Cat, C, Mux
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

        # rs1/rs2_data helpers.
        m.submodules.rvfi_rs1 = rs1_port = self.cpu.datapath.regfile.mem.read_port()  # noqa: E501
        m.submodules.rvfi_rs2 = rs2_port = self.cpu.datapath.regfile.mem.read_port()  # noqa: E501

        # By default, don't output new data on the ports.
        m.d.comb += [
            rs1_port.en.eq(0),
            rs2_port.en.eq(0),
        ]

        # Insn retirement helpers.
        in_init = Signal(1, reset=1)
        committed_to_insn = Signal()
        just_committed_to_insn = Signal()
        # If we fetched an insn and the bus just ACK'ed, the next cycle the
        # microcode will check for interrupts and start processing the
        # insn. Therefore this cycle can be considered retirement.
        m.d.comb += committed_to_insn.eq(self.cpu.control.insn_fetch &
                                         self.cpu.bus.ack &
                                         (self.cpu.control.ucoderom.addr ==
                                          self.CHECK_INT_ADDR))
        m.d.sync += just_committed_to_insn.eq(committed_to_insn)

        # RVFI RD_DATAW helpers.
        dat_w_mux = Signal.like(self.cpu.datapath.regfile.dat_w)
        dat_w_reg = Signal.like(self.cpu.datapath.regfile.dat_w)
        m.d.comb += dat_w_mux.eq(Mux(self.cpu.datapath.gp.ctrl.reg_write,
                                     self.cpu.datapath.regfile.dat_w,
                                     dat_w_reg))
        with m.If(self.cpu.datapath.gp.ctrl.reg_write):
            m.d.sync += dat_w_reg.eq(self.cpu.datapath.regfile.dat_w)

        # RVFI_INTR helpers
        exception_taken = Signal()

        with m.If(committed_to_insn):
            with m.If(in_init):
                # There is nothing to pipeline/interleave, so wait for first
                # insn to be fetched, and then process it before declaring
                # valid.
                m.d.sync += in_init.eq(0)
            with m.Elif(exception_taken):
                # If an exception was taken, we didn't retire an insn. Do
                # not set valid. Do not increment order. But process all
                # other signals as normal.
                m.d.sync += [
                    exception_taken.eq(0),
                    self.rvfi.intr.eq(1),
                ]
            with m.Else():
                m.d.comb += self.rvfi.valid.eq(1)
                m.d.sync += [
                    self.rvfi.order.eq(self.rvfi.order + 1),
                    self.rvfi.intr.eq(0),
                ]

            # RVFI is valid for only a single cycle; prepare to latch new
            # insn data.
            m.d.sync += [
                self.rvfi.trap.eq(0),
                self.rvfi.insn.eq(self.cpu.decode.insn),
                self.rvfi.rs1_addr.eq(self.cpu.decode.rs1),
                self.rvfi.rs2_addr.eq(self.cpu.decode.rs2),
                self.rvfi.rd_addr.eq(self.cpu.decode.rd),
                # The just-retired insn's PC. Overwrite with the fetched PC,
                # the nominal PC_WDATA.
                self.rvfi.pc_rdata.eq(self.cpu.datapath.pc.dat_r << 2),
            ]

            # If write of prev insn is happening while we've committed to a
            # new insn, make sure we present the correct data to RVFI.
            m.d.comb += [
                self.rvfi.rd_wdata.eq(dat_w_mux),

                # Nominally, PC_WDATA of the retired insn becomes PC_RDATA
                # of the current insn when it retires. But in the case of
                # exceptions, this isn't necessarily true. So expose what insn
                # was actually fetched according to the PC while everything's
                # valid.
                self.rvfi.pc_wdata.eq(self.cpu.datapath.pc.dat_r << 2)
            ]

            # Prepare to latch read data for the incoming insn.
            m.d.comb += [
                rs1_port.en.eq(1),
                rs2_port.en.eq(1),
                rs1_port.addr.eq(self.cpu.decode.rs1),
                rs2_port.addr.eq(self.cpu.decode.rs2)
            ]

        with m.If(just_committed_to_insn):
            # Get data from last cycle. If we ever get insns that retire in
            # 2 cycles, then this will need to be muxed like RD_WDATA.
            m.d.sync += [
                self.rvfi.rs1_rdata.eq(rs1_port.data),
                self.rvfi.rs2_rdata.eq(rs2_port.data)
            ]

        # Will be reset every time we commit to a new insn.
        with m.If(self.cpu.rvfi.exception):
            m.d.sync += self.rvfi.trap.eq(1)
        with m.Elif(committed_to_insn):
            m.d.sync += self.rvfi.trap.eq(0)

        # We've decided to taken an exception. This may be replacable with
        # RVFI_TRAP, but Idk for sure right now.
        with m.If(self.cpu.control.ucoderom.addr ==
                  self.EXCEPTION_HANDLER_ADDR):
            m.d.sync += exception_taken.eq(1)

        # Non-insn memory accesses.
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
        with m.Else():
            m.d.sync += [
                self.rvfi.mem_rmask.eq(0),
                self.rvfi.mem_wmask.eq(0)
            ]

        # rvfi_halt
        m.d.comb += self.rvfi.halt.eq(0)

        # rvfi_mode
        m.d.comb += self.rvfi.mode.eq(3)

        # rvfi_ixl
        m.d.comb += self.rvfi.ixl.eq(1)

        return m
