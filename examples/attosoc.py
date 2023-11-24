# SoC components. This is more of a "utilities" module.

import argparse
from functools import reduce
from random import randint
from pathlib import Path

from bronzebeard.asm import assemble
from makeelf.elf import ELF, SHF, SHT
from amaranth import Module, Memory, Signal, Cat, C
from amaranth_soc import wishbone
from amaranth_soc.memory import MemoryMap
from amaranth.lib.wiring import In, Out, Component, Elaboratable, connect, \
    Signature
from amaranth.build import ResourceError
from amaranth.utils import log2_int
from amaranth_boards import icestick, ice40_hx8k_b_evn

from sentinel.top import Top


class WBMemory(Component):
    @property
    def signature(self):
        sig = Signature({
            "bus": In(wishbone.Signature(addr_width=log2_int(self.num_bytes) - 2,  # noqa: E501
                                         data_width=32,
                                         granularity=8)),
        })

        if self.sim:
            sig.members["ctrl"] = Out(Signature({
                "force_ws": Out(1)  # noqa: F821
            }))
        return sig

    def __init__(self, *, sim=False, num_bytes=0x400):
        self.sim = sim
        self.num_bytes = num_bytes
        super().__init__()

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


class Timer(Component):
    bus: In(wishbone.Signature(addr_width=1, data_width=8, granularity=8))
    irq: Out(1)

    def __init__(self):
        super().__init__()

    def elaborate(self, plat):
        m = Module()

        prescalar = Signal(16)
        cnt = Signal(8)
        cmp = Signal(8)

        m.d.sync += prescalar.eq(prescalar + 1)

        with m.If(prescalar == 0xFFFF):
            cnt.eq(cnt + 1)

        with m.If(cnt == cmp):
            m.d.sync += self.irq.eq(1)

        with m.If(self.bus.stb & self.bus.cyc & self.bus.ack & self.bus.we &
                  self.bus.sel[0]):
            with m.If(self.bus.adr[0] == 0):
                m.d.sync += [
                    cmp.eq(self.bus.dat_w),
                    cnt.eq(0),
                    prescalar.eq(0)
                ]

            with m.If(self.bus.adr[0] == 1):
                m.d.sync += self.irq.eq(0)

        with m.If(self.bus.stb & self.bus.cyc & ~self.bus.ack):
            m.d.sync += self.bus.ack.eq(1)
        with m.Else():
            m.d.sync += self.bus.ack.eq(0)

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
    bus: In(wishbone.Signature(addr_width=0, data_width=32, granularity=8))
    rx: In(1)
    tx: Out(1)
    irq: Out(1)

    def __init__(self):
        super().__init__()
        self.serial = UART(divisor=12000000 // 115200)

    def elaborate(self, plat):
        m = Module()
        m.submodules.ser_internal = self.serial

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

        with m.If(self.bus.stb & self.bus.cyc & self.bus.sel[0]):
            m.d.sync += self.bus.dat_r.eq(self.serial.rx_data)
            with m.If(~self.bus.we):
                m.d.comb += self.serial.rx_ack.eq(1)

            with m.If(self.bus.ack & self.bus.we):
                m.d.comb += [
                    self.serial.tx_data.eq(self.bus.dat_w),
                    self.serial.tx_rdy.eq(1)
                ]

        with m.If(self.bus.stb & self.bus.cyc & self.bus.sel[1]):
            m.d.sync += self.bus.dat_r[8:10].eq(Cat(rx_rdy_irq, tx_ack_irq))

            with m.If(self.bus.ack & self.bus.we):
                m.d.sync += [
                    rx_rdy_irq.eq(self.bus.dat_w[8]),
                    tx_ack_irq.eq(self.bus.dat_w[9]),
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


# Reimplementation of nextpnr-ice40's AttoSoC example (https://github.com/YosysHQ/nextpnr/tree/master/ice40/smoketest/attosoc),  # noqa: E501
# to exercise attaching Sentinel to amaranth-soc's wishbone components.
class AttoSoC(Elaboratable):
    def __init__(self, *, sim=False, num_bytes=0x400):
        self.cpu = Top()
        self.mem = WBMemory(sim=sim, num_bytes=num_bytes)
        self.leds = Leds()
        self.sim = sim
        if not self.sim:
            self.timer = Timer()
            self.serial = WBSerial()

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

        mem_bus = wishbone.Interface(addr_width=log2_int(self.mem.num_bytes) - 2,  # noqa: E501
                                     data_width=32,
                                     granularity=8,
                                     memory_map=MemoryMap(addr_width=log2_int(self.mem.num_bytes),  # noqa: E501
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
            ser = plat.request("uart")

        decoder.add(mem_bus)
        decoder.add(led_bus, sparse=True)
        if not self.sim:
            m.submodules.timer = self.timer
            timer_bus = wishbone.Interface(addr_width=1, data_width=8,
                                           granularity=8,
                                           memory_map=MemoryMap(addr_width=1,
                                                                data_width=8),
                                           path=("timer",))
            decoder.add(timer_bus, sparse=True)
            connect(m, timer_bus, self.timer.bus)

            m.submodules.serial = self.serial
            serial_bus = wishbone.Interface(addr_width=0, data_width=32,
                                            granularity=8,
                                            memory_map=MemoryMap(addr_width=2,
                                                                 data_width=8),
                                            path=("serial",))
            decoder.add(serial_bus)
            connect(m, serial_bus, self.serial.bus)
            m.d.comb += [
                self.serial.rx.eq(ser.rx.i),
                ser.tx.o.eq(self.serial.tx)
            ]

            # m.d.comb += self.cpu.irq.eq(self.timer.irq | self.serial.irq)
            m.d.comb += self.cpu.irq.eq(self.serial.irq)

        connect(m, mem_bus, self.mem.bus)
        connect(m, led_bus, self.leds.bus)
        connect(m, self.cpu.bus, decoder.bus)

        return m


def demo(args):
    asoc = AttoSoC(num_bytes=0x1000)

    if args.g:
        # In-line objcopy -O binary implementation. Probably does not handle
        # anything but basic cases well, but I think it's "good enough".
        with open(args.g, "rb") as fp:
            elf, _ = ELF.from_bytes(fp.read())

            # First, look for the sections that are part of the executable
            # (not metadata) _and_ take up space in the ELF file (basically
            # everything except zero-init/uninitialized memory).
            to_write = []
            for i, shdr in enumerate(elf.Elf.Shdr_table):
                if (shdr.sh_flags & int(SHF.SHF_ALLOC)) and \
                        (shdr.sh_type & int(SHT.SHT_PROGBITS)):
                    to_write.append(i)

            def append_bytes(a, b):
                return a + b

            def section(i):
                return elf.Elf.sections[i]

            def section_addr(i):
                return elf.Elf.Shdr_table[i].sh_addr

            # Sort the sections in order of increasing load address (the final
            # location from Sentinel's POV where the data is loaded), get the
            # contents of each section in that order, and concatenate them.
            asoc.rom = reduce(append_bytes,
                              map(section, sorted(to_write, key=section_addr)),
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
        case "icestick":
            plat = icestick.ICEStickPlatform()

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
    plan.execute_local(args.b, run_script=not args.n)

    if args.x:
        with open(Path(args.b) / Path(args.x).with_suffix(".hex"), "w") as fp:
            fp.writelines(f"{i:08x}\n" for i in asoc.rom)


def main():
    parser = argparse.ArgumentParser(description="Sentinel AttoSoC Demo generator")  # noqa: E501
    parser.add_argument("-n", help="dry run",
                        action="store_true")
    parser.add_argument("-b", help="build directory",
                        default="build")
    parser.add_argument("-p", help="build platform",
                        choices=("icestick", "ice40_hx8k_b_evn"),
                        default="icestick")
    group = parser.add_mutually_exclusive_group()
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
