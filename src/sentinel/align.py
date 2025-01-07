"""Components to align external data going in/out of the Sentinel Core."""

from amaranth import Signal, Module
from amaranth.lib.wiring import Component, In, Out

from .ucodefields import MemSel, MemExtend, MemReq, InsnFetch


class AddressAlign(Component):
    """Align internal address data before driving external address lines.

    This :class:`~amaranth:amaranth.lib.wiring.Component` is pure combinational
    logic that splits a 32-bit input address for a memory or I/O transfer into
    two parts:

    * A :attr:`30-bit address <wb_adr>` to/from which to write/read 32-bit
      data. This directly drives Wishbone signal ``ADR_O``.
    * :attr:`4 select lines <wb_sel>` which determine which bytes of the 32-bit
      :attr:`write <WriteDataAlign.wb_dat_w>` or
      :attr:`read data <ReadDataAlign.wb_dat_r>` are valid/meaningful for the
      current transfer. These lines directly drive Wishbone signal ``SEL_O``.

    If :attr:`insn_fetch` is asserted:

    * The 30-bit address comes directly from the
      :class:`~sentinel.datapath.ProgramCounter`.
    * All select lines are asserted.

    If :attr:`insn_fetch` is not asserted:

    * The 30-bit address comes from the top 30 bits of :attr:`latched_adr`.
    * The bottom two bits of :attr:`latched_adr` and the :attr:`mem_sel`
      signals calculate the proper select lines to assert (all for a 32-bit
      transfer, top two or bottom two for 16-bit transfers, and one-hot for an
      8-bit transfer).

    For space reasons, :class:`AddressAlign` does *not* qualify
    :attr:`insn_fetch` by the *de-assertion* of
    :data:`~sentinel.ucodefields.WriteMem`, even though an instruction write
    transfer doesn't make really sense.
    """

    #: In(:data:`~sentinel.ucodefields.MemReq`): If set, indicates a memory
    #: transfer over the Wishbone bus is occurring. Outputs are qualified by
    #: this signal.
    mem_req: In(MemReq)
    #: In(MemSel): Select whether to do an 8-bit, 16-bit, or 32-bit read, or
    #: ignore.
    mem_sel: In(MemSel)
    #: In(:data:`~sentinel.ucodefields.InsnFetch`): If set, the current memory
    #: read is an instruction fetch.
    insn_fetch: In(InsnFetch)
    #: Current value of the :class:`~sentinel.datapath.ProgramCounter`, used to
    #: generate :attr:`wb_adr` when :attr:`insn_fetch` is asserted.
    pc: In(30)
    #: Registered address of the memory transfer, latched on a previous
    #: cycle. Raw address before alignment used to generate :attr:`wb_adr` when
    #: and :attr:`wb_sel` when :attr:`insn_fetch` is *not* asserted.
    latched_adr: In(32)
    #: 32-bit aligned address, which directly drives Wishbone ``ADR_O``.
    wb_adr: Out(30)
    #: Data select lines, which qualify which bytes in the 32-bit ``DAT_I`` and
    #: ``DAT_O`` are valid for the current memory transfer. Directly drives
    #: Wishbone ``SEL_O``.
    wb_sel: Out(4)

    def elaborate(self, platform):  # noqa: D102
        m = Module()

        # DataPath.dat_w constantly has traffic. We only want to latch
        # the address once per mem access, and we want it the address to be
        # valid synchronous with ready assertion.
        with m.If(self.mem_req):
            with m.If(self.insn_fetch):
                m.d.comb += [self.wb_adr.eq(self.pc),
                             self.wb_sel.eq(0xf)]
            with m.Else():
                m.d.comb += self.wb_adr.eq(self.latched_adr[2:])

                # TODO: Misaligned accesses
                with m.Switch(self.mem_sel):
                    with m.Case(MemSel.BYTE):
                        with m.If(self.latched_adr[0:2] == 0):
                            m.d.comb += self.wb_sel.eq(1)
                        with m.Elif(self.latched_adr[0:2] == 1):
                            m.d.comb += self.wb_sel.eq(2)
                        with m.Elif(self.latched_adr[0:2] == 2):
                            m.d.comb += self.wb_sel.eq(4)
                        with m.Else():
                            m.d.comb += self.wb_sel.eq(8)
                    with m.Case(MemSel.HWORD):
                        with m.If(self.latched_adr[1] == 0):
                            m.d.comb += self.wb_sel.eq(3)
                        with m.Else():
                            m.d.comb += self.wb_sel.eq(0xc)
                    with m.Case(MemSel.WORD):
                        m.d.comb += self.wb_sel.eq(0xf)

        return m


