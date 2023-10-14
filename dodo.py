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

    # No harm in running once. FIXME: Unix-ism.
    yield {
        "name": "mkdir",
        "actions": [["mkdir", "-p", outdir]],
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
