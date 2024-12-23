"""Top-Level Module for Amaranth Components of Sentinel CPU."""

from amaranth import Signal, Module
from amaranth.lib.wiring import Component, Signature, Out, In, connect, flipped
from amaranth_soc import wishbone

from .alu import ALU, ASrcMux, BSrcMux
from .align import AddressAlign, WriteDataAlign
from .control import Control
from .datapath import DataPath, DataPathSrcMux  # noqa: F401
from .decode import Decode
from .exception import ExceptionRouter
from .ucodefields import RegRSel, RegWSel, CSRSel


class Top(Component):
    """The Sentinel CPU Top-Level.

    The Sentinel CPU top-level provides an `interface <amaranth:wiring>`_ to
    a `Wishbone Classic <https://cdn.opencores.org/downloads/wbspec_b4.pdf>`_
    bus and Interrupt ReQuest (IRQ) signal. Optionally, one may generate extra
    signals which are used for verifying core functionality using the
    `RISC-V Formal Interface <https://github.com/YosysHQ/riscv-formal/blob/main/docs/rvfi.md>`_
    (RVFI).

    Sentinel uses a *single* clock domain, called ``sync``
    `by convention <https://amaranth-lang.org/docs/amaranth/latest/guide.html#control-domains>`_.
    On the first cycle after reset is de-asserted, Sentinel begins execution
    at address ``0``.

    The Wishbone bus provides your typical address, data, and control lines
    for transferring data to and from the CPU. Sentinel only support Wishbone
    Classic Single Xfers. Specifically, when ``CYC`` and ``STB`` are both
    asserted ``1`` on a given clock cycle, the following holds:

    * If ``WE`` is asserted, Sentinel wants to write data over its bus to
      peripherals on its ``DAT_W`` lines. Any byte in ``DAT_W`` where ``SEL``
      is *also* asserted is valid data. Sentinel will wait for ``ACK`` to be
      asserted.
    * If ``WE`` is *not* asserted, Sentinel wants to read data from a
      peripheral over its ``DAT_R`` lines. Peripherals should ensure that any
      byte in ``DAT_R`` where ``SEL`` is *also* asserted is valid data before
      asserting ``ACK``.
    * When ``ACK`` is sent to Sentinel on a given clock cycle, Sentinel will
      deassert ``CYC`` and ``STB`` on the next cycle, for at least one cycle.

    At present (12/3/2024), I could not find good opportunities in the
    microcode program to try Block Xfers without potentially
    `violating <https://github.com/fossi-foundation/wishbone/issues/26>`_ the
    spec.

    The IRQ line triggers Machine External Interrupts when asserted (``1``)-
    i.e. it is level-triggered. For any peripherals, devices, etc that can
    assert an IRQ, the user must provide software, hardware, or a combination
    to *also* deassert their IRQ logic upon acknowledgement from the CPU. The
    Machine Software and Machine Timer interrupt lines are not presently
    implemented.

    .. todo::

        Seeing that it's memory-mapped, there should probably be provisions for
        a user-supplied Machine Timer.

    Sentinel directly reads the IRQ line in two related, but distinct,
    scenarios:

    * An instruction wants to read the Machine Interrupt Pending (``MIP``)
      register. In this case, Sentinel will directly latch the value of the IRQ
      line into ``MIP``'s Machine External Interrupt Pending (``MEIP``) bit
      on the next positive edge of the ``sync`` clock domain.
    * The microcode is :class:`querying <sentinel.ucodefields.ExceptCtl>`
      exceptions from
      :attr:`the decoder <sentinel.ucodefields.ExceptCtl.LATCH_DECODER>`. In
      this case, several :mod:`control Components <sentinel.control>` and
      the ``MCAUSE`` register depend on the sampled value of the IRQ line
      on the next positive edge of ``sync``.

    To `ensure <https://www.eetimes.com/understanding-clock-domain-crossing-issues/>`_
    that all internal components of Sentinel see the same value of the IRQ line
    on a given clock cycle, a user must place their own :class:`synchronization
    <amaranth:amaranth.lib.cdc.FFSynchronizer>` logic before the IRQ input if
    interrupt sources can be triggerred asynchronously to ``sync``.

    See the :ref:`CSRs <csrs>` section for more information on exception
    handling (including interrupts).

    Parameters
    ----------
    formal: bool
        The Wishbone bus and IRQ line alone don't give enough information to
        properly use the `RISC-V Formal Interface <https://github.com/YosysHQ/riscv-formal/blob/main/docs/rvfi.md>`__
        to verify core properties. If ``True``, Sentinel will gain an extra
        ``rvfi`` port :class:`~amaranth:amaranth.lib.wiring.Member` with
        signals required to implement RVFI.

        As RVFI is meant for verification, the ``rvfi``
        :class:`~amaranth:amaranth.lib.wiring.Member` is not meant to be used
        in a synthesized design. It is best to leave this option disabled
        unless you are using :class:`Top` in conjunction with
        :class:`FormalTop`.

    Attributes
    ----------
    formal: bool
        If ``True``, ``rvfi`` :class:`~amaranth:amaranth.lib.wiring.Member` is
        present.

    bus: Out(wishbone.Signature)
        Wishbone Classic Bus.

        Connect your memory and I/O to this bus.

    irq: In(1)
        Interrupt Request Line.

        External peripherals signal they need attention when this line is high.

    rvfi: Out(Signature)
        Internal connections required for implementing the
        `RISC-V Formal Interface <https://github.com/YosysHQ/riscv-formal/blob/main/docs/rvfi.md>`__

        The signature is of the form

        .. code-block::

            Out(Signature({
                    "exception": Out(1),
                    "decode": Out(self.decode.rvfi.signature)
            })

        where:

        * ``exception``: Asserted if an exception occurred this cycle.
        * ``decode``: Forwarded RVFI signals from
          :class:`sentinel.decode.Decode`.

        .. _formal-todo:

        .. todo::

            Right now, the formal harness tends to directly "reach" into
            :class:`Top`
            and :class:`Components <amaranth:amaranth.lib.wiring.Component>`
            to read the appropriate signals.

            I would prefer encapsulation via an explicity ``rvfi`` port
            :class:`~amaranth:amaranth.lib.wiring.Member`, but this process
            `has been slow <https://github.com/cr1901/sentinel/commit/1304842fb5f9be6c25c4c85d44863e849a45e481>`_.
            I will wait to document until this interface :class:`~amaranth:amaranth.lib.wiring.Member`
            is more stable.

    alu: sentinel.alu.ALU
        ..
            Arithmetic Logic Unit
            :class:`~amaranth:amaranth.lib.wiring.Component`

    addr_align: sentinel.align.AddressAlign
        ..
            Address Alignment :class:`~amaranth:amaranth.lib.wiring.Component`

    a_src: sentinel.alu.ASrcMux

    b_src: sentinel.alu.BSrcMux

    control: sentinel.control.Control

    datapath: sentinel.datapath.DataPath

    decode: sentinel.decode.Decode

    exception_router: sentinel.exception.ExceptionRouter

    wdata_align: sentinel.align.WriteDataAlign
    """  # noqa: E501, RUF100

    def __init__(self, *, formal=False):
        self.formal = formal

        ###

        self.alu = ALU(32)
        self.addr_align = AddressAlign()
        self.a_src = ASrcMux()
        self.b_src = BSrcMux()
        self.control = Control()
        self.datapath = DataPath(formal=formal)
        self.decode = Decode(formal=formal)
        # self.d_src = DataPathSrcMux()
        self.exception_router = ExceptionRouter()
        self.wdata_align = WriteDataAlign()

        sig = {
                "bus": Out(wishbone.Signature(addr_width=30, data_width=32,
                                              granularity=8)),
                "irq": In(1)
        }
        if self.formal:
            sig["rvfi"] = Out(Signature({
                    "exception": Out(1),
                    "decode": Out(self.decode.rvfi.signature)
            }))

        super().__init__(sig)

    def elaborate(self, platform):  # noqa: D102
        m = Module()

        m.submodules.alu = self.alu
        m.submodules.addr_align = self.addr_align
        m.submodules.a_src = self.a_src
        m.submodules.b_src = self.b_src
        m.submodules.control = self.control
        m.submodules.datapath = self.datapath
        m.submodules.decode = self.decode
        m.submodules.exception_router = self.exception_router
        m.submodules.wdata_align = self.wdata_align
        # m.submodules.d_src = self.d_src

        # The lone sync logic in Top. They don't fit nicely elsewhere.
        data_adr = Signal.like(self.alu.o)
        write_data = Signal.like(self.bus.dat_w)
        mem_reset_guard = Signal(init=1)

        with m.If(self.control.latch_adr):
            m.d.sync += data_adr.eq(self.alu.o)

        with m.If(self.control.latch_data):
            m.d.sync += write_data.eq(self.wdata_align.wb_dat_w)

        m.d.sync += mem_reset_guard.eq(0)

        # Bus conns
        read_data = Signal.like(self.bus.dat_r)
        mem_ack = Signal()
        irq = Signal()

        m.d.comb += [
            # Stale microcode entry that asserts mem_req might survive reset
            # and then attempt to read/write address 0!
            self.bus.cyc.eq(self.control.mem_req & ~mem_reset_guard),
            self.bus.stb.eq(self.control.mem_req & ~mem_reset_guard),
            self.bus.we.eq(self.control.write_mem),
            self.bus.dat_w.eq(write_data),
            self.bus.adr.eq(self.addr_align.wb_adr),
            self.bus.sel.eq(self.addr_align.wb_sel),
            read_data.eq(self.bus.dat_r),
            mem_ack.eq(self.bus.ack),
            irq.eq(self.irq)
            # self.insn_fetch.eq(self.control.insn_fetch)
        ]

        # ALU conns
        connect(m, self.alu.ctrl, self.control.alu)

        m.d.comb += [
            self.alu.a.eq(self.a_src.data),
            self.a_src.latch.eq(self.control.latch_a),
            self.a_src.sel.eq(self.control.a_src),
            self.a_src.gp.eq(self.datapath.gp.dat_r),
            self.a_src.imm.eq(self.decode.imm),
            self.a_src.alu.eq(self.alu.o),

            self.alu.b.eq(self.b_src.data),
            self.b_src.latch.eq(self.control.latch_b),
            self.b_src.sel.eq(self.control.b_src),
            self.b_src.gp.eq(self.datapath.gp.dat_r),
            self.b_src.imm.eq(self.decode.imm),
            self.b_src.pc.eq(self.datapath.pc.dat_r),
            self.b_src.dat_r.eq(read_data),
            self.b_src.csr_imm.eq(self.decode.src_a),
            self.b_src.csr.eq(self.datapath.csr.dat_r),
            self.b_src.mcause.eq(self.exception_router.out.mcause)
        ]

        # Control/Decode conns
        # Load-bearing Signals that do nothing, but somehow save LUTs...
        req_next = Signal()
        insn_fetch_next = Signal()

        m.d.comb += [
            self.control.opcode.eq(self.decode.opcode),
            self.control.requested_op.eq(self.decode.requested_op),
            # TODO: Spin out into a register of exception sources.
            self.control.exception.eq(self.exception_router.out.exception),
            self.control.mem_valid.eq(mem_ack),

            req_next.eq(self.control.mem_req),
            insn_fetch_next.eq(self.control.insn_fetch),

            self.decode.insn.eq(read_data),
            # Decode begins automatically.
            self.decode.do_decode.eq(self.control.insn_fetch & mem_ack),
        ]

        # DataPath conns
        connect(m, self.datapath.gp.ctrl, self.control.gp)
        connect(m, self.datapath.pc.ctrl, self.control.pc)

        # This is a load-bearing optimization... yes, they must be a Signal of
        # width 6, not 5, and they must directly connect the inline
        # DataPathSrcMux implementation below to the DataPath.
        # No, I don't get it either, and I'm willing to accept the ugliness
        # for now and come back to it later when I'm refreshed.
        reg_r_adr = Signal(6)
        reg_w_adr = Signal(6)
        m.d.comb += [
            self.datapath.gp.dat_w.eq(self.alu.o),
            self.datapath.gp.adr_r.eq(reg_r_adr),
            self.datapath.gp.adr_w.eq(reg_w_adr),
            # FIXME: Compressed insns.
            self.datapath.pc.dat_w.eq(self.alu.o[2:]),
            self.datapath.csr.dat_w.eq(self.alu.o),
            self.datapath.csr.ctrl.exception.eq(self.control.except_ctl),
            self.datapath.csr.mip_w.meip.eq(irq)
        ]

        # Alignment conns
        m.d.comb += [
            self.addr_align.mem_req.eq(self.control.mem_req),
            self.addr_align.mem_sel.eq(self.control.mem_sel),
            self.addr_align.insn_fetch.eq(self.control.insn_fetch),
            self.addr_align.latched_adr.eq(data_adr),
            self.addr_align.pc.eq(self.datapath.pc.dat_r),

            self.b_src.mem_sel.eq(self.control.mem_sel),
            self.b_src.mem_extend.eq(self.control.mem_extend),
            self.b_src.data_adr.eq(data_adr),

            self.wdata_align.mem_sel.eq(self.control.mem_sel),
            self.wdata_align.latched_adr.eq(data_adr),
            self.wdata_align.data.eq(self.alu.o),
        ]

        # Datapath Src Conns
        # FIXME: This should be replaced with the following glue once I
        # figure out why DataPathSrcMux doesn't optimize well:
        # m.d.comb += [
        #     self.d_src.insn_fetch.eq(self.control.insn_fetch),
        #     self.d_src.reg_r_sel.eq(self.control.reg_r_sel),
        #     self.d_src.reg_w_sel.eq(self.control.reg_w_sel),
        #     self.d_src.csr_sel.eq(self.control.csr_sel),
        #     self.d_src.src_a_unreg.eq(self.decode.src_a_unreg),
        #     self.d_src.src_a.eq(self.decode.src_a),
        #     self.d_src.src_b.eq(self.decode.src_b),
        #     self.d_src.dst.eq(self.decode.dst),
        #     self.d_src.csr_encoding.eq(self.decode.csr_encoding),
        #     self.d_src.csr_target.eq(self.control.target[0:4]),

        #     self.datapath.gp.adr_r.eq(self.d_src.reg_r_adr),
        #     self.datapath.gp.adr_w.eq(self.d_src.reg_w_adr),
        #     self.datapath.gp.ctrl.allow_zero_wr.eq(self.d_src.allow_zero_wr),
        #     self.datapath.csr.adr.eq(self.d_src.csr_adr)
        # ]

        # DataPathSrcMux inline implementation. Optimizes much better than the
        # module, especially with the reg_{r,w}_adr intermediate Signals.
        # Doesn't make much sense to me, but whatever...
        with m.Switch(self.control.reg_r_sel):
            with m.Case(RegRSel.INSN_RS1):
                with m.If(self.control.insn_fetch):
                    m.d.comb += reg_r_adr.eq(self.decode.src_a_unreg)
                with m.Else():
                    m.d.comb += reg_r_adr.eq(self.decode.src_a)
            with m.Case(RegRSel.INSN_RS2):
                m.d.comb += reg_r_adr.eq(self.decode.src_b)

        with m.Switch(self.control.reg_w_sel):
            with m.Case(RegWSel.INSN_RD):
                m.d.comb += reg_w_adr.eq(self.decode.dst)
            with m.Case(RegWSel.ZERO):
                m.d.comb += [
                    reg_w_adr.eq(0),
                    self.datapath.gp.ctrl.allow_zero_wr.eq(1)
                ]

        # CSR Op/Address control (data conns taken care above)
        m.d.comb += self.datapath.csr.ctrl.op.eq(self.control.csr.op)
        with m.Switch(self.control.csr_sel):
            with m.Case(CSRSel.INSN_CSR):
                m.d.comb += self.datapath.csr.adr.eq(self.decode.csr_encoding)
            with m.Case(CSRSel.TRG_CSR):
                m.d.comb += self.datapath.csr.adr.eq(self.control.target[0:4])

        # Exception Router sources
        m.d.comb += [
            self.exception_router.src.alu_lo.eq(self.alu.o[0:2]),
            self.exception_router.src.csr.mstatus.eq(
                self.datapath.csr.mstatus_r),
            self.exception_router.src.csr.mip.eq(self.datapath.csr.mip_r),
            self.exception_router.src.csr.mie.eq(self.datapath.csr.mie_r),
            self.exception_router.src.ctrl.mem_sel.eq(self.control.mem_sel),
            self.exception_router.src.ctrl.except_ctl.eq(
                self.control.except_ctl),
            self.exception_router.src.decode.eq(self.decode.exception),
        ]

        if self.formal:
            m.d.comb += self.rvfi.exception.eq(
                self.exception_router.out.exception)
            connect(m, flipped(self.rvfi.decode), self.decode.rvfi)

        return m
