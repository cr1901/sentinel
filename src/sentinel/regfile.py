from amaranth import Memory, Module, ClockDomain, ClockSignal, ResetSignal
from amaranth.lib.wiring import Component, Signature, In, Out
from amaranth.utils import log2_int

from .ucoderom import UCodeFieldClasses


def rwport_signature(width, depth, ucode):
    return Signature({
        "addr_a": Out(log2_int(depth)),
        "addr_b": Out(log2_int(depth)),
        "dat_r_a": In(width),
        "dat_r_b": In(width),
        "dat_w": Out(width),  # reuses B port addr
        "rd_en": Out(ucode.RegRead),
        "we": Out(ucode.RegWrite)
    })


class RegFile(Component):
    @property
    def signature(self):
        return rwport_signature(self.width, self.depth, self.ucode)

    def __init__(self, width: int, depth: int, ucode: UCodeFieldClasses):
        self.ucode = ucode
        self.width = width
        self.depth = depth

        super().__init__()
        self.mem = Memory(width=self.width, depth=self.depth)

    def elaborate(self, plat):
        m = Module()
        # FIXME: Convert to negedge once #611 is addressed.
        m.d.domains.negsync = ClockDomain("negsync", clk_edge="pos")

        m.d.comb += [
            ClockSignal("negsync").eq(~ClockSignal("sync")),
            ResetSignal("negsync").eq(ResetSignal("sync")),
        ]

        m.submodules.rdport = rdport = self.mem.read_port(domain="negsync")
        m.submodules.wrport = wrport = self.mem.write_port()

        self.dat_r_a.reset_less = True
        self.dat_r_b.reset_less = True
        m.d.comb += self.dat_r_b.eq(rdport.data)
        with m.Switch(self.rd_en):
            m.d.comb += rdport.en.eq(1)
            with m.Case(self.ucode.RegRead.READ_A):
                m.d.comb += rdport.addr.eq(self.addr_a)
                m.d.sync += [
                    self.dat_r_a.eq(rdport.data),
                ]
            with m.Case(self.ucode.RegRead.READ_B):
                m.d.comb += rdport.addr.eq(self.addr_b)

        m.d.comb += [
            wrport.addr.eq(self.addr_b),
            wrport.data.eq(self.dat_w)
        ]
        with m.If(self.we == self.ucode.RegWrite.WRITE_B):
            m.d.comb += wrport.en.eq(1)

        return m
