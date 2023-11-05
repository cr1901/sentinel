from pathlib import Path
import subprocess
from shutil import copy2, move
from itertools import chain
from functools import partial

# https://groups.google.com/g/python-doit/c/GFtEuBp82xc/m/j7jFkvAGH1QJ
from doit.action import CmdAction
from doit.tools import run_once, create_folder, result_dep, \
    check_timestamp_unchanged
from doit.reporter import ConsoleReporter


# Overrides
# Tasks typically only skip printing titles if they're private. For the
# list_sby_status tasks, I want to skip the titles because it interfaces
# with their extra stdout when parallelism is on.
class MaybeSuppressReporter(ConsoleReporter):
    def execute_task(self, task):
        if task.meta and task.meta.get("suppress_reporter", False):
            pass
        else:
            super().execute_task(task)


DOIT_CONFIG = {
    "default_tasks": [],
    "action_string_formatting": "new",
    "reporter": MaybeSuppressReporter
}


# Helpers
# doit actions must return certain types. None is one of these, but
# paths are not (like in copy2).
def copy_(src, dst):
    copy2(src, dst)


# Ditto.
def move_(src, dst):
    move(src, dst)


# Lambdas are unpickleable on Windows (works on *nix?!), and some tasks can
# be easily parallelized using multiprocessing if we don't use lambdas.
# Custom titles were originally supplied using lambdas; work around the
# multiprocessing limitation this by dispatching to a single print_title
# function and using each tasks' "meta" field. Note this runs before
# custom reporters (like MaybeSuppressReporter), and so can be combined.
def print_title(task):
    if task.meta:
        return task.meta.get("title", "")
    else:
        return ""


def with_root_and_suffix(path, root, suffix):
    return root / path.with_suffix(suffix).name


def maybe_disasm_move_vcd(sentinel_dir, root, path):
    sby_dir = sentinel_dir / "checks" / path.stem

    cover = path.stem == "cover"

    if cover:
        trace_names = ("trace0.vcd", "trace1.vcd", "trace2.vcd")
    else:
        trace_names = ("trace.vcd",)

    for i, trace_name in enumerate(trace_names):
        if cover:
            maybe_path_with_num = path.parent / (path.stem + str(i) +
                                                 path.suffix)
        else:
            maybe_path_with_num = path

        if (sby_dir / "engine_0" / trace_name).exists():
            copy2(sby_dir / "engine_0" / trace_name,
                  with_root_and_suffix(maybe_path_with_num, root, ".vcd"))

            rc = subprocess.Popen(["python3", "disasm.py",
                                   Path("checks") / path.stem /
                                   "engine_0" / trace_name,
                                   maybe_path_with_num.stem],
                                  cwd=sentinel_dir).wait()

            if rc:
                return False

            # If successful, will produce a disasm.s
            rc = subprocess.Popen("riscv64-unknown-elf-objdump -d "
                                  f"-M numeric,no-aliases disasm-{maybe_path_with_num.stem}.o "  # noqa E501
                                  f"> disasm-{maybe_path_with_num.stem}.s",
                                  cwd=sentinel_dir, shell=True).wait()

            if rc:
                return False

            # Which we then copy to the root.
            copy2(sentinel_dir / f"disasm-{maybe_path_with_num.stem}.s",
                  with_root_and_suffix(maybe_path_with_num, root, ".s"))

    return True


# Customize the status task(s) to print all output on a single line.
# Think like autoconf scripts "checking for foo... yes"!
def echo_sby_status(checks_dir, c):
    with open(checks_dir / c / "status", "r") as fp:
        res = fp.read()

    if "FAIL" in res:
        print(f"{c}... FAIL")
    else:
        print(f"{c}... PASS")


# Private tasks
def task__git():
    return {'actions': ["git rev-parse HEAD"]}


def task__demo():
    build_dir = Path("./build")
    yosys_log = build_dir / "top.rpt"
    nextpnr_log = build_dir / "top.tim"
    pyfiles = [s for s in Path("./src/sentinel").glob("*.py")]

    return {
        "actions": ["pdm demo"],
        "targets": [yosys_log, nextpnr_log],
        "file_dep": pyfiles + [Path("./src/sentinel/microcode.asm")],
    }


