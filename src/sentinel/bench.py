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


STAT_CALC = """
${quiet} submod -name ALU top/alu.*
${quiet} submod -name UCodeROM top/control.ucoderom.*
${quiet} submod -name Control top/control.*
${quiet} submod -name DataPath top/datapath.*
${quiet} submod -name Decode top/decode.*
stat -json
"""


class ScriptType(Enum):
    # From nextpnr-generic. This is basically an upper bound on resource-usage.
    # However, it's limited to FFs and LUTs only (no memories).
    GENERIC = Template("""
${quiet} read_ilang << rtlil
${rtlil_text}
rtlil
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
    SYNTH = Template("""
${quiet} read_ilang << rtlil
${rtlil_text}
rtlil
${quiet} synth -lut 4
""" + STAT_CALC)

    ICE40 = Template("""
${quiet} read_ilang << rtlil
${rtlil_text}
rtlil
${quiet} synth_ice40
""" + STAT_CALC)

    ECP5 = Template("""
${quiet} read_ilang << rtlil
${rtlil_text}
rtlil
${quiet} synth_lattice -family ecp5
""" + STAT_CALC)

    GOWIN = Template("""
${quiet} read_ilang << rtlil
${rtlil_text}
rtlil
${quiet} synth_gowin
""" + STAT_CALC)

    XC7 = Template("""
${quiet} read_ilang << rtlil
${rtlil_text}
rtlil
${quiet} synth_xilinx
""" + STAT_CALC)

    CYCLONE5 = Template("""
${quiet} read_ilang << rtlil
${rtlil_text}
rtlil
${quiet} synth_intel_alm
""" + STAT_CALC)


# TODO: verbose and show.dot
def stats(m: Elaboratable, script: ScriptType | Template, debug=False):
    rtlil_text = rtlil.convert(m)

    if isinstance(script, ScriptType):
        script = script.value

    quiet = "" if debug else "tee -q"
    stdin = script.substitute(rtlil_text=rtlil_text, quiet=quiet)

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
    parser.add_argument("-d", action="store_true",
                        help="debug mode (print yosys stdout)")
    parser.add_argument("-s", choices=ScriptType,
                        default=ScriptType.ICE40,
                        help="toolchain script to run")
    parser.add_argument("-j", choices=ScriptType,
                        help="emit JSON instead of a table")
    args = parser.parse_args()

    stdout = stats(Top(), args.s, debug=args.d)

    if args.d or args.j:
        print(stdout)
    else:
        print(mk_table(json.load(stdout)))
