"""Components for interfacing Sentinel to external verification tools."""

from amaranth import Signal, Module, Mux
from amaranth.lib.wiring import Component, Signature, Out, In, connect, \
    flipped
from amaranth_soc import wishbone

from .top import Top
from .datapath import CSRFile
from .ucodefields import CSROp


class FormalTop(Component):
    r"""Sentinel CPU RVFI Harness.

    .. todo::
        As mentioned :attr:`previously <sentinel.top.Top.rvfi>`,
        :class:`FormalTop` does not connect to the rest of Sentinel via a
        well-defined interface.

        It relies directly on many :class:`sentinel.top.Top` internal signals
        that I would rather be exposed via an
        :doc:`Interface <amaranth:stdlib/wiring>`, but progress has been slow.
        This includes hardcoding microcode addresses constants as class
        attributes.

        I'm deferring describing how this module works internally until I clean
        it up. Fortunately, I don't think it's not exceptionally difficult to
        follow in its current state. Cleanup mostly consists of:

        * Fleshing out the aforementioned interface started in
          :attr:`sentinel.top.Top.rvfi`.
        * Refactoring the implicit state machine from the combination of
          ``in_init``, ``committed_to_insn``, and ``just_committed_to_insn``
          into an explicit one.

    Attributes
    ----------
    bus: Out(wishbone.Signature)
        A :ref:`forwarded <amaranth:wiring-forwarding>` copy of
        :attr:`sentinel.top.Top.bus`.

    irq: In(1)
        A :ref:`forwarded <amaranth:wiring-forwarding>` copy of
        :attr:`sentinel.top.Top.irq`.

    rvfi: Out(Signature)
        Signature :class:`~amaranth.lib.wiring.Member` implementing the
        `RISC-V Formal Interface <https://github.com/YosysHQ/riscv-formal/blob/main/docs/rvfi.md>`__.

        When exported to Verilog, Amaranth will generate its own names for
        ports, and the won't necessarily match the RISC-V Formal Interface
        names in the linked document. As of Amaranth 0.5.4, I use the following
        Verilog macros to forward the exported :class:`FormalTop` port names to
        RISC-V Formal IP ports:

        .. code-block:: verilog

            `define RVFI_AMARANTH_PORT(suff) .rvfi__``suff(rvfi_``suff)
            `define RVFI_CSR_AMARANTH_PORTS(csr) \
                .rvfi__csr__``csr``__rmask(rvfi_csr_``csr``_rmask),       \
                .rvfi__csr__``csr``__wmask(rvfi_csr_``csr``_wmask),       \
                .rvfi__csr__``csr``__rdata(rvfi_csr_``csr``_rdata),       \
                .rvfi__csr__``csr``__wdata(rvfi_csr_``csr``_wdata)

        Its :class:`~amaranth.lib.wiring.Signature` looks like the following:

        .. testcode::
            :hide:

            import sentinel.formal
            print(sentinel.formal.FormalTop().rvfi.signature)

        .. todo::

            Fix goofy formatting, currently (1/11/2025) a
            `side-effect <https://stackoverflow.com/a/17640475>`_ of how
            ``NORMALIZE_WHITESPACE`` in :mod:`python:doctest` works.

        .. testoutput::
            :options: +NORMALIZE_WHITESPACE

            Signature({'valid': Out(1),
                'order': Out(64),
                'insn': Out(32),
                'trap': Out(1),
                'halt': Out(1),
                'intr': Out(1),
                'mode': Out(2),
                'ixl': Out(2),
                'rs1_addr': Out(5),
                'rs2_addr': Out(5),
                'rs1_rdata': Out(32),
                'rs2_rdata': Out(32),
                'rd_addr': Out(5),
                'rd_wdata': Out(32),
                'pc_rdata': Out(32),
                'pc_wdata': Out(32),
                'mem_addr': Out(32),
                'mem_rmask': Out(4),
                'mem_wmask': Out(4),
                'mem_rdata': Out(32),
                'mem_wdata': Out(32),
                'csr': Out(Signature({'mscratch': Out(Signature({'rmask': Out(32),
                        'wmask': Out(32),
                        'rdata': Out(32),
                        'wdata': Out(32)})),
                    'mcause': Out(Signature({'rmask': Out(32),
                        'wmask': Out(32),
                        'rdata': Out(32),
                        'wdata': Out(32)})),
                    'mip': Out(Signature({'rmask': Out(32),
                        'wmask': Out(32),
                        'rdata': Out(32),
                        'wdata': Out(32)})),
                    'mie': Out(Signature({'rmask': Out(32),
                        'wmask': Out(32),
                        'rdata': Out(32),
                        'wdata': Out(32)})),
                    'mstatus': Out(Signature({'rmask': Out(32),
                        'wmask': Out(32),
                        'rdata': Out(32),
                        'wdata': Out(32)})),
                    'mtvec': Out(Signature({'rmask': Out(32),
                        'wmask': Out(32),
                        'rdata': Out(32),
                        'wdata': Out(32)})),
                    'mepc': Out(Signature({'rmask': Out(32),
                        'wmask': Out(32),
                        'rdata': Out(32),
                        'wdata': Out(32)})),
                    'misa': Out(Signature({'rmask': Out(32),
                        'wmask': Out(32),
                        'rdata': Out(32),
                        'wdata': Out(32)})),
                    'mvendorid': Out(Signature({'rmask': Out(32),
                        'wmask': Out(32),
                        'rdata': Out(32),
                        'wdata': Out(32)})),
                    'marchid': Out(Signature({'rmask': Out(32),
                        'wmask': Out(32),
                        'rdata': Out(32),
                        'wdata': Out(32)})),
                    'mimpid': Out(Signature({'rmask': Out(32),
                        'wmask': Out(32),
                        'rdata': Out(32),
                        'wdata': Out(32)})),
                    'mhartid': Out(Signature({'rmask': Out(32),
                        'wmask': Out(32),
                        'rdata': Out(32),
                        'wdata': Out(32)})),
                    'mconfigptr': Out(Signature({'rmask': Out(32),
                        'wmask': Out(32),
                        'rdata': Out(32),
                        'wdata': Out(32)})),
                    'mstatush': Out(Signature({'rmask': Out(32),
                        'wmask': Out(32),
                        'rdata': Out(32),
                        'wdata': Out(32)})),
                    'mcountinhibit': Out(Signature({'rmask': Out(32),
                        'wmask': Out(32),
                        'rdata': Out(32),
                        'wdata': Out(32)})),
                    'mtval': Out(Signature({'rmask': Out(32),
                        'wmask': Out(32),
                        'rdata': Out(32),
                        'wdata': Out(32)})),
                    'mcycle': Out(Signature({'rmask': Out(64),
                        'wmask': Out(64),
                        'rdata': Out(64),
                        'wdata': Out(64)})),
                    'minstret': Out(Signature({'rmask': Out(64),
                        'wmask': Out(64),
                        'rdata': Out(64),
                        'wdata': Out(64)})),
                    'mhpmcounter3': Out(Signature({'rmask': Out(64),
                        'wmask': Out(64),
                        'rdata': Out(64),
                        'wdata': Out(64)})),
                    'mhpmevent3': Out(Signature({'rmask': Out(32),
                        'wmask': Out(32),
                        'rdata': Out(32),
                        'wdata': Out(32)}))}))})

    """  # noqa: E501, RUF100

    # FIXME: Harcoded microcode addresses. Do not rely on.
    _CHECK_INT_ADDR = 1
    _CSR_DECODE_VALIDITY_ADDR = 0x24
    _EXCEPTION_HANDLER_ADDR = 240

    def __init__(self):
        rvfi_sig = {
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
        }

        csrs = {}
        for name in ("mscratch", "mcause", "mip", "mie", "mstatus", "mtvec",
                     "mepc", "misa", "mvendorid", "marchid", "mimpid",
                     "mhartid", "mconfigptr", "mstatush", "mcountinhibit",
                     "mtval", "mcycle", "minstret", "mhpmcounter3",
                     "mhpmevent3"):
            # Per RVFI: Always 64-bit wide, even on pure RV32 processors.
            if name in ("mcycle", "minstret", "mhpmcounter3"):
                csr_ports = Signature({
                    "rmask": Out(64),
                    "wmask": Out(64),
                    "rdata": Out(64),
                    "wdata": Out(64)
                })
            else:
                csr_ports = Signature({
                    "rmask": Out(32),
                    "wmask": Out(32),
                    "rdata": Out(32),
                    "wdata": Out(32)
                })

            csrs[name] = Out(csr_ports)
        rvfi_sig["csr"] = Out(Signature(csrs))

        sig = {
            "bus": Out(wishbone.Signature(addr_width=30, data_width=32,
                                          granularity=8)),
            "rvfi": Out(Signature(rvfi_sig)),
            "irq": In(1)
        }

        super().__init__(sig)
        self.cpu = Top(formal=True)

    def elaborate(self, plat):  # noqa: D102
        m = Module()

        m.submodules.cpu = self.cpu

        connect(m, self.cpu.bus, flipped(self.bus))
        m.d.comb += self.cpu.irq.eq(self.irq)

        # rs1/rs2_data helpers.
        w_port = self.cpu.datapath.regfile.w_port
        rs1_port = self.cpu.datapath.regfile.mem.read_port(transparent_for=(w_port,))  # noqa: E501
        rs2_port = self.cpu.datapath.regfile.mem.read_port(transparent_for=(w_port,))  # noqa: E501

        # By default, don't output new data on the ports.
        m.d.comb += [
            rs1_port.en.eq(0),
            rs2_port.en.eq(0),
        ]

        # Insn retirement helpers.
        in_init = Signal(1, init=1)
        committed_to_insn = Signal()
        just_committed_to_insn = Signal()
        # If we fetched an insn and the bus just ACK'ed, the next cycle the
        # microcode will check for interrupts and start processing the
        # insn. Therefore this cycle can be considered retirement.
        m.d.comb += committed_to_insn.eq(self.cpu.control.mem.insn_fetch &
                                         self.cpu.bus.ack &
                                         (self.cpu.control.ucoderom.addr ==
                                          self._CHECK_INT_ADDR))
        m.d.sync += just_committed_to_insn.eq(committed_to_insn)

        # RVFI RD_DATAW helpers.
        dat_w_mux = Signal.like(self.cpu.datapath.gp.dat_w)
        dat_w_reg = Signal.like(self.cpu.datapath.gp.dat_w)
        m.d.comb += dat_w_mux.eq(Mux(self.cpu.datapath.gp.ctrl.reg_write &
                                     (self.cpu.control.csr.ctrl.op !=
                                      CSROp.WRITE_CSR),
                                     self.cpu.datapath.gp.dat_w,
                                     dat_w_reg))
        with m.If(self.cpu.datapath.gp.ctrl.reg_write &
                  (self.cpu.control.csr.ctrl.op != CSROp.WRITE_CSR)):
            m.d.sync += dat_w_reg.eq(self.cpu.datapath.gp.dat_w)

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
                self.rvfi.insn.eq(self.cpu.rvfi.decode.insn),
                self.rvfi.rs1_addr.eq(self.cpu.rvfi.decode.rs1),
                self.rvfi.rs2_addr.eq(self.cpu.rvfi.decode.rs2),
                self.rvfi.rd_addr.eq(self.cpu.rvfi.decode.rd),
                # The just-retired insn's PC. Overwrite with the fetched PC,
                # the nominal PC_WDATA.
                self.rvfi.pc_rdata.eq(self.cpu.datapath.pc.dat_r << 2),
            ]

            # For an instruction that writes no rd register, this output must
            # always be zero.
            with m.If(~self.cpu.rvfi.decode.rd_valid):
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
                rs1_port.addr.eq(self.cpu.rvfi.decode.rs1),
                rs2_port.addr.eq(self.cpu.rvfi.decode.rs2)
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
        with m.If(~self.cpu.control.mem.insn_fetch & self.cpu.control.mem.req &
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
        mscratch_port = self.cpu.datapath.regfile.mem.read_port(transparent_for=(w_port,))  # noqa: E501
        mcause_port = self.cpu.datapath.regfile.mem.read_port(transparent_for=(w_port,))  # noqa: E501
        mtvec_port = self.cpu.datapath.regfile.mem.read_port(transparent_for=(w_port,))  # noqa: E501
        mepc_port = self.cpu.datapath.regfile.mem.read_port(transparent_for=(w_port,))  # noqa: E501
        m.d.comb += [
            mscratch_port.addr.eq(CSRFile.MSCRATCH + 32),
            mcause_port.addr.eq(CSRFile.MCAUSE + 32),
            mtvec_port.addr.eq(CSRFile.MTVEC + 32),
            mepc_port.addr.eq(CSRFile.MEPC + 32),
            self.rvfi.csr.mscratch.rmask.eq(-1),
            self.rvfi.csr.mscratch.wmask.eq(-1),
            self.rvfi.csr.mscratch.rdata.eq(mscratch_port.data),
            self.rvfi.csr.mcause.rmask.eq(-1),
            self.rvfi.csr.mcause.wmask.eq(-1),
            self.rvfi.csr.mcause.rdata.eq(mcause_port.data),
            self.rvfi.csr.mip.rmask.eq(-1),
            self.rvfi.csr.mip.wmask.eq(-1),
            self.rvfi.csr.mie.rmask.eq(-1),
            self.rvfi.csr.mie.wmask.eq(-1),
            self.rvfi.csr.mstatus.rmask.eq(-1),
            self.rvfi.csr.mstatus.wmask.eq(-1),
            self.rvfi.csr.mtvec.rmask.eq(-1),
            self.rvfi.csr.mtvec.wmask.eq(-1),
            self.rvfi.csr.mtvec.rdata.eq(mtvec_port.data),
            self.rvfi.csr.mepc.rmask.eq(-1),
            self.rvfi.csr.mepc.wmask.eq(-1),
            self.rvfi.csr.mepc.rdata.eq(mepc_port.data),
        ]

        # Reads are always valid. But if a CSR is being written, we have to
        # hold the previous data, b/c RVFI expects the rdata to be that at
        # the _beginning_ of the insn.
        mscratch_hold_rd = Signal(1)
        mcause_hold_rd = Signal(1)
        mtvec_hold_rd = Signal(1)
        mepc_hold_rd = Signal(1)
        mip_hold_rd = Signal(1)
        mie_hold_rd = Signal(1)
        mstatus_hold_rd = Signal(1)

        # Holding state is reset on an insn-by-insn basis.
        with m.If(committed_to_insn):
            m.d.sync += [
                mscratch_hold_rd.eq(0),
                mcause_hold_rd.eq(0),
                mtvec_hold_rd.eq(0),
                mepc_hold_rd.eq(0),
                mip_hold_rd.eq(0),
                mie_hold_rd.eq(0),
                mstatus_hold_rd.eq(0)
            ]

        m.d.comb += [
            mscratch_port.en.eq(~mscratch_hold_rd),
            mcause_port.en.eq(~mcause_hold_rd),
            mtvec_port.en.eq(~mtvec_hold_rd),
            mepc_port.en.eq(~mepc_hold_rd),
        ]

        with m.If(~mip_hold_rd):
            m.d.sync += self.rvfi.csr.mip.rdata.eq(self.cpu.datapath.csr.mip_r)
        with m.If(~mie_hold_rd):
            m.d.sync += self.rvfi.csr.mie.rdata.eq(self.cpu.datapath.csr.mie_r)
        with m.If(~mstatus_hold_rd):
            m.d.sync += self.rvfi.csr.mstatus.rdata.eq(
                self.cpu.datapath.csr.mstatus_r)

        with m.If(self.cpu.control.csr.ctrl.op == CSROp.WRITE_CSR):
            with m.Switch(self.cpu.datapath.csr.adr):
                with m.Case(CSRFile.MSCRATCH):
                    m.d.sync += [
                        self.rvfi.csr.mscratch.wdata.eq(
                            self.cpu.datapath.csr.dat_w),
                        mscratch_hold_rd.eq(1)
                    ]
                    # Preempt a transparent read.
                    m.d.comb += mscratch_port.en.eq(0)
                with m.Case(CSRFile.MCAUSE):
                    m.d.sync += [
                        self.rvfi.csr.mcause.wdata.eq(
                            self.cpu.datapath.csr.dat_w),
                        mcause_hold_rd.eq(1)
                    ]
                    m.d.comb += mcause_port.en.eq(0)
                with m.Case(CSRFile.MIP):
                    m.d.sync += [
                        self.rvfi.csr.mip.wdata.eq(
                            self.cpu.datapath.csr.dat_w),
                        mip_hold_rd.eq(1)
                    ]
                with m.Case(CSRFile.MIE):
                    m.d.sync += [
                        self.rvfi.csr.mie.wdata.eq(
                            self.cpu.datapath.csr.dat_w),
                        mie_hold_rd.eq(1)
                    ]
                with m.Case(CSRFile.MSTATUS):
                    m.d.sync += [
                        self.rvfi.csr.mstatus.wdata.eq(
                            self.cpu.datapath.csr.dat_w),
                        mstatus_hold_rd.eq(1)
                    ]
                with m.Case(CSRFile.MTVEC):
                    m.d.sync += [
                        self.rvfi.csr.mtvec.wdata.eq(
                            self.cpu.datapath.csr.dat_w),
                        mtvec_hold_rd.eq(1)
                    ]
                    m.d.comb += mtvec_port.en.eq(0)
                with m.Case(CSRFile.MEPC):
                    m.d.sync += [
                        self.rvfi.csr.mepc.wdata.eq(
                            self.cpu.datapath.csr.dat_w),
                        mepc_hold_rd.eq(1)
                    ]
                    m.d.comb += mepc_port.en.eq(0)

        # Read-only zero CSRs
        # Read-only ops are optimized, so we can't inspect the datapath for
        # their values. We'll have to manually construct the expected values
        # and hope for the best.
        csr_addr_shadow = Signal(12)
        csr_op_shadow = Signal(3)
        doing_csr_decode = Signal()

        # sync, since uPC points one ahead of currently executing insn :).
        m.d.sync += doing_csr_decode.eq(self.cpu.control.ucoderom.addr ==
                                        self._CSR_DECODE_VALIDITY_ADDR)
        with m.If(self.cpu.rvfi.decode.do_decode):
            m.d.sync += [
                csr_addr_shadow.eq(self.cpu.rvfi.decode.funct12),
                csr_op_shadow.eq(self.cpu.rvfi.decode.funct3)
            ]

        for addr, csr_name, hiword in [
                (0xF11, "mvendorid", False), (0xF12, "marchid", False),
                (0xF13, "mimpid", False), (0xF14, "mhartid", False),
                (0xF15, "mconfigptr", False), (0x301, "misa", False),
                (0x310, "mstatush", False), (0x343, "mtval", False),
                (0xB00, "mcycle", False), (0xB02, "minstret", False),
                # `define RISCV_FORMAL_CSRWH isn't there for mhpmcounter3...
                # should it be?
                (0xB03, "mhpmcounter3", False), (0xB80, "mcycle", True),
                (0xB82, "minstret", True), (0xB83, "mhpmcounter3", True),
                (0x320, "mcountinhibit", False), (0x323, "mhpmevent3", False)]:
            rvfi_csr = getattr(self.rvfi.csr, csr_name)
            m.d.comb += [
                rvfi_csr.rmask.eq(-1),
                rvfi_csr.wmask.eq(-1),
                rvfi_csr.rdata.eq(0)
            ]

            # 64-bit registers. These are the only regs where we take
            # advantage of masks (to keep the hiword logic in the decode block
            # below easier). Make sure only 32-bits are ever updated at once.
            if csr_name in ("mcycle", "minstret", "mhpmcounter3") and hiword:
                with m.If(csr_addr_shadow == addr):
                    m.d.comb += rvfi_csr.wmask[:32].eq(0)
                    m.d.comb += rvfi_csr.wmask[32:].eq(-1)
                with m.Else():
                    m.d.comb += rvfi_csr.wmask[:32].eq(-1)
                    m.d.comb += rvfi_csr.wmask[32:].eq(0)

            with m.If(doing_csr_decode):
                # RVFI CSRW Check mandates this.
                with m.If(self.cpu.rvfi.exception):
                    m.d.sync += self.rvfi.rd_addr.eq(0)

                with m.If(csr_addr_shadow == addr):
                    with m.If((csr_op_shadow == 1) | ((csr_op_shadow == 2) &
                              (self.rvfi.rs1_addr != 0))):
                        # csrrw/csrrs
                        if hiword:
                            m.d.sync += rvfi_csr.wdata[32:].eq(self.rvfi.rs1_rdata)  # noqa: E501
                        else:
                            m.d.sync += rvfi_csr.wdata[:32].eq(self.rvfi.rs1_rdata)  # noqa: E501
                    with m.Elif((csr_op_shadow == 5) |
                                ((csr_op_shadow == 6) &
                                (self.rvfi.rs1_addr != 0))):
                        # csrrwi/csrrsi
                        if hiword:
                            m.d.sync += rvfi_csr.wdata[32:].eq(self.rvfi.rs1_addr)  # noqa: E501
                        else:
                            m.d.sync += rvfi_csr.wdata[:32].eq(self.rvfi.rs1_addr)  # noqa: E501
                    with m.Else():
                        if hiword:
                            m.d.sync += rvfi_csr.wdata[32:].eq(0)
                        else:
                            m.d.sync += rvfi_csr.wdata[:32].eq(0)

        return m