# These two tasks do not require "pdm run" because I had trouble installing
# matplotlib into the venv. Intended usage in cases like mine is
# "doit bench_luts" or "doit plot_luts".
def task_bench_luts():
    "build \"pdm demo\" bitstream (if out of date), record LUT usage using LogLUTs"  # noqa: E501
    build_dir = Path("./build")
    yosys_log = build_dir / "top.rpt"
    nextpnr_log = build_dir / "top.tim"
    luts_csv = Path("./LUTs.csv")

    return {
        "actions": [f"python -m logluts --yosys-log {yosys_log} "
                    f"--nextpnr-log {nextpnr_log} --git . --target ice40 "
                    f"--add-commit --csvfile {luts_csv}"
                    ],
        "targets": [luts_csv],
        "file_dep": [yosys_log, nextpnr_log],
        "uptodate": [result_dep("_git")],
        "verbosity": 2
    }


def task_plot_luts():
    "build \"pdm demo\" bitstream (if out of date), plot LUT usage using LogLUTs"  # noqa: E501
    build_dir = Path("./build")
    yosys_log = build_dir / "top.rpt"
    nextpnr_log = build_dir / "top.tim"
    luts_csv = Path("./LUTs.csv")

    return {
        "actions": [f"python -m logluts --yosys-log {yosys_log} "
                    f"--nextpnr-log {nextpnr_log} --git . --target ice40 "
                    f"--plot --csvfile {luts_csv}"
                    ],
        "targets": [],
        "file_dep": [yosys_log, nextpnr_log],
        "uptodate": [False],
        "verbosity": 2
    }


def task_ucode():
    "assemble microcode and copy non-bin artifacts to root"
    ucode = Path("./src/sentinel/microcode.asm")
    hex_ = ucode.with_suffix(".asm_block_ram.hex")
    fdef = ucode.with_suffix(".asm_block_ram.fdef")

    return {
        "actions": ["python -m m5meta {ucodefile}",
                    (move_, (hex_, Path(".") / hex_.name)),
                    (move_, (fdef, Path(".") / fdef.name))
                    ],
        "params": [{
                    "name": "ucodefile",
                    "default": str(ucode)
                    }],
        "targets": [Path(".") / hex_.name, Path(".") / fdef.name],
        "file_dep": [ucode],
    }


# RISC-V Formal
SBY_TESTS = (
    "causal_ch0", "cover", "insn_addi_ch0", "insn_add_ch0", "insn_andi_ch0",
    "insn_and_ch0", "insn_auipc_ch0", "insn_beq_ch0", "insn_bgeu_ch0",
    "insn_bge_ch0", "insn_bltu_ch0", "insn_blt_ch0", "insn_bne_ch0",
    "insn_jalr_ch0", "insn_jal_ch0", "insn_lbu_ch0", "insn_lb_ch0",
    "insn_lhu_ch0", "insn_lh_ch0", "insn_lui_ch0", "insn_lw_ch0",
    "insn_ori_ch0", "insn_or_ch0", "insn_sb_ch0", "insn_sh_ch0",
    "insn_slli_ch0", "insn_sll_ch0", "insn_sltiu_ch0", "insn_slti_ch0",
    "insn_sltu_ch0", "insn_slt_ch0", "insn_srai_ch0", "insn_sra_ch0",
    "insn_srli_ch0", "insn_srl_ch0", "insn_sub_ch0", "insn_sw_ch0",
    "insn_xori_ch0", "insn_xor_ch0", "pc_bwd_ch0", "pc_fwd_ch0", "reg_ch0",
    "unique_ch0", "liveness_ch0",
    "csrw_mscratch_ch0", "csrc_any_mscratch_ch0", "csrw_mcause_ch0",
    "csr_ill_eff_ch0", "csrw_mip_ch0", "csrc_zero_mip_ch0", "csrw_mie_ch0",
    "csrc_zero_mie_ch0", "csrw_mstatus_ch0", "csrc_const_mstatus_ch0",
    "csrw_mtvec_ch0", "csrc_zero_mtvec_ch0", "csrw_mepc_ch0",
    "csrc_zero_mepc_ch0",
    # "csrw_misa_ch0", "csrc_zero_misa_ch0",
)


def task_formal_init():
    "initialize RISC-V Formal submodule"
    formal_tests = Path("./tests/formal/")
    submod = formal_tests / "riscv-formal" / ".git"
    return {
        "title": print_title,
        "actions": [CmdAction("git submodule update --init --recursive",
                              cwd=formal_tests)],
        "targets": [submod],
        "uptodate": [run_once],
        "meta": {
            "title": "Initializing RISC-V Formal submodule"
        }
    }


