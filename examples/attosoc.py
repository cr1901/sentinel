# SoC components. This is more of a "utilities" module.

import argparse
from functools import reduce
import itertools
from random import randint
from pathlib import Path, PurePosixPath
import importlib
import shutil
import enum
from enum import auto

from bronzebeard.asm import assemble
from elftools.elf.elffile import ELFFile
from amaranth import Module, Memory, Signal, Cat, C
from amaranth_soc import wishbone
from amaranth_soc import csr
from amaranth_soc.csr.wishbone import WishboneCSRBridge
from amaranth_soc.memory import MemoryMap
from amaranth.lib.wiring import In, Out, Component, Elaboratable, connect, \
    Signature, flipped
from amaranth.build import ResourceError, Resource, Pins
from amaranth_boards import icestick, ice40_hx8k_b_evn
from tabulate import tabulate

from sentinel.top import Top


class WBMemory(Component):
    @property
    def signature(self):
        return self._signature

    def __init__(self, *, sim=False, num_bytes=0x400):
        bus_signature = wishbone.Signature(addr_width=23, data_width=32,
                                           granularity=8)
        bus_signature.memory_map = MemoryMap(addr_width=25, data_width=8)
        self._signature = Signature({
            "bus": In(bus_signature)
        })

        if sim:
            self._signature.members["ctrl"] = Out(Signature({
                "force_ws": Out(1)  # noqa: F821
            }))

        self.sim = sim
        self.num_bytes = num_bytes

        super().__init__()
        bus_signature.memory_map.add_resource(self.bus, name="ram",
                                              size=num_bytes)

    @property
    def init_mem(self):
        return self.mem_contents

    @init_mem.setter
    def init_mem(self, mem):
        self.mem_contents = mem

    def elaborate(self, plat):
        m = Module()
        self.mem = Memory(width=32, depth=self.num_bytes//4,
                          init=self.mem_contents)
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


class WBLeds(Component):
    @property
    def signature(self):
        return self._signature

    def __init__(self):
        bus_signature = wishbone.Signature(addr_width=25, data_width=8,
                                           granularity=8)
        bus_signature.memory_map = MemoryMap(addr_width=25, data_width=8,
                                             name="leds")
        self._signature = Signature({
            "bus": In(bus_signature),
            "leds": Out(8),
            "gpio": In(Signature({
                 "i": In(1),
                 "o": Out(1),
                 "oe": Out(1)
            })).array(8)
        })

        super().__init__()
        bus_signature.memory_map.add_resource(self.leds,
                                              name="leds", size=1)
        bus_signature.memory_map.add_resource(((g.o for g in self.gpio),
                                               (g.i for g in self.gpio)),
                                              name="inout", size=1)
        bus_signature.memory_map.add_resource((g.oe for g in self.gpio),
                                              name="oe", size=1)

    def elaborate(self, plat):
        m = Module()

        with m.If(self.bus.stb & self.bus.cyc & self.bus.ack & self.bus.we
                  & (self.bus.adr[0:2] == 0) & self.bus.sel[0]):
            m.d.sync += self.leds.eq(self.bus.dat_w)

        with m.If(self.bus.stb & self.bus.cyc & ~self.bus.ack &
                  (self.bus.adr[0:2] == 1) & self.bus.sel[0]):
            with m.If(~self.bus.we):
                for i in range(8):
                    m.d.sync += self.bus.dat_r[i].eq(self.gpio[i].i)
            with m.Else():
                for i in range(8):
                    m.d.sync += self.gpio[i].o.eq(self.bus.dat_w[i])

        with m.If(self.bus.stb & self.bus.cyc & ~self.bus.ack & self.bus.we
                  & (self.bus.adr[0:2] == 2) & self.bus.sel[0]):
            for i in range(8):
                m.d.sync += self.gpio[i].oe.eq(self.bus.dat_w[i])

        with m.If(self.bus.stb & self.bus.cyc & ~self.bus.ack):
            m.d.sync += self.bus.ack.eq(1)
        with m.Else():
            m.d.sync += self.bus.ack.eq(0)

        return m


