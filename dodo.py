from pathlib import Path
import os
import subprocess
from shutil import copy2

# https://groups.google.com/g/python-doit/c/GFtEuBp82xc/m/j7jFkvAGH1QJ
from doit.action import CmdAction
from doit.tools import run_once, create_folder


DOIT_CONFIG = {
    "default_tasks": [],
}


def task_formal_init():
    formal_tests = Path("./tests/formal/")
    submod = formal_tests / "riscv-formal" / ".git"
    return {
        "title": lambda _: "Initializing RISC-V Formal submodule",
        "actions": [CmdAction("git submodule update --init --recursive",
                              cwd=formal_tests)],
        "targets": [submod],
        "uptodate": [run_once],
    }


def task_formal_mkdir_copy_files():
    formal_tests = Path("./tests/formal/")
    submod = formal_tests / "riscv-formal" / ".git"
    cores_dir = formal_tests / "riscv-formal" / "cores"
    sentinel_dir = cores_dir / "sentinel"

    disasm_py = formal_tests / "disasm.py"
    checks_cfg = formal_tests / "checks.cfg"
    wrapper_sv = formal_tests / "wrapper.sv"

    # doit actions must return certain types. None is one of these, but
    # paths are not (like in copy2).
    def copy(src, dst):
        copy2(src, dst)

    return {
        "title": lambda _: "Moving formal cfg into RISC-V Formal submodule",
        "actions": [(create_folder, [cores_dir / "sentinel"]),
                    (copy, [disasm_py, sentinel_dir / disasm_py.name]),
                    (copy, [checks_cfg, sentinel_dir / checks_cfg.name]),
                    (copy, [wrapper_sv, sentinel_dir / wrapper_sv.name])],
        "targets": [sentinel_dir / disasm_py.name,
                    sentinel_dir / checks_cfg.name,
                    sentinel_dir / wrapper_sv.name],
        "file_dep": [disasm_py, checks_cfg, wrapper_sv, submod],
    }


def task_formal_gen_files():
    formal_tests = Path("./tests/formal/")
    cores_dir = formal_tests / "riscv-formal" / "cores"
    sentinel_dir = cores_dir / "sentinel"
    pyfiles = [s for s in Path("./src/sentinel").glob("*.py")]

    disasm_py = sentinel_dir / "disasm.py"
    checks_cfg = sentinel_dir / "checks.cfg"
    wrapper_sv = sentinel_dir / "wrapper.sv"
    sentinel_v = sentinel_dir / "sentinel.v"
    genchecks = formal_tests / "riscv-formal" / "checks" / "genchecks.py"

    # https://groups.google.com/g/python-doit/c/UtdhdKk-ixs/m/jw3Eo31TAgAJ
    def get_dep(mod):
        paths = [os.fspath(c) for c in Path(mod).glob("*.sby")] + \
            [os.fspath(sentinel_v)]
        return {"file_dep": paths}

    return {
        "title": lambda _: "Generating RISC-V Formal tests",
        "actions": [f"pdm gen -o {sentinel_v} -f",
                    CmdAction("python3 ../../checks/genchecks.py",
                              cwd=sentinel_dir),
                    (get_dep, [sentinel_dir / "checks"])
                    ],
        "targets": [sentinel_v],
        "file_dep": [disasm_py, checks_cfg, wrapper_sv, genchecks] + pyfiles,
    }


