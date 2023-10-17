# SoC components. This is more of a "utilities" module.

from bronzebeard.asm import assemble
from amaranth import Module, Memory
from amaranth_soc import wishbone
from amaranth_soc.memory import MemoryMap
from amaranth.lib.wiring import In, Out, Component, Elaboratable, connect, \
    Signature
from amaranth.build import ResourceError
from amaranth.utils import log2_int

from .top import Top


class WBMemory(Component):
    @property
    def signature(self):
        sig = Signature({
            "bus": In(wishbone.Signature(addr_width=log2_int(self.depth) - 2,
                                         data_width=32,
                                         granularity=8)),
        })

        if self.sim:
            sig.members["ctrl"] = Out(Signature({
                "force_ws": Out(1)  # noqa: F821
            }))
        return sig

    def __init__(self, *, sim=False, depth=0x400):
        self.sim = sim
        self.depth = depth
        super().__init__()

    @property
    def init_mem(self):
        return self.mem_contents

    @init_mem.setter
    def init_mem(self, mem):
        self.mem_contents = mem

    def elaborate(self, plat):
        m = Module()
        self.mem = Memory(width=32, depth=self.depth, init=self.mem_contents)
        m.submodules.rdport = rdport = self.mem.read_port(transparent=True)
        m.submodules.wrport = wrport = self.mem.write_port(granularity=8)

        m.d.comb += [
            rdport.addr.eq(self.bus.adr),
            wrport.addr.eq(self.bus.adr),
            self.bus.dat_r.eq(rdport.data),
            wrport.data.eq(self.bus.dat_w),
            rdport.en.eq(self.bus.stb & self.bus.cyc & ~self.bus.we),
        ]

        with m.If(self.bus.stb & self.bus.cyc & self.bus.we):
            m.d.comb += wrport.en.eq(self.bus.sel)

        if self.sim:
            ack_cond = self.bus.stb & self.bus.cyc & ~self.bus.ack & \
                      ~self.ctrl.force_ws
        else:
            ack_cond = self.bus.stb & self.bus.cyc & ~self.bus.ack

        with m.If(ack_cond):
            m.d.sync += self.bus.ack.eq(1)
        with m.Else():
            m.d.sync += self.bus.ack.eq(0)

        return m


class Leds(Component):
    bus: In(wishbone.Signature(addr_width=1, data_width=8, granularity=8))
    leds: Out(8)

    def __init__(self):
        super().__init__()

    def elaborate(self, plat):
        m = Module()

        with m.If(self.bus.stb & self.bus.cyc & self.bus.ack
                  & self.bus.sel[0]):
            m.d.sync += self.leds.eq(self.bus.dat_w)

        with m.If(self.bus.stb & self.bus.cyc & ~self.bus.ack):
            m.d.sync += self.bus.ack.eq(1)
        with m.Else():
            m.d.sync += self.bus.ack.eq(0)

        return m


# Reimplementation of nextpnr-ice40's AttoSoC example (https://github.com/YosysHQ/nextpnr/tree/master/ice40/smoketest/attosoc),  # noqa: E501
# to exercise attaching Sentinel to amaranth-soc's wishbone components.
class AttoSoC(Elaboratable):
    def __init__(self, *, sim=False, depth=0x400):
        self.cpu = Top()
        self.mem = WBMemory(sim=sim, depth=depth)
        self.leds = Leds()

    @property
    def rom(self):
        return self.mem.init_mem

    @rom.setter
    def rom(self, source_or_list):
        if isinstance(source_or_list, str):
            insns = assemble(source_or_list)
            self.mem.init_mem = [int.from_bytes(insns[adr:adr+4],
                                                byteorder="little")
                                 for adr in range(0, len(insns), 4)]
        elif isinstance(source_or_list, (bytes, bytearray)):
            self.mem.init_mem = [int.from_bytes(source_or_list[adr:adr+4],
                                                byteorder="little")
                                 for adr in range(0, len(source_or_list), 4)]
        else:
            self.mem.init_mem = source_or_list

    def elaborate(self, plat):
        m = Module()

        decoder = wishbone.Decoder(addr_width=30, data_width=32, granularity=8,
                                   alignment=25)

        m.submodules.cpu = self.cpu
        m.submodules.mem = self.mem
        m.submodules.leds = self.leds
        m.submodules.decoder = decoder

        mem_bus = wishbone.Interface(addr_width=log2_int(self.mem.depth) - 2,
                                     data_width=32,
                                     granularity=8,
                                     memory_map=MemoryMap(addr_width=log2_int(self.mem.depth),  # noqa: E501
                                                          data_width=8),
                                     path=("mem",))
        led_bus = wishbone.Interface(addr_width=1, data_width=8,
                                     granularity=8,
                                     memory_map=MemoryMap(addr_width=1,
                                                          data_width=8),
                                     path=("led",))

        if plat:
            for i in range(8):
                try:
                    led = plat.request("led", i)
                except ResourceError:
                    break
                m.d.comb += led.o.eq(self.leds.leds[i])

        decoder.add(mem_bus)
        decoder.add(led_bus, sparse=True)
        connect(m, mem_bus, self.mem.bus)
        connect(m, led_bus, self.leds.bus)
        connect(m, self.cpu.bus, decoder.bus)

        return m