class CSRLeds(Component):
    @property
    def signature(self):
        return self._signature

    def __init__(self):
        self.mux = csr.bus.Multiplexer(addr_width=4, data_width=8, name="gpio")
        self._signature = self.mux.signature
        self._signature.members += {
            "leds": Out(8),
            "gpio": In(Signature({
                 "i": In(1),
                 "o": Out(1),
                 "oe": Out(1)
            })).array(8)
        }

        self.leds_reg = csr.Element(8, "w", path=("leds",))
        self.inout_reg = csr.Element(8, "rw", path=("inout",))
        self.oe_reg = csr.Element(8, "rw", path=("oe",))
        self.mux.add(self.leds_reg, name="leds")
        self.mux.add(self.inout_reg, name="inout", addr=4)
        self.mux.add(self.oe_reg, name="oe", addr=8)

        super().__init__()

    def elaborate(self, plat):
        m = Module()
        m.submodules.mux = self.mux

        connect(m, flipped(self.bus), self.mux.bus)

        with m.If(self.leds_reg.w_stb):
            m.d.sync += self.leds.eq(self.leds_reg.w_data)

        with m.If(self.inout_reg.w_stb):
            for i in range(8):
                m.d.sync += self.gpio[i].o.eq(self.leds_reg.w_data[i])

        for i in range(8):
            m.d.comb += self.inout_reg.r_data[i].eq(self.gpio[i].i)

        with m.If(self.oe_reg.w_stb):
            for i in range(8):
                m.d.sync += self.gpio[i].oe.eq(self.oe_reg.w_data[i])

        return m


class WBTimer(Component):
    @property
    def signature(self):
        return self._signature

    def __init__(self):
        bus_signature = wishbone.Signature(addr_width=30, data_width=8,
                                           granularity=8)
        bus_signature.memory_map = MemoryMap(addr_width=30, data_width=8,
                                             name="timer")
        self._signature = Signature({
            "bus": In(bus_signature),
            "irq": Out(1),
        })

        super().__init__()
        bus_signature.memory_map.add_resource(self.irq, name="irq", size=1)

    def elaborate(self, plat):
        m = Module()

        prescalar = Signal(15)

        m.d.sync += prescalar.eq(prescalar + 1)
        m.d.comb += self.irq.eq(prescalar[14])

        with m.If(self.bus.stb & self.bus.cyc & ~self.bus.we):
            with m.If(self.bus.sel[0] == 1):
                m.d.sync += self.bus.dat_r.eq(self.irq)

                with m.If(self.irq):
                    m.d.sync += prescalar[14].eq(0)

        with m.If(self.bus.stb & self.bus.cyc & ~self.bus.ack):
            m.d.sync += self.bus.ack.eq(1)
        with m.Else():
            m.d.sync += self.bus.ack.eq(0)

        return m


class CSRTimer(Component):
    @property
    def signature(self):
        return self._signature

    def __init__(self):
        self.mux = csr.bus.Multiplexer(addr_width=3, data_width=8,
                                       name="timer")
        self._signature = self.mux.signature
        self._signature.members += {
            "irq": Out(1)
        }

        self.irq_reg = csr.Element(8, "r", path=("irq",))
        self.mux.add(self.irq_reg, name="irq")

        super().__init__()

    def elaborate(self, plat):
        m = Module()
        m.submodules.mux = self.mux

        connect(m, flipped(self.bus), self.mux.bus)

        prescaler = Signal(15)

        m.d.sync += prescaler.eq(prescaler + 1)
        m.d.comb += [
            self.irq.eq(prescaler[14]),
            self.irq_reg.r_data.eq(prescaler[14])
        ]

        with m.If(self.irq_reg.r_stb):
            with m.If(self.irq):
                m.d.sync += prescaler[14].eq(0)

        return m