class ReadDataAlign(Component):
    """Align external read data before latching internally.

    This :class:`~amaranth:amaranth.lib.wiring.Component` is pure combinational
    logic that aligns and then extends read data to 32-bits:

    * If :attr:`mem_sel` is :attr:`~sentinel.ucodefields.MemSel.BYTE`, pass
      any of the 4 bytes of :attr:`wb_dat_r` to an data extension circuit,
      depending on :attr:`address <latched_adr>` alignment. Then
      either zero or sign-extend the selected byte to 32-bits, depending on
      :attr:`mem_extend`. Finally, pass the extender output to :attr:`data`.

    * If :attr:`mem_sel` is :attr:`~sentinel.ucodefields.MemSel.HWORD`, pass
      either the low 16-bits or high 16-bits of :attr:`wb_dat_r` to an data
      extension circuit, depending on :attr:`address <latched_adr>`
      alignment. Then, either zero or sign-extend these 16-bits to 32-bits,
      depending on :attr:`mem_extend`. Finally, pass the extender output
      to :attr:`data`.

    * If :attr:`mem_sel` is :attr:`~sentinel.ucodefields.MemSel.WORD`, pass
      :attr:`wb_dat_r` to :attr:`data` unaltered. The extension circuit is
      not used.

    Because I found it to be a size win, I physically implement
    :class:`ReadDataAlign` as part of :class:`sentinel.alu.BSrcMux`; the
    :attr:`sentinel.alu.BSrcMux.dat_r` input feeds directly into
    :class:`ReadDataAlign`.

    :class:`AddressAlign` ensures that the appropriate ``SEL_O`` lines
    are asserted for the read.
    """

    #: In(MemSel): Select whether to do an 8-bit, 16-bit, or 32-bit read, or
    #: ignore.
    mem_sel: In(MemSel)
    #: In(MemExtend): Zero or sign-extend reads of less than 32-bits.
    mem_extend: In(MemExtend)
    #: Registered address from which data will be read, latched on a previous
    #: cycle.
    latched_adr: In(32)
    #: Unregistered raw input data, directly from Wishbone ``DAT_I``.
    wb_dat_r: In(32)
    #: Aligned and extended data output.
    data: Out(32)

    def elaborate(self, platform):  # noqa: D102
        m = Module()

        selected_dat = Signal.like(self.wb_dat_r)

        with m.Switch(self.mem_sel):
            with m.Case(MemSel.BYTE):
                with m.If(self.latched_adr[0:2] == 0):
                    m.d.comb += selected_dat.eq(self.wb_dat_r[0:8])
                with m.Elif(self.latched_adr[0:2] == 1):
                    m.d.comb += selected_dat.eq(self.wb_dat_r[8:16])
                with m.Elif(self.latched_adr[0:2] == 2):
                    m.d.comb += selected_dat.eq(self.wb_dat_r[16:24])
                with m.Else():
                    m.d.comb += selected_dat.eq(self.wb_dat_r[24:])

                with m.If(self.mem_extend == MemExtend.SIGN):
                    m.d.comb += self.data.eq(selected_dat[0:8].as_signed())
                with m.Else():
                    m.d.comb += self.data.eq(selected_dat[0:8])
            with m.Case(MemSel.HWORD):
                with m.If(self.latched_adr[1] == 0):
                    m.d.comb += selected_dat.eq(self.wb_dat_r[0:16])
                with m.Else():
                    m.d.comb += selected_dat.eq(self.wb_dat_r[16:])

                with m.If(self.mem_extend == MemExtend.SIGN):
                    m.d.comb += self.data.eq(selected_dat[0:16].as_signed())
                with m.Else():
                    m.d.comb += self.data.eq(selected_dat[0:16])
            with m.Case(MemSel.WORD):
                m.d.comb += self.data.eq(self.wb_dat_r)

        return m


class WriteDataAlign(Component):
    """Align internal write data before sending to external peripherals.

    This :class:`~amaranth:amaranth.lib.wiring.Component` is pure combinational
    logic that aligns write data to an appropriate offset within 32-bits:

    * If :attr:`mem_sel` is :attr:`~sentinel.ucodefields.MemSel.BYTE`, move the
      low byte of :attr:`data` to one of the 4 constituent bytes of
      :attr:`wb_dat_w`, depending on :attr:`address <latched_adr>`
      alignment. The other bytes of :attr:`wb_dat_w` are invalid.

    * If :attr:`mem_sel` is :attr:`~sentinel.ucodefields.MemSel.HWORD`, the
      low 16-bits :attr:`data` move into either the low 16-bits or high
      16-bits of :attr:`wb_dat_w`, depending on :attr:`address <latched_adr>`
      alignment. The other 16-bits of :attr:`wb_dat_w` is invalid.

    * If :attr:`mem_sel` is :attr:`~sentinel.ucodefields.MemSel.WORD`, pass
      :attr:`data` to :attr:`wb_dat_w` unaltered. All bits are valid.

    Since not all 32-bits of ``DAT_O`` will necessarily be valid for a given
    write, :class:`AddressAlign` ensures that the appropriate ``SEL_O`` lines
    are asserted for the write.
    """

    #: In(MemSel): Select whether to do an 8-bit, 16-bit, or 32-bit write, or
    #: ignore.
    mem_sel: In(MemSel)
    #: Registered address to which data will be written, latched on a previous
    #: cycle.
    latched_adr: In(32)
    #: Data to be written externally, before alignment.
    data: In(32)
    #: Aligned data to be :data:`latched <sentinel.ucodefields.LatchData>`,
    #: which then drives Wishbone ``DAT_O``.
    wb_dat_w: Out(32)

    def elaborate(self, platform):  # noqa: D102
        m = Module()

        # TODO: Misaligned accesses
        with m.Switch(self.mem_sel):
            with m.Case(MemSel.BYTE):
                with m.If(self.latched_adr[0:2] == 0):
                    m.d.comb += self.wb_dat_w[0:8].eq(self.data[0:8])
                with m.Elif(self.latched_adr[0:2] == 1):
                    m.d.comb += self.wb_dat_w[8:16].eq(self.data[0:8])
                with m.Elif(self.latched_adr[0:2] == 2):
                    m.d.comb += self.wb_dat_w[16:24].eq(self.data[0:8])
                with m.Else():
                    m.d.comb += self.wb_dat_w[24:].eq(self.data[0:8])
            with m.Case(MemSel.HWORD):
                with m.If(self.latched_adr[1] == 0):
                    m.d.comb += self.wb_dat_w[0:16].eq(self.data[0:16])
                with m.Else():
                    m.d.comb += self.wb_dat_w[16:].eq(self.data[0:16])
            with m.Case(MemSel.WORD):
                m.d.comb += self.wb_dat_w.eq(self.data)

        return m
