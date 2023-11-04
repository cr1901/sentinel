from amaranth import Signal, Module, Cat, C, Mux
from amaranth.lib.wiring import Component, Signature, Out, In, connect, \
    flipped
from amaranth_soc import wishbone

from .top import Top
from .alu import ALU
from .control import Control
from .csr import MCause
from .datapath import CSRFile
from .decode import OpcodeType
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
            "rvfi": Out(self.rvfi_sig),
            "irq": In(1)
        })

    def __init__(self):
        self.rvfi_sig = RVFISignature
        self.csrs = Signature({})

        self.add_csr("mscratch")
        self.add_csr("mcause")
        # self.add_csr("misa")
        self.rvfi_sig.members["csr"] = Out(self.csrs)

        super().__init__()
        self.cpu = Top(formal=True)

    def add_csr(self, name):
        csr_ports = Signature({
            "rmask": Out(32),
            "wmask": Out(32),
            "rdata": Out(32),
            "wdata": Out(32)
        })

        self.csrs.members[name] = Out(csr_ports)

    def elaborate(self, plat):
        m = Module()

        m.submodules.cpu = self.cpu

        connect(m, self.cpu.bus, flipped(self.bus))
        m.d.comb += self.cpu.irq.eq(self.irq)

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
        m.d.comb += dat_w_mux.eq(Mux(self.cpu.datapath.gp.ctrl.reg_write &
                                     (self.cpu.control.csr.op !=
                                      CSROp.WRITE_CSR),
                                     self.cpu.datapath.regfile.dat_w,
                                     dat_w_reg))
        with m.If(self.cpu.datapath.gp.ctrl.reg_write &
                  (self.cpu.control.csr.op != CSROp.WRITE_CSR)):
            m.d.sync += dat_w_reg.eq(self.cpu.datapath.regfile.dat_w)

        with m.If(committed_to_insn):
            with m.If(in_init):
                # There is nothing to pipeline/interleave, so wait for first
                # insn to be fetched, and then process it before declaring
                # valid.
                m.d.sync += in_init.eq(0)
            with m.Elif(self.rvfi.trap):
                m.d.comb += self.rvfi.valid.eq(1)
                m.d.sync += [
                    self.rvfi.order.eq(self.rvfi.order + 1),
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

            # For an instruction that writes no rd register, this output must
            # always be zero.
            with m.If((self.cpu.decode.opcode == OpcodeType.BRANCH) |
                      (self.cpu.decode.opcode == OpcodeType.MISC_MEM) |
                      (self.cpu.decode.opcode == OpcodeType.STORE)):
                m.d.sync += self.rvfi.rd_addr.eq(0)

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

            # https://github.com/YosysHQ/riscv-formal/blob/a5443540f965cc948c5cf63321c405474f34ced3/docs/rvfi.md#integer-register-readwrite  # noqa: E501
            # "This output must be zero when rd is zero."
            with m.If(self.rvfi.rd_addr == 0):
                m.d.comb += self.rvfi.rd_wdata.eq(0)

            # Prepare to latch read data for the incoming insn, since the read
            # ports are synchronous (I don't know if it's safe to have
            # simulated async read and sync read ports on the same memory).
            m.d.comb += [
                rs1_port.en.eq(1),
                rs2_port.en.eq(1),
                rs1_port.addr.eq(self.cpu.decode.rs1),
                rs2_port.addr.eq(self.cpu.decode.rs2)
            ]

            # If either mask is non-zero, and the insn is not a load or store,
            # MEM_RDATA and MEM_WDATA need to match:
            # https://github.com/YosysHQ/riscv-formal/blob/a5443540f965cc948c5cf63321c405474f34ced3/checks/rvfi_insn_check.sv#L188-L191
            # I cannot promise this condition holds, so set the masks to 0
            # by default.
            m.d.sync += [
                self.rvfi.mem_rmask.eq(0),
                self.rvfi.mem_wmask.eq(0)
            ]

        with m.If(just_committed_to_insn):
            # Get data from last cycle. If we ever get insns that retire in
            # 2 cycles, then this will need to be muxed like RD_WDATA.
            m.d.sync += [
                self.rvfi.rs1_rdata.eq(rs1_port.data),
                self.rvfi.rs2_rdata.eq(rs2_port.data)
            ]

        # Will be reset every time we commit to a new insn. But should be
        # overridden if there's an exception during the commit cycle.
        with m.If(self.cpu.rvfi.exception):
            m.d.sync += self.rvfi.trap.eq(1)

        # Non-insn memory accesses.
        with m.If(~self.cpu.control.insn_fetch & self.cpu.control.mem_req &
                  self.cpu.bus.ack):
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

        # rvfi_halt
        m.d.comb += self.rvfi.halt.eq(0)

        # rvfi_mode
        m.d.comb += self.rvfi.mode.eq(3)

        # rvfi_ixl
        m.d.comb += self.rvfi.ixl.eq(1)

        # CSRS
        # MSCRATCH
        m.submodules.mscratch = mscratch_port = self.cpu.datapath.regfile.mem.read_port()  # noqa: E501
        m.submodules.mcause = mcause_port = self.cpu.datapath.regfile.mem.read_port()  # noqa: E501
        m.d.comb += [
            mscratch_port.addr.eq(CSRFile.MSCRATCH + 32),
            mcause_port.addr.eq(CSRFile.MCAUSE + 32),
            self.rvfi.csr.mscratch.rmask.eq(-1),
            self.rvfi.csr.mscratch.wmask.eq(-1),
            self.rvfi.csr.mscratch.rdata.eq(mscratch_port.data),
            self.rvfi.csr.mcause.rmask.eq(-1),
            self.rvfi.csr.mcause.wmask.eq(-1),
            self.rvfi.csr.mcause.rdata.eq(mcause_port.data),
            # self.rvfi.csr.misa.rmask.eq(-1),
            # self.rvfi.csr.misa.wmask.eq(-1),
            # self.rvfi.csr.misa.rdata.eq(0),
            # self.rvfi.csr.misa.wdata.eq(0),
        ]

        # By default, don't output CSR data
        m.d.comb += [
            mscratch_port.en.eq(0),
            mcause_port.en.eq(0),
        ]

        with m.If(self.cpu.control.csr.op == CSROp.READ_CSR):
            with m.Switch(self.cpu.datapath.csr.adr_r):
                with m.Case(CSRFile.MSCRATCH):
                    m.d.comb += mscratch_port.en.eq(1)
                with m.Case(CSRFile.MCAUSE):
                    m.d.comb += mcause_port.en.eq(1)

        with m.If(self.cpu.control.csr.op == CSROp.WRITE_CSR):
            with m.Switch(self.cpu.datapath.csr.adr_w):
                with m.Case(CSRFile.MSCRATCH):
                    m.d.sync += self.rvfi.csr.mscratch.wdata.eq(
                        self.cpu.datapath.csr.dat_w)
                with m.Case(CSRFile.MCAUSE):
                    m.d.sync += self.rvfi.csr.mcause.wdata.eq(
                        self.cpu.datapath.csr.dat_w)

        return m
