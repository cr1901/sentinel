import sys
import argparse
import subprocess
import re

from amaranth import *
from amaranth.back import rtlil, cxxrtl, verilog
from amaranth.sim import *

from .alu import ALU
from .control import Control
from .datapath import DataPath
from .decode import Decode
from .top import Top
from .ucoderom import UCodeROM

class RunnerError(Exception):
    pass


def main_parser(parser=None):
    # amaranth.cli begin
    if parser is None:
        parser = argparse.ArgumentParser()

    p_action = parser.add_subparsers(dest="action")

    p_generate = p_action.add_parser("generate",
        help="generate RTLIL, Verilog or CXXRTL from the design")
    p_generate.add_argument("-t", "--type", dest="generate_type",
        metavar="LANGUAGE", choices=["il", "cc", "v"],
        help="generate LANGUAGE (il for RTLIL, v for Verilog, cc for CXXRTL; default: file extension of FILE, if given)")
    p_generate.add_argument("generate_file",
        metavar="FILE", type=argparse.FileType("w"), nargs="?",
        help="write generated code to FILE")
    # amaranth.cli end

    p_size = p_action.add_parser("size",
        help="Run a generic synth script to query design size")
    p_size.add_argument("-v", "--verbose", action="store_true",
        help="Show full yosys output, not just stats")
    p_size.add_argument("-s", "--show", action="store_true",
        help="Emit show.dot file for the module")

    p_ucode = p_action.add_parser("microcode",
        help="Run the microcode assembler (ignores --module arg)")
    p_ucode.add_argument("-f", "--field-defs",
        metavar="FDEFS-FILE", help="emit field defines to FDEFS-FILE")
    p_ucode.add_argument("-x", "--hex",
        metavar="HEX-FILE", help="emit a hex file")

    return parser


def main_runner(parser, args, design, platform=None, name="top", ports=()):
    # amaranth.cli begin
    if args.action == "generate":
        fragment = Fragment.get(design, platform)
        generate_type = args.generate_type
        if generate_type is None and args.generate_file:
            if args.generate_file.name.endswith(".il"):
                generate_type = "il"
            if args.generate_file.name.endswith(".cc"):
                generate_type = "cc"
            if args.generate_file.name.endswith(".v"):
                generate_type = "v"
        if generate_type is None:
            parser.error("Unable to auto-detect language, specify explicitly with -t/--type")
        if generate_type == "il":
            output = rtlil.convert(fragment, name=name, ports=ports)
        if generate_type == "cc":
            output = cxxrtl.convert(fragment, name=name, ports=ports)
        if generate_type == "v":
            output = verilog.convert(fragment, name=name, ports=ports)
        if args.generate_file:
            args.generate_file.write(output)
        else:
            print(output)
    # amaranth.cli end

    if args.action == "size":
        fragment = Fragment.get(design, platform)
        rtlil_text = rtlil.convert(fragment, name=name, ports=ports)

        # Created from a combination of amaranth._toolchain.yosys and
        # amaranth.back.verilog. Script comes from nextpnr-generic.
        script = []
        script.append("read_ilang <<rtlil\n{}\nrtlil".format(rtlil_text))
        script.append("hierarchy -check")
        script.append("proc")
        script.append("flatten")
        script.append("tribuf -logic")
        script.append("deminout")
        script.append("synth -run coarse")
        # script.append("memory_map")
        script.append("opt -full")
        script.append("techmap -map +/techmap.v")
        script.append("opt -fast")
        script.append("dfflegalize -cell $_DFF_P_ 0")
        script.append("abc -lut 4 -dress")
        script.append("clean -purge")
        if args.show:
            script.append("show")
        script.append("hierarchy -check")
        script.append("stat")

        stdin = "\n".join(script)

        popen = subprocess.Popen(["yosys", "-"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            encoding="utf-8")
        stdout, stderr = popen.communicate(stdin)
        if popen.returncode:
            raise RunnerError(stderr.strip())

        if args.verbose:
            print(stdout)
        else:
            begin_re = re.compile(r"[\d.]+ Printing statistics.")
            end_re = re.compile(r"End of script.")
            capture = False
            # begin_l = 0
            # end_l = 0

            for i, l in enumerate(stdout.split("\n")):
                if begin_re.match(l):
                    capture = True

                if end_re.match(l):
                    capture = False

                if capture:
                    print(l)

    if args.action == "microcode":
        ucode = UCodeROM(field_defs=args.field_defs, hex=args.hex)
        ucode._MustUse__used = True


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--module", dest="module",
        metavar="MODULE", choices=["ALU", "Control", "DataPath", "Decode",
            "Top", "UCodeROM"], default = "Top", help="generate code for module.")

    # In amaranth.cli, these are passed straight to main_runner. We need
    # different main_runner depending on component.
    main_p = main_parser(parser)
    args = parser.parse_args()

    if args.action not in ("microcode"):
        if args.module == "ALU":
            mod = ALU(width=32)
        elif args.module == "Control":
            mod = Control()
        elif args.module == "DataPath":
            mod = DataPath()
        elif args.module == "Decode":
            mod = Decode()
        elif args.module == "Top":
            mod = Top()
        elif args.module == "UCodeROM":
            mod = UCodeROM()
        else:
            assert False
        ports = mod.ports()
    else:
        mod = None
        ports = None

    main_runner(parser, args, mod, ports=ports)
