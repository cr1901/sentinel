"""Components to align external data going in/out of the Sentinel Core."""

from amaranth import Elaboratable, Signal, Module, C, Cat
from amaranth.lib.wiring import Component, Signature, In, Out

from .ucodefields import ASrc, BSrc, RegRSel, RegWSel, MemSel, \
    MemExtend, CSRSel


class AddressAlign(Component):
    def __init__(self):
        sig = {
            "mem_req": Out(1),
            "mem_sel": Out(MemSel),
            "insn_fetch": Out(1),
            "pc": Out(30),
            "latched_adr": Out(32),
            "wb_adr": In(30),
            "wb_sel": In(4)
        }
        super().__init__(Signature(sig).flip())

    def elaborate(self, platform):
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
    def __init__(self):
        sig = {
            "mem_sel": Out(MemSel),
            "mem_extend": Out(MemExtend),
            "latched_adr": Out(32),
            "wb_dat_r": Out(32),
            "data": In(32)
        }
        super().__init__(Signature(sig).flip())

    def elaborate(self, platform):
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
    def __init__(self):
        sig = {
            "mem_sel": Out(MemSel),
            "latched_adr": Out(32),
            "data": Out(32),
            "wb_dat_w": In(32),
        }
        super().__init__(Signature(sig).flip())

    def elaborate(self, platform):
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
