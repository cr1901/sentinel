import json
import subprocess
from enum import Enum
from string import Template

from io import StringIO
from amaranth import Elaboratable
from amaranth.back import rtlil


class RunnerError(Exception):
    pass


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
stat -json
""")

    # Yosys' internal cell libraries.
    SYNTH = Template("""
${quiet} read_ilang << rtlil
${rtlil_text}
rtlil
${quiet} synth -lut 4
stat -json
""")

    ICE40 = Template("""
${quiet} read_ilang << rtlil
${rtlil_text}
rtlil
${quiet} synth_ice40
stat -json
""")

    ECP5 = Template("""
${quiet} read_ilang << rtlil
${rtlil_text}
rtlil
${quiet} synth_lattice -family ecp5
stat -json
""")

    GOWIN = Template("""
${quiet} read_ilang << rtlil
${rtlil_text}
rtlil
${quiet} synth_gowin
stat -json
""")

    XC7 = Template("""
${quiet} read_ilang << rtlil
${rtlil_text}
rtlil
${quiet} synth_xilinx
stat -json
""")

    CYCLONE5 = Template("""
${quiet} read_ilang << rtlil
${rtlil_text}
rtlil
${quiet} synth_intel_alm
stat -json
""")


# TODO: verbose and show.dot
def stats(m: Elaboratable, script: ScriptType | Template):
    rtlil_text = rtlil.convert(m)

    if isinstance(script, ScriptType):
        script = script.value

    stdin = script.substitute(rtlil_text=rtlil_text, quiet="tee -q")

    popen = subprocess.Popen(["yosys", "-Q", "-T", "-"],
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             encoding="utf-8")
    stdout, stderr = popen.communicate(stdin)
    if popen.returncode:
        raise RunnerError(stderr.strip())

    # Find the start of the JSON from the stats command.
    for i, l in enumerate(StringIO(stdout).readlines()):
        if l[0] == "{":
            break

    # Restart read since we can't really put back a line...
    stdout = StringIO(stdout)
    stdout.readlines(i)  # Drain non-JSON lines.
    return json.load(stdout)
