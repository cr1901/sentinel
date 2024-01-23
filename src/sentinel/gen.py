import argparse
import sys
from contextlib import contextmanager

from amaranth.back import verilog

from .formal import FormalTop
from .top import Top


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
        if len(sys.argv) < 2:
            m = Top()
            print(verilog.convert(m))
        else:
            do_gen(**vars(args))
    else:
        if len(sys.argv) < 2:
            m = Top()
            print(verilog.convert(m))
        else:
            parser = argparse.ArgumentParser(description="Sentinel Verilog generator (invoked from PDM)")  # noqa: E501
            generate_args(parser)
            do_gen(**vars(parser.parse_args()))


def main():
    parser = argparse.ArgumentParser(description="Sentinel Verilog generator")  # noqa: E501

    generate_args(parser)
    args = parser.parse_args()
    generate(args)


if __name__ == "__main__":
    main()