def task_run_sby():
    root = Path(".")
    formal_tests = Path("./tests/formal/")
    cores_dir = formal_tests / "riscv-formal" / "cores"
    sentinel_dir = cores_dir / "sentinel"

    def get_trace_dst(path):
        return root / path.with_suffix(".vcd").name

    def get_disasm_dst(path):
        return root / path.with_suffix(".s").name

    def maybe_disasm_move_vcd(path):
        sby_dir = sentinel_dir / "checks" / path.stem
        if (sby_dir / "engine_0" / "trace.vcd").exists():
            copy2(sby_dir / "engine_0" / "trace.vcd", get_trace_dst(path))

            rc = subprocess.Popen(["python3", "disasm.py",
                                   Path("checks") / path.stem / "engine_0" /
                                   "trace.vcd"],
                                  cwd=sentinel_dir).wait()

            if not rc:
                copy2(sentinel_dir / "disasm.s", get_disasm_dst(path))

    for c in Path(sentinel_dir / "checks").glob("*.sby"):
        yield {
            "name": c.stem,
            "title": lambda _, c=c: f"Running RISC-V Formal Test {c.stem}",
            "actions": [CmdAction(f"sby -f {c.name}",
                                  cwd=sentinel_dir / "checks")],
            "targets": [],
            "calc_dep": ["formal_gen_files"],
            "verbosity": 2,
            # TODO: Replace with clean if I can figure out how to do
            # dynamically-generated targets (might not be possible).
            "uptodate": [False]
        }

        yield {
            "name": f"{c.stem}_vcds",
            "title": lambda _, c=c: f"Generating VCD and disasm for RISC-V Formal Test {c.stem} (if failed)",  # noqa: E501
            "actions": [(maybe_disasm_move_vcd, [c])],
            "file_dep": [],
            "targets": [get_trace_dst(c), get_disasm_dst(c)],
            "task_dep": [f"run_sby:{c.stem}"],
            "verbosity": 2,
            "uptodate": [False]
        }


def task__upstream_init():
    upstream_tests = Path("./tests/upstream/")
    submod = upstream_tests / "riscv-tests" / ".git"
    return {
        "actions": [CmdAction("git submodule update --init --recursive",
                              cwd=upstream_tests)],
        "targets": [submod],
        "uptodate": [run_once],
    }


# I figured out the correct invocations for compiling and objdump by running
# the autoconf script, compiling normally, and seeing which flags the compiler
# and objdump are invoked with. It might not be perfect (but seems to work
# fine).
def task__compile_upstream():
    flags = "-march=rv32g -mabi=ilp32 -static -mcmodel=medany \
-fvisibility=hidden -nostdlib -nostartfiles".split(" ")

    upstream_tests = Path("./tests/upstream/")
    outdir = upstream_tests / "binaries"
    cfg = upstream_tests / "riscv_test.h"
    link_file = upstream_tests / "link.ld"
    submod = upstream_tests / "riscv-tests" / ".git"
    isa_dir = upstream_tests / "riscv-tests/isa/rv32ui"
    macros_dir = upstream_tests / "riscv-tests/isa/macros/scalar"

    yield {
        "name": "mkdir",
        "actions": [(create_folder, [outdir])],
    }

    for source_file in isa_dir.glob('*.S'):
        elf_file = outdir / source_file.with_suffix(".elf").name
        yield {
            "name": elf_file.name,
            "actions": [["riscv64-unknown-elf-gcc", source_file, *flags,
                         "-I", upstream_tests, "-I", macros_dir,
                         "-T", link_file, "-o", elf_file]],
            "file_dep": [source_file, cfg, link_file, submod],
            "targets": [elf_file],
        }


def task__create_raw():
    upstream_tests = Path("./tests/upstream/")
    outdir = upstream_tests / "binaries"

    isa_dir = upstream_tests / "riscv-tests/isa/rv32ui"

    for source_file in isa_dir.glob('*.S'):
        elf_file = outdir / source_file.with_suffix(".elf").name
        bin_file = outdir / source_file.with_suffix("").name
        yield {
            "name": bin_file.name,
            "actions": ["riscv64-unknown-elf-objcopy -O binary \
                        %(dependencies)s %(targets)s"],
            "file_dep": [elf_file],
            "targets": [bin_file],
        }


def task__dump_tests():
    upstream_tests = Path("./tests/upstream/")
    outdir = upstream_tests / "binaries"

    isa_dir = upstream_tests / "riscv-tests/isa/rv32ui"

    for elf_file in map(lambda s: outdir / s.with_suffix(".elf").name,
                        isa_dir.glob('*.S')):
        dump_file = elf_file.with_suffix(".dump")
        bin_file = elf_file.with_suffix("")
        yield {
            "name": dump_file.name,
            "actions": [f"riscv64-unknown-elf-objdump --disassemble-all \
                        --disassemble-zeroes --section=.text \
                        --section=.text.startup --section=.text.init \
                        --section=.data {elf_file} > %(targets)s"],
            "file_dep": [elf_file, bin_file],
            "targets": [dump_file],
        }
