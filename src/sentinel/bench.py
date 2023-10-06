import argparse
import json
import subprocess
from enum import Enum
from itertools import chain
from string import Template

from io import StringIO
from amaranth import Elaboratable
from amaranth.back import rtlil
from tabulate import tabulate

from .top import Top


class RunnerError(Exception):
    pass


DESIGN = """
${quiet} read_ilang << rtlil
${rtlil_text}
rtlil
"""


STAT_CALC = """
${quiet} submod -name ALU top/alu.*
${quiet} submod -name UCodeROM top/control.ucoderom.*
${quiet} submod -name Control top/control.*
${quiet} submod -name DataPath top/datapath.*
${quiet} submod -name Decode top/decode.*
${quiet} ${write}
stat -json
"""


class ScriptType(Enum):
    @classmethod
    def from_argstr(cls, str_):
        for m in cls.__members__:
            if str(cls[m]) == str_:
                return cls[m]
        else:
            raise ValueError(f"{str_} is not a valid value of {cls}")

    # From nextpnr-generic. This is basically an upper bound on resource-usage.
    # However, it's limited to FFs and LUTs only (no memories).
    GENERIC = Template(DESIGN + """
${quiet} hierarchy -check
${quiet} proc
${quiet} flatten
${quiet} tribuf -logic
${quiet} deminout
${quiet} synth -run coarse
${quiet} memory_map
${quiet} opt -full
${quiet} techmap -map +/techmap.v
${quiet} opt -fast
${quiet} dfflegalize -cell $$_DFF_P_ 0
${quiet} abc -lut 4 -dress
${quiet} clean -purge
""" + STAT_CALC)

    # Yosys' internal cell libraries.
    SYNTH = Template(DESIGN + """
${quiet} synth -lut 4
""" + STAT_CALC)

    ICE40 = Template(DESIGN + """
${quiet} synth_ice40
""" + STAT_CALC)

    ECP5 = Template(DESIGN + """
${quiet} synth_lattice -family ecp5
""" + STAT_CALC)

    GOWIN = Template(DESIGN + """
${quiet} synth_gowin
""" + STAT_CALC)

    XC7 = Template(DESIGN + """
${quiet} synth_xilinx
""" + STAT_CALC)

    CYCLONE5 = Template(DESIGN + """
${quiet} synth_intel_alm
""" + STAT_CALC)


class CustomCommands:
    def __init__(self, cmds):
        cmds_list = []
        for c in cmds:
            cmds_list.extend(c[0].split(";"))

        self.cmds = cmds_list

    def template(self):
        quiet_cmds = ";".join(f"${{quiet}} {c}" for c in self.cmds)
        return Template(DESIGN + quiet_cmds + STAT_CALC)


# TODO: verbose and show.dot
def stats(m: Elaboratable, script: ScriptType | Template, debug=False,
          verilog=False):
    rtlil_text = rtlil.convert(m)

    if isinstance(script, ScriptType):
        script = script.value

    quiet = "" if debug else "tee -q"
    write = f"write_verilog {verilog}" if verilog else ""
    stdin = script.substitute(rtlil_text=rtlil_text, quiet=quiet, write=write)

    if debug:
        print(stdin)

    popen = subprocess.Popen(["yosys", "-Q", "-T", "-"],
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             encoding="utf-8")
    stdout, stderr = popen.communicate(stdin)
    if popen.returncode:
        raise RunnerError(stderr.strip())

    if not debug:
        # Find the start of the JSON from the stats command.
        for i, l in enumerate(StringIO(stdout).readlines()):
            if l[0] == "{":
                break

        # Restart read since we can't really put back a line...
        stdout = StringIO(stdout)
        stdout.readlines(i)  # Drain non-JSON lines.
        return stdout
    else:
        return stdout


def mk_table(st):
    def mk_table_rows():
        rows = []
        for m in mods:
            row = [m]
            for c in cells:
                num = st["modules"][m]["num_cells_by_type"].get(c)
                row.append(num if num else 0)
            rows.append(row)

        return rows

    unique_cells = set(chain.from_iterable(st["modules"][d]
                                           ["num_cells_by_type"]
                                           for d in st["modules"]))
    mods = []
    cells = []
    for c in sorted(unique_cells):
        if st["modules"].get("\\" + c):
            mods.append("\\" + c)
        else:
            cells.append(c)

    for m in st["modules"]:
        if m not in mods:
            mods.append(m)

    rows = mk_table_rows()
    design = ["Design"]
    design.extend([st["design"]["num_cells_by_type"][c] for c in cells])
    rows.append(design)

    hdr = ["Module"]
    hdr.extend(cells)
    return tabulate(rows, headers=hdr)


def main():
    parser = argparse.ArgumentParser(description="Sentinel size benchmarker")
    group = parser.add_argument_group()
    s_group = group.add_mutually_exclusive_group()
    s_group.add_argument("-s", choices=list(str(s) for s in ScriptType),
                         help="toolchain script to run",
                         default="ScriptType.ICE40")
    s_group.add_argument("-p", action="append", nargs=1,
                         help="semicolon-separated commands to run (allowed "
                         "multiple times)")
    parser.add_argument("-d", action="store_true",
                        help="debug mode (print yosys stdout)")
    parser.add_argument("-j", action="store_true",
                        help="emit JSON instead of a table")
    parser.add_argument("-v", metavar="FILE", type=str,
                        help="emit split verilog file")
    args = parser.parse_args()

    if args.p:
        script = CustomCommands(args.p).template()
    else:
        script = ScriptType.from_argstr(args.s)

    stdout = stats(Top(), script, debug=args.d, verilog=args.v)

    if args.d or args.j:
        print(stdout)
    else:
        print(mk_table(json.load(stdout)))