# Taken from: https://github.com/amaranth-lang/amaranth/blob/f9da3c0d166dd2be189945dca5a94e781e74afeb/examples/basic/uart.py  # noqa: E501
class UART(Elaboratable):
    """
    Parameters
    ----------
    divisor : int
        Set to ``round(clk-rate / baud-rate)``.
        E.g. ``12e6 / 115200`` = ``104``.
    """
    def __init__(self, divisor, data_bits=8):
        assert divisor >= 4

        self.data_bits = data_bits
        self.divisor = divisor

        self.tx_o = Signal()
        self.rx_i = Signal()

        self.tx_data = Signal(data_bits)
        self.tx_rdy = Signal()
        self.tx_ack = Signal()

        self.rx_data = Signal(data_bits)
        self.rx_err = Signal()
        self.rx_ovf = Signal()
        self.rx_rdy = Signal()
        self.rx_ack = Signal()

    def elaborate(self, platform):
        m = Module()

        tx_phase = Signal(range(self.divisor))
        tx_shreg = Signal(1 + self.data_bits + 1, reset=-1)
        tx_count = Signal(range(len(tx_shreg) + 1))

        m.d.comb += self.tx_o.eq(tx_shreg[0])
        with m.If(tx_count == 0):
            m.d.comb += self.tx_ack.eq(1)
            with m.If(self.tx_rdy):
                m.d.sync += [
                    tx_shreg.eq(Cat(C(0, 1), self.tx_data, C(1, 1))),
                    tx_count.eq(len(tx_shreg)),
                    tx_phase.eq(self.divisor - 1),
                ]
        with m.Else():
            with m.If(tx_phase != 0):
                m.d.sync += tx_phase.eq(tx_phase - 1)
            with m.Else():
                m.d.sync += [
                    tx_shreg.eq(Cat(tx_shreg[1:], C(1, 1))),
                    tx_count.eq(tx_count - 1),
                    tx_phase.eq(self.divisor - 1),
                ]

        rx_phase = Signal(range(self.divisor))
        rx_shreg = Signal(1 + self.data_bits + 1, reset=-1)
        rx_count = Signal(range(len(rx_shreg) + 1))

        m.d.comb += self.rx_data.eq(rx_shreg[1:-1])
        with m.If(rx_count == 0):
            m.d.comb += self.rx_err.eq(~(~rx_shreg[0] & rx_shreg[-1]))
            with m.If(~self.rx_i):
                with m.If(self.rx_ack | ~self.rx_rdy):
                    m.d.sync += [
                        self.rx_rdy.eq(0),
                        self.rx_ovf.eq(0),
                        rx_count.eq(len(rx_shreg)),
                        rx_phase.eq(self.divisor // 2),
                    ]
                with m.Else():
                    m.d.sync += self.rx_ovf.eq(1)
            with m.If(self.rx_ack):
                m.d.sync += self.rx_rdy.eq(0)
        with m.Else():
            with m.If(rx_phase != 0):
                m.d.sync += rx_phase.eq(rx_phase - 1)
            with m.Else():
                m.d.sync += [
                    rx_shreg.eq(Cat(rx_shreg[1:], self.rx_i)),
                    rx_count.eq(rx_count - 1),
                    rx_phase.eq(self.divisor - 1),
                ]
                with m.If(rx_count == 1):
                    m.d.sync += self.rx_rdy.eq(1)

        return m


class WBSerial(Component):
    @property
    def signature(self):
        return self._signature

    def __init__(self):
        bus_signature = wishbone.Signature(addr_width=30, data_width=8,
                                           granularity=8)
        bus_signature.memory_map = MemoryMap(addr_width=30, data_width=8,
                                             name="serial")
        self._signature = Signature({
            "bus": In(bus_signature),
            "rx": In(1),
            "tx": Out(1),
            "irq": Out(1),
        })

        super().__init__()
        bus_signature.memory_map.add_resource((self.tx, self.rx), name="rxtx",
                                              size=1)
        bus_signature.memory_map.add_resource(self.irq, name="irq", size=1)
        self.serial = UART(divisor=12000000 // 9600)

    def elaborate(self, plat):
        m = Module()
        m.submodules.ser_internal = self.serial

        # rx_rdy_prev having reset of 0 will deliberately will trigger IRQ at
        # reset. We use this to detect WB vs CSR bus.
        rx_rdy_irq = Signal()
        rx_rdy_prev = Signal()
        tx_ack_irq = Signal()
        tx_ack_prev = Signal()

        m.d.comb += [
            self.irq.eq(rx_rdy_irq | tx_ack_irq),
            self.tx.eq(self.serial.tx_o),
            self.serial.rx_i.eq(self.rx)
        ]

        m.d.sync += [
            rx_rdy_prev.eq(self.serial.rx_rdy),
            tx_ack_prev.eq(self.serial.tx_ack),
        ]

        with m.If(self.bus.stb & self.bus.cyc & self.bus.sel[0] &
                  ~self.bus.adr[0]):
            m.d.sync += self.bus.dat_r.eq(self.serial.rx_data)
            with m.If(~self.bus.we):
                m.d.comb += self.serial.rx_ack.eq(1)

            with m.If(self.bus.ack & self.bus.we):
                m.d.comb += [
                    self.serial.tx_data.eq(self.bus.dat_w),
                    self.serial.tx_rdy.eq(1)
                ]

        with m.If(self.bus.stb & self.bus.cyc & self.bus.sel[0] &
                  self.bus.adr[0] & ~self.bus.we & ~self.bus.ack):
            m.d.sync += [
                self.bus.dat_r.eq(Cat(rx_rdy_irq, tx_ack_irq)),
                rx_rdy_irq.eq(0),
                tx_ack_irq.eq(0)
            ]

        with m.If(self.bus.stb & self.bus.cyc & ~self.bus.ack):
            m.d.sync += self.bus.ack.eq(1)
        with m.Else():
            m.d.sync += self.bus.ack.eq(0)

        # Don't accidentally miss an IRQ
        with m.If(self.serial.rx_rdy & ~rx_rdy_prev):
            m.d.sync += rx_rdy_irq.eq(1)
        with m.If(self.serial.tx_ack & ~tx_ack_prev):
            m.d.sync += tx_ack_irq.eq(1)

        return m


class CSRSerial(Component):
    @property
    def signature(self):
        return self._signature

    def __init__(self):
        self.mux = csr.bus.Multiplexer(addr_width=3, data_width=8, alignment=0,
                                       name="serial")
        self._signature = self.mux.signature
        self._signature.members += {
            "rx": In(1),
            "tx": Out(1),
            "irq": Out(1)
        }

        self.txrx_reg = csr.Element(8, "rw", path=("txrx",))
        self.mux.add(self.txrx_reg, name="txrx")
        self.irq_reg = csr.Element(8, "r", path=("irq",))
        self.mux.add(self.irq_reg, name="irq", addr=4)

        super().__init__()
        self.serial = UART(divisor=12000000 // 9600)

    def elaborate(self, plat):
        m = Module()
        m.submodules.ser_internal = self.serial
        m.submodules.mux = self.mux

        connect(m, flipped(self.bus), self.mux.bus)

        # rx_rdy_prev having reset of 1 will suppress IRQ at reset. We use this
        # to detect WB vs CSR bus.
        rx_rdy_irq = Signal()
        rx_rdy_prev = Signal(reset=1)
        tx_ack_irq = Signal()
        tx_ack_prev = Signal(reset=1)

        m.d.comb += [
            self.irq.eq(rx_rdy_irq | tx_ack_irq),
            self.tx.eq(self.serial.tx_o),
            self.serial.rx_i.eq(self.rx)
        ]

        m.d.sync += [
            rx_rdy_prev.eq(self.serial.rx_rdy),
            tx_ack_prev.eq(self.serial.tx_ack),
        ]

        m.d.comb += [
            self.serial.tx_data.eq(self.txrx_reg.w_data),
            self.txrx_reg.r_data.eq(self.serial.rx_data),
            self.irq_reg.r_data.eq(Cat(rx_rdy_irq, tx_ack_irq))
        ]

        with m.If(self.txrx_reg.w_stb):
            m.d.comb += self.serial.tx_rdy.eq(1)
        with m.If(self.txrx_reg.r_stb):
            m.d.comb += self.serial.rx_ack.eq(1)

        with m.If(self.irq_reg.r_stb):
            m.d.sync += [
                rx_rdy_irq.eq(0),
                tx_ack_irq.eq(0)
            ]

        # Don't accidentally miss an IRQ
        with m.If(self.serial.rx_rdy & ~rx_rdy_prev):
            m.d.sync += rx_rdy_irq.eq(1)
        with m.If(self.serial.tx_ack & ~tx_ack_prev):
            m.d.sync += tx_ack_irq.eq(1)

        return m


class BusType(enum.Enum):
    WB = auto()
    CSR = auto()


# Reimplementation of nextpnr-ice40's AttoSoC example (https://github.com/YosysHQ/nextpnr/tree/master/ice40/smoketest/attosoc),  # noqa: E501
# to exercise attaching Sentinel to amaranth-soc's wishbone components.
class AttoSoC(Elaboratable):
    # CSR is the default because it's what's encouraged. However, the default
    # for the demo is WB because that's what fits on the ICE40HX1K!
    def __init__(self, *, sim=False, num_bytes=0x400, bus_type=BusType.CSR):
        self.cpu = Top()
        self.mem = WBMemory(sim=sim, num_bytes=num_bytes)
        self.decoder = wishbone.Decoder(addr_width=30, data_width=32,
                                        granularity=8, alignment=25)
        self.sim = sim
        self.bus_type = bus_type

        match bus_type:
            case BusType.WB:
                self.leds = WBLeds()

                if not self.sim:
                    self.timer = WBTimer()
                    self.serial = WBSerial()
            case BusType.CSR:
                self.leds = CSRLeds()

                if not self.sim:
                    self.timer = CSRTimer()
                    self.serial = CSRSerial()

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

        m.submodules.cpu = self.cpu
        m.submodules.mem = self.mem
        m.submodules.leds = self.leds
        m.submodules.decoder = self.decoder

        if plat:
            for i in range(8):
                try:
                    led = plat.request("led", i)
                except ResourceError:
                    break
                m.d.comb += led.o.eq(self.leds.leds[i])

            ser = plat.request("uart")

            for i in range(8):
                try:
                    gpio = plat.request("gpio", i)
                except ResourceError:
                    break

                m.d.comb += [
                    self.leds.gpio[i].i.eq(gpio.i),
                    gpio.oe.eq(self.leds.gpio[i].oe),
                    gpio.o.eq(self.leds.gpio[i].o)
                ]

        self.decoder.add(flipped(self.mem.bus))

        if self.bus_type == BusType.WB:
            self.decoder.add(flipped(self.leds.bus), sparse=True)

            if not self.sim:
                m.submodules.timer = self.timer
                self.decoder.add(flipped(self.timer.bus), sparse=True)

                m.submodules.serial = self.serial
                self.decoder.add(flipped(self.serial.bus), sparse=True)

        elif self.bus_type == BusType.CSR:
            # CSR (has to be done first other mem map "frozen" errors?)
            periph_decode = csr.Decoder(addr_width=25, data_width=8,
                                        alignment=23, name="periph")
            periph_decode.add(self.leds.bus, addr=0)

            if not self.sim:
                periph_decode.add(self.timer.bus)
                periph_decode.add(self.serial.bus)
                m.submodules.timer = self.timer
                m.submodules.serial = self.serial

            # Connect peripherals to Wishbone
            periph_wb = WishboneCSRBridge(periph_decode.bus, data_width=32)
            self.decoder.add(flipped(periph_wb.wb_bus))

            m.submodules.periph_bus = periph_decode
            m.submodules.periph_wb = periph_wb

        if not self.sim:
            if plat:
                m.d.comb += [
                    self.serial.rx.eq(ser.rx.i),
                    ser.tx.o.eq(self.serial.tx)
                ]

            m.d.comb += self.cpu.irq.eq(self.timer.irq | self.serial.irq)

        def destruct_res(res):
            return ("/".join(res.path), res.start, res.end, res.width)

        print(tabulate(map(destruct_res,
                           self.decoder.bus.memory_map.all_resources()),
                       intfmt=("", "#010x", "#010x", ""),
                       headers=["name", "start", "end", "width"]))
        connect(m, self.cpu.bus, self.decoder.bus)

        return m


def demo(args):
    match args.i:
        case "wishbone":
            asoc = AttoSoC(num_bytes=0x1000, bus_type=BusType.WB)
        case "csr":
            asoc = AttoSoC(num_bytes=0x1000, bus_type=BusType.CSR)

    if args.g:
        # In-line objcopy -O binary implementation. Probably does not handle
        # anything but basic cases well, but I think it's "good enough".
        with open(args.g, "rb") as fp:
            def append_bytes(a, b):
                return a + b

            def seg_data(seg):
                return seg.data()

            segs = ELFFile(fp).iter_segments()
            text_ro_and_data_segs = itertools.islice(segs, 2)
            asoc.rom = reduce(append_bytes,
                              map(seg_data, text_ro_and_data_segs),
                              b"")
    elif args.r:
        asoc.rom = [randint(0, 0xffffffff) for _ in range(0x400)]
    else:
        # Primes test firmware from tests and nextpnr AttoSoC.
        asoc.rom = """
            li      s0,2
            lui     s1,0x2000  # IO port at 0x2000000
            li      s3,256
    outer:
            addi    s0,s0,1
            blt     s0,s3,noinit
            li      s0,2
    noinit:
            li      s2,2
    next_int:
            bge     s2,s0,write_io
            mv      a0,s0
            mv      a1,s2
            call    prime?
            beqz    a0,not_prime
            addi    s2,s2,1
            j       next_int
    write_io:
            sw      s0,0(s1)
            call    delay
    not_prime:
            j       outer
    prime?:
            li      t0,1
    submore:
            sub     a0,a0,a1
            bge     a0,t0,submore
            ret
    delay:
            li      t0,360000
    countdown:
            addi    t0,t0,-1
            bnez    t0,countdown
            ret
    """

    match args.p:
        case "ice40_hx8k_b_evn":
            plat = ice40_hx8k_b_evn.ICE40HX8KBEVNPlatform()
            plat.add_resources([
                Resource("gpio", 0, Pins("4", dir="io", conn=("j", 2))),
                Resource("gpio", 1, Pins("5", dir="io", conn=("j", 2))),
                Resource("gpio", 2, Pins("6", dir="io", conn=("j", 2))),
                Resource("gpio", 3, Pins("9", dir="io", conn=("j", 2))),
                Resource("gpio", 4, Pins("10", dir="io", conn=("j", 2))),
                Resource("gpio", 5, Pins("11", dir="io", conn=("j", 2))),
                Resource("gpio", 6, Pins("12", dir="io", conn=("j", 2))),
                Resource("gpio", 7, Pins("13", dir="io", conn=("j", 2)))
            ])
        case "icestick":
            plat = icestick.ICEStickPlatform()
            plat.add_resources([
                # Cutting a bit close to 1280 LCs. Right now, just expose
                # enough to bitbang I2C based on PMOD spec pins:
                # https://digilent.com/blog/new-i2c-standard-for-pmods/
                # Resource("gpio", 0, Pins("1", dir="io", conn=("pmod", 0))),
                # Resource("gpio", 1, Pins("2", dir="io", conn=("pmod", 0))),
                # Resource("gpio", 2, Pins("3", dir="io", conn=("pmod", 0))),
                # Resource("gpio", 3, Pins("4", dir="io", conn=("pmod", 0)))
                Resource("gpio", 0, Pins("3", dir="io", conn=("pmod", 0))),
                Resource("gpio", 1, Pins("4", dir="io", conn=("pmod", 0)))
            ])

    plan = plat.build(asoc, name="rand" if args.r else "top", do_build=False,
                      debug_verilog=True,
                      # Optimize for area, not speed.
                      # https://libera.irclog.whitequark.org/yosys/2023-11-20#1700497858-1700497760;  # noqa: E501
                      script_after_read="\n".join([
                          "scratchpad -set abc9.D 83333",
                          "scratchpad -copy abc9.script.flow3 abc9.script"
                      ]),
                      # This also works wonders for optimizing for size.
                      synth_opts="-dff")

    if args.s:
        if not args.b:
            args.b = PurePosixPath("/tmp/build-remote")

        paramiko = importlib.import_module("paramiko")
        cfg_path = Path("~/.ssh/config").expanduser()
        config = paramiko.config.SSHConfig.from_path(cfg_path)
        host_cfg = config.lookup(args.s)

        connect_to_dict = {
            "hostname": host_cfg["hostname"],
            "username": host_cfg["user"]
        }

        products = plan.execute_remote_ssh(connect_to=connect_to_dict,
                                           root=str(args.b),
                                           run_script=not args.n)

        local_path = (Path(".") / Path(args.b).stem)
        local_path.mkdir(exist_ok=True)
        if not args.n:
            for prod in ("top.bin", "top.asc"):
                with products.extract(prod) as fn:
                    shutil.copy2(fn, local_path / prod)
    else:
        if not args.b:
            args.b = "build"
        plan.execute_local(Path(args.b), run_script=not args.n)
        local_path = Path(args.b)

    if args.x:
        # Although probably not that useful, it's easier to let this work
        # with remote as well as local builds than to use mutually-exclusive
        # groups to gate it.
        with open(Path(local_path) / Path(args.x).with_suffix(".hex"), "w") as fp:  # noqa: E501
            fp.writelines(f"{i:08x}\n" for i in asoc.rom)


def main():
    parser = argparse.ArgumentParser(description="Sentinel AttoSoC Demo generator")  # noqa: E501
    parser.add_argument("-n", help="dry run", action="store_true")
    parser.add_argument("-b", help="build directory (default build if local, "
                        "/tmp/build-remote if remote, and also extract "
                        "products locally)")
    parser.add_argument("-p", help="build platform",
                        choices=("icestick", "ice40_hx8k_b_evn"),
                        default="icestick")
    parser.add_argument("-i", help="peripheral interconnect type",
                        choices=("wishbone", "csr"),
                        default="wishbone")
    group = parser.add_mutually_exclusive_group()
    # Remote firmware override/random file generation is not supported;
    # Amaranth does not have provisions for supporting adding your own build
    # products remotely, and I don't feel like adding it using paramiko.
    # -x is supported remotely (after extracting from remote) to keep the CLI
    # simple.
    group.add_argument("-s", help="remote (SSH) build host from ~/.ssh/config, "  # noqa: E501
                       "keys loaded from ~/.ssh/id_*", metavar="HOST")
    group.add_argument("-g", help="firmware override",
                       default=None)
    group.add_argument("-r", help="use random numbers to fill firmware "
                                  "(use with -x and -n)", action="store_true")
    parser.add_argument("-x", help="generate a hex file of firmware in build "
                                   "dir (use with {ice,ecp}bram)",
                        metavar="BASENAME",
                        default=None)
    args = parser.parse_args()
    demo(args)


if __name__ == "__main__":
    main()
