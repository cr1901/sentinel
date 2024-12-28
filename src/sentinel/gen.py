"""Verilog generation module/script for Sentinel.

At present, only running this module directly from the command-line
(as ``__main__``) or from PDM is supported:

::

    python -m sentinel.gen --help

.. code-block:: toml

    [tool.pdm.scripts]
    gen = { call = "sentinel.gen:generate", help="generate Sentinel Verilog file" }

Individual functions are documented for completeness and should not be treated
as public (see :doc:`/development/guidelines`).
"""  # noqa: E501

import argparse
import sys
from contextlib import contextmanager

from amaranth.back import verilog

from .formal import FormalTop
from .top import Top


@contextmanager
def _file_or_stdout(fn):
    """Context manager to open either a file or stdout if "-" is passed.

    Yields
    ------
    fp
        File-like object representing either stdout or a disk-backed file.
    """
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


def _generate_args(parser):
    """Add argparse arguments."""
    parser.add_argument("-o", help="output filename")
    parser.add_argument("-n", help="top-level name")
    parser.add_argument("-f", action="store_true", help="add RVFI connections")


def generate(args=None):
    """Intended programmatic entry point to generate Sentinel core.

    .. todo::

        This function is not yet complete and only works in the context of invoking
        via ``pdm``:

        .. code-block:: toml

            [tool.pdm.scripts]
            gen = { call = "sentinel.gen:generate", help="generate Sentinel Verilog file" }

    Parameters
    ----------
    args
        Used to detect whether we are running as a script or as an imported
        module. Leave as ``None`` until the function is completed in a later
        release.
    """  # noqa: E501
    def do_gen(*, n, o, f):
        with _file_or_stdout(o) as fp:
            if f:
                m = FormalTop()
            else:
                m = Top()
            v = verilog.convert(m, name=n or "sentinel")
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
            _generate_args(parser)
            do_gen(**vars(parser.parse_args()))


def _main():
    """Scripting entry point to generate Sentinel core."""
    parser = argparse.ArgumentParser(description="Sentinel Verilog generator")

    _generate_args(parser)
    args = parser.parse_args()
    generate(args)


if __name__ == "__main__":
    _main()
