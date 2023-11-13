import argparse
import sys
from contextlib import contextmanager

from amaranth.back import verilog
from amaranth_boards import icestick, ice40_hx8k_b_evn

from .formal import FormalTop
from .top import Top
from .soc import AttoSoC


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


def generate_args(parser):
    parser.add_argument("-o", help="output filename")
    parser.add_argument("-n", help="top-level name")
    parser.add_argument("-f", action="store_true", help="add RVFI connections")


def generate(args=None):
    def do_gen(*, n, o, f):
        with file_or_stdout(o) as fp:
            if f:
                m = FormalTop()
            else:
                m = Top()
            v = verilog.convert(m, name=n or "sentinel")  # noqa: E501
            fp.write(v)

    if isinstance(args, argparse.Namespace):
        do_gen(args)
    else:
        if len(sys.argv) < 2:
            m = Top()
            print(verilog.convert(m))
        else:
            parser = argparse.ArgumentParser(description="Sentinel Verilog generator (invoked from PDM)")  # noqa: E501
            generate_args(parser)
            do_gen(**vars(parser.parse_args()))


def demo_args(parser):
    parser.add_argument("-p", help="build platform",
                        choices=("icestick", "ice40_hx8k_b_evn"),
                        default="icestick")
    parser.add_argument("-n", help="dry run",
                        action="store_true")
    parser.add_argument("-b", help="build directory",
                        default="build")


def demo(args=None):
    def do_demo(*, p, n, b):
        print(b)
        asoc = AttoSoC()
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

        if p == "ice40_hx8k_b_evn":
            plat = ice40_hx8k_b_evn.ICE40HX8KBEVNPlatform()
        else:
            plat = icestick.ICEStickPlatform()

        plan = plat.build(asoc, do_build=False, debug_verilog=True)
        plan.execute_local(b, run_script=not n)

    if isinstance(args, argparse.Namespace):
        do_demo(args)
    else:
        if len(sys.argv) < 2:
            do_demo(p="icestick", n=False, b="build")
        else:
            parser = argparse.ArgumentParser(description="Sentinel Demo generator (invoked from PDM)")  # noqa: E501
            demo_args(parser)
            do_demo(**vars(parser.parse_args()))


def main():
    parser = argparse.ArgumentParser(description="Sentinel Verilog/Demo generator")  # noqa: E501
    sub = parser.add_subparsers(help="subcommand", required=True)

    gen = sub.add_parser("generate", aliases=("gen", "g"))
    generate_args(gen)
    gen.set_defaults(func=generate)

    d = sub.add_parser("demo", aliases=("d"))
    demo_args(d)
    d.set_defaults(func=demo)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