def task_formal_mkdir_copy_files():
    "copy Sentinel files in tests/formal to RISC-V Formal submodule"
    formal_tests = Path("./tests/formal/")
    submod = formal_tests / "riscv-formal" / ".git"
    cores_dir = formal_tests / "riscv-formal" / "cores"
    sentinel_dir = cores_dir / "sentinel"

    disasm_py = formal_tests / "disasm.py"
    checks_cfg = formal_tests / "checks.cfg"
    wrapper_sv = formal_tests / "wrapper.sv"

    return {
        "title": print_title,
        "actions": [(create_folder, [cores_dir / "sentinel"]),
                    (copy_, [disasm_py, sentinel_dir / disasm_py.name]),
                    (copy_, [checks_cfg, sentinel_dir / checks_cfg.name]),
                    (copy_, [wrapper_sv, sentinel_dir / wrapper_sv.name])],
        "targets": [sentinel_dir / disasm_py.name,
                    sentinel_dir / checks_cfg.name,
                    sentinel_dir / wrapper_sv.name],
        "file_dep": [disasm_py, checks_cfg, wrapper_sv, submod],
        "meta": {
            "title": "Moving formal cfg into RISC-V Formal submodule"
        }
    }


def task_formal_gen_files():
    "run RISC-V Formal's genchecks.py script using copied Sentinel inputs"
    formal_tests = Path("./tests/formal/")
    cores_dir = formal_tests / "riscv-formal" / "cores"
    sentinel_dir = cores_dir / "sentinel"
    pyfiles = [s for s in Path("./src/sentinel").glob("*.py")]

    disasm_py = sentinel_dir / "disasm.py"
    checks_cfg = sentinel_dir / "checks.cfg"
    wrapper_sv = sentinel_dir / "wrapper.sv"
    sentinel_v = sentinel_dir / "sentinel.v"
    genchecks = formal_tests / "riscv-formal" / "checks" / "genchecks.py"

    sby_files = [(sentinel_dir / "checks" / s).with_suffix(".sby")
                 for s in SBY_TESTS]

    return {
        "title": print_title,
        "actions": [f"pdm gen -o {sentinel_v} -f",
                    CmdAction("python3 ../../checks/genchecks.py",
                              cwd=sentinel_dir),
                    ],
        "targets": sby_files + [sentinel_v],
        "file_dep": [disasm_py, checks_cfg, wrapper_sv, genchecks] + pyfiles,
        "meta": {
            "title": "Generating RISC-V Formal tests"
        }
    }


def task_run_sby():
    "run symbiyosys flow on Sentinel, \"doit list --all run_sby\" for choices"
    root = Path(".")
    formal_tests = Path("./tests/formal/")
    cores_dir = formal_tests / "riscv-formal" / "cores"
    sentinel_dir = cores_dir / "sentinel"
    sentinel_v = sentinel_dir / "sentinel.v"

    sby_files = [(sentinel_dir / "checks" / s).with_suffix(".sby")
                 for s in SBY_TESTS]

    for c in sby_files:
        yield {
            "name": c.stem,
            "title": print_title,
            "actions": [CmdAction(f"sby -f {c.name}",
                                  cwd=sentinel_dir / "checks")],
            "targets": [sentinel_dir / "checks" / c.stem / "status"],
            "file_dep": [c, sentinel_v],
            "verbosity": 2,
            "meta": {
                "title": f"Running RISC-V Formal Test {c.stem}"
            }
        }

        yield {
            "name": f"{c.stem}_vcds",
            "title": print_title,
            "actions": [
                (maybe_disasm_move_vcd, (sentinel_dir, root, c))
            ],
            "file_dep": [sentinel_dir / "checks" / c.stem / "status"],
            "targets": [],
            "task_dep": [f"run_sby:{c.stem}"],
            "verbosity": 2,
            "uptodate": [check_timestamp_unchanged(str(sentinel_dir /
                                                       "checks" /
                                                       c.stem / "status"))],
            "meta": {
                "title": f"Generating VCD and disasm for RISC-V Formal Test {c.stem} (if exists)"  # noqa: E501
            }
        }


