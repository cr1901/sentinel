import argparse
import sys
import importlib
from contextlib import contextmanager

from bronzebeard.asm import assemble
from amaranth import Module, Memory, Signal
from amaranth_soc import wishbone
from amaranth_soc.memory import MemoryMap
from amaranth.lib.wiring import In, Out, Component, Elaboratable, connect
from amaranth.back import verilog
from amaranth.build import ResourceError
from amaranth_boards import icestick, ice40_hx8k_b_evn

from .top import Top


class WBMemory(Component):
    bus: In(wishbone.Signature(addr_width=10, data_width=32, granularity=8))

    def __init__(self):
        super().__init__()
        self.mem = Memory(width=32, depth=0x400)

    @property
    def init_mem(self):
        return self.mem.init

    @init_mem.setter
    def init_mem(self, mem):
        self.mem.init = mem

    def elaborate(self, plat):
        m = Module()
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

        with m.If(self.bus.stb & self.bus.cyc & ~self.bus.ack):
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


# Reimplementation of nextpnr-ice40's AttoSoC example (https://github.com/YosysHQ/nextpnr/tree/master/ice40/smoketest/attosoc),
# to exercise attaching Sentinel to amaranth-soc's wishbone components.
class AttoSoC(Elaboratable):
    def __init__(self):
        self.cpu = Top()
        self.mem = WBMemory()
        self.leds = Leds()

    def elaborate(self, plat):
        m = Module()

        decoder = wishbone.Decoder(addr_width=30, data_width=32, granularity=8,
                                   alignment=25)

        m.submodules.cpu = self.cpu
        m.submodules.mem = self.mem
        m.submodules.leds = self.leds
        m.submodules.decoder = decoder

        mem_bus = wishbone.Interface(addr_width=10, data_width=32,
                                     granularity=8,
                                     memory_map=MemoryMap(addr_width=12,
                                                          data_width=8),
                                     path=("mem",))
        led_bus = wishbone.Interface(addr_width=1, data_width=8,
                                     granularity=8,
                                     memory_map=MemoryMap(addr_width=1,
                                                          data_width=8),
                                     path=("led",))

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


@contextmanager
def file_or_stdout(fn):
    is_stdout = not fn or fn == "-"

    if not is_stdout:
        fp = open(fn, "w")
    else:
        fp = sys.stdout

    try:
        yield fp
    finally:
        if not is_stdout:
            fp.close()


def generate(args=None):
    if isinstance(args, argparse.Namespace):
        with file_or_stdout(args.o) as fp:
            m = Top()
            v = verilog.convert(m, name=args.n or "top")  # noqa: E501
            fp.write(v)
    else:
        m = Top()
        print(verilog.convert(m))


def demo(args):
    insns = assemble("""
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
""")

    asoc = AttoSoC()
    asoc.mem.init_mem = [int.from_bytes(insns[adr:adr+4], byteorder="little")
                         for adr in range(0, len(insns), 4)]

    if args.p == "ice40_hx8k_b_evn":
        plat = ice40_hx8k_b_evn.ICE40HX8KBEVNPlatform()
    else:
        plat = icestick.ICEStickPlatform()

    plan = plat.build(asoc, do_build=False, debug_verilog=True)
    plan.execute_local(run_script=not args.n)


def main():
    parser = argparse.ArgumentParser(description="Sentinel Verilog/Demo generator")  # noqa: E501
    sub = parser.add_subparsers(help="subcommand", required=True)

    gen = sub.add_parser("generate", aliases=("gen", "g"))
    gen.add_argument("-o", help="output filename")
    gen.add_argument("-n", help="top-level name")
    gen.set_defaults(func=generate)

    d = sub.add_parser("demo", aliases=("d"))
    d.add_argument("-p", help="build platform",
                   choices=("icestick", "ice40_hx8k_b_evn"),
                   default="icestick")
    d.add_argument("-n", help="dry run",
                   action="store_true")
    d.set_defaults(func=demo)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
