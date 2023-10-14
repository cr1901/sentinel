from pathlib import Path

from doit.tools import run_once


DOIT_CONFIG = {
    "default_tasks": [],
}


def task__upstream_init():
    upstream_tests = Path("./tests/upstream/")
    submod = upstream_tests / "riscv-tests" / ".git"
    return {
        "actions": [f"cd {upstream_tests}",
                    "git submodule update --init --recursive"],
        "targets": [submod],
        "uptodate": [run_once],
    }


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
        "actions": [["mkdir", "-p", outdir]],
    }

    for source_file in isa_dir.glob('*.S'):
        bin_file = outdir / source_file.with_suffix("").name
        yield {
            "name": bin_file.name,
            "actions": [["riscv64-unknown-elf-gcc", source_file, *flags,
                         "-I", upstream_tests, "-I", macros_dir,
                         "-T", link_file, "-o", bin_file]],
            "file_dep": [source_file, cfg, link_file, submod],
            "targets": [bin_file],
        }


def task__dump_tests():
    upstream_tests = Path("./tests/upstream/")
    outdir = upstream_tests / "binaries"

    isa_dir = upstream_tests / "riscv-tests/isa/rv32ui"

    for source_file in map(lambda s: outdir / s.with_suffix("").name,
                           isa_dir.glob('*.S')):
        dump_file = source_file.with_suffix(".dump")
        yield {
            "name": dump_file.name,
            "actions": ["riscv64-unknown-elf-objdump --disassemble-all \
                        --disassemble-zeroes --section=.text \
                        --section=.text.startup --section=.text.init \
                        --section=.data %(dependencies)s > %(targets)s"],
            "file_dep": [source_file],
            "targets": [dump_file],
        }