def task_list_sby_status():
    "list \"run_sby\" subtasks' status, \"doit list --all list_sby_status\" for choices"  # noqa: E501
    formal_tests = Path("./tests/formal/")
    cores_dir = formal_tests / "riscv-formal" / "cores"
    sentinel_dir = cores_dir / "sentinel"
    checks_dir = sentinel_dir / "checks"

    for c in SBY_TESTS:
        yield {
            "name": c,
            "actions": [(echo_sby_status, (checks_dir, c))],
            "file_dep": [sentinel_dir / "checks" / c / "status"],
            "verbosity": 2,
            "uptodate": [False],
            "meta": {
                "suppress_reporter": True
            }
        }


# Upstream
UNSUPPORTED_UPSTREAM = ("breakpoint",)


def task_upstream_init():
    "initialize riscv-tests submodule"
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
def task_compile_upstream():
    "compile riscv-tests tests to ELF, \"doit list --all compile_upstream\" for choices"  # noqa: E501
    flags = "-march=rv32g -mabi=ilp32 -static -mcmodel=medany \
-fvisibility=hidden -nostdlib -nostartfiles".split(" ")

    upstream_tests = Path("./tests/upstream/")
    outdir = upstream_tests / "binaries"
    cfg = upstream_tests / "riscv_test.h"
    link_file = upstream_tests / "link.ld"
    submod = upstream_tests / "riscv-tests" / ".git"
    isa_dir = upstream_tests / "riscv-tests/isa/rv32ui"
    mmode_dir = upstream_tests / "riscv-tests/isa/rv32mi"
    macros_dir = upstream_tests / "riscv-tests/isa/macros/scalar"
    env_dir = upstream_tests / "riscv-tests/env"

    yield {
        "name": "mkdir",
        "actions": [(create_folder, [outdir])],
    }

    for source_file in chain(isa_dir.glob('*.S'), mmode_dir.glob('*.S')):
        if source_file.stem in UNSUPPORTED_UPSTREAM:
            continue

        elf_file = outdir / source_file.with_suffix(".elf").name
        yield {
            "name": elf_file.name,
            "actions": [["riscv64-unknown-elf-gcc", source_file, *flags,
                         "-I", upstream_tests, "-I", macros_dir, "-I", env_dir,
                         "-T", link_file, "-o", elf_file]],
            "file_dep": [source_file, cfg, link_file, submod],
            "targets": [elf_file],
        }


def task_create_raw():
    "convert riscv-tests ELFs into raw bins for pytest, \"doit list --all create_raw\" for choices"  # noqa: E501
    upstream_tests = Path("./tests/upstream/")
    outdir = upstream_tests / "binaries"

    isa_dir = upstream_tests / "riscv-tests/isa/rv32ui"
    mmode_dir = upstream_tests / "riscv-tests/isa/rv32mi"

    for source_file in chain(isa_dir.glob('*.S'), mmode_dir.glob('*.S')):
        if source_file.stem in UNSUPPORTED_UPSTREAM:
            continue

        elf_file = outdir / source_file.with_suffix(".elf").name
        bin_file = outdir / source_file.with_suffix("").name
        yield {
            "name": bin_file.name,
            # {dependencies} and {targets} doesn't work for parallel
            # (at least on Windows). But f-strings do.
            "actions": ["riscv64-unknown-elf-objcopy -O binary "
                        f"{elf_file} {bin_file}"],
            "file_dep": [elf_file],
            "targets": [bin_file],
        }


def task_dump_tests():
    "dump listing of ELF files for debugging/pytest, \"doit list --all dump_tests\" for choices"  # noqa: E501
    upstream_tests = Path("./tests/upstream/")
    outdir = upstream_tests / "binaries"

    isa_dir = upstream_tests / "riscv-tests/isa/rv32ui"
    mmode_dir = upstream_tests / "riscv-tests/isa/rv32mi"

    for elf_file in map(partial(with_root_and_suffix, root=outdir,
                                suffix=".elf"),
                        chain(isa_dir.glob('*.S'), mmode_dir.glob('*.S'))):
        if elf_file.stem in UNSUPPORTED_UPSTREAM:
            continue

        dump_file = elf_file.with_suffix(".dump")
        bin_file = elf_file.with_suffix("")
        yield {
            "name": dump_file.name,
            "actions": [f"riscv64-unknown-elf-objdump --disassemble-all \
                        --disassemble-zeroes --section=.text \
                        --section=.text.startup --section=.text.init \
                        --section=.data {elf_file} > {dump_file}"],
            # {{targets}} does not work for parallel execution.
            # But f-strings do.
            "file_dep": [elf_file, bin_file],
            "targets": [dump_file],
        }
