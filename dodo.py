from pathlib import Path
import subprocess
from shutil import copy2, move, rmtree
import os
import re
import gzip
import hashlib
from itertools import chain
from functools import partial

from doit import task_params
# https://groups.google.com/g/python-doit/c/GFtEuBp82xc/m/j7jFkvAGH1QJ
from doit.action import CmdAction
from doit.tools import run_once, create_folder, result_dep, title_with_actions
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


# Iterate over multiple trees and remove them!
def rmtrees(paths):
    for p in paths:
        rmtree(p)


# Lambdas are unpickleable on Windows (works on *nix?!), and some tasks can
# be easily parallelized using multiprocessing if we use pickleable types.
# Custom titles were originally supplied using lambdas; work around the
# multiprocessing limitation this by dispatching to a single print_title
# function whose evaluation is deferred using partial. Note this runs before
# custom reporters (like MaybeSuppressReporter), and so can be combined.
def print_title(task, title):
    return title


# Generic tasks
def git_init(repo_dir):
    submod = repo_dir / ".git"
    return {
        "basename": "_git_init",
        "name": repo_dir.stem,
        "actions": [CmdAction("git submodule update --init --recursive",
                              cwd=repo_dir)],
        "targets": [submod],
        "uptodate": [run_once],
    }


def task_git():
    riscof_tests = Path("./tests/riscof/")

    yield {
        "basename": "_git_init",
        "name": None,
        "doc": "initialize git submodules, \"doit list --all -p _git_init\" "
               "for choices"
    }

    for p in [Path("./tests/upstream/riscv-tests"),
              Path("./tests/formal/riscv-formal"),
              riscof_tests / "sail-riscv", riscof_tests / "riscv-arch-test"]:
        yield git_init(p)


def task__git_rev():
    "get git revision"
    return {'actions': ["git rev-parse HEAD"]}


def task__demo():
    "create a demo bitstream (for benchmarking)"
    pyfiles = [s for s in Path("./src/sentinel").glob("*.py")] + \
              [Path("./examples/attosoc.py")]

    return {
        "actions": ["pdm demo -b build-bench"],
        "file_dep": pyfiles + [Path("./src/sentinel/microcode.asm")]
    }


# These two tasks do not require "pdm run" because I had trouble installing
# matplotlib into the venv. Intended usage in cases like mine is
# "doit bench_luts" or "doit plot_luts".
def task_luts():
    build_dir = Path("./build-bench")
    yosys_log = build_dir / "top.rpt"
    nextpnr_log = build_dir / "top.tim"
    luts_csv = Path("./LUTs.csv")
    pyfiles = [s for s in Path("./src/sentinel").glob("*.py")] + \
              [Path("./examples/attosoc.py")]

    yield {
        "basename": "bench_luts",
        "actions": [f"python -m logluts --yosys-log {yosys_log} "
                    f"--nextpnr-log {nextpnr_log} --git . --target ice40 "
                    f"--add-commit --csvfile {luts_csv}"
                    ],
        "targets": [luts_csv],
        "uptodate": [result_dep("_git_rev")],
        "verbosity": 2,
        "setup": ["_demo"],
        "file_dep": pyfiles + [Path("./src/sentinel/microcode.asm")],
        "doc": "build \"pdm demo\" bitstream (if out of date), record LUT usage using LogLUTs"  # noqa: E501
    }

    yield {
        "basename": "plot_luts",
        "actions": [f"python -m logluts --yosys-log {yosys_log} "
                    f"--nextpnr-log {nextpnr_log} --git . --target ice40 "
                    f"--plot --csvfile {luts_csv}"
                    ],
        "targets": [],
        "uptodate": [False],
        "verbosity": 2,
        "setup": ["_demo"],
        "file_dep": pyfiles + [Path("./src/sentinel/microcode.asm")],
        "doc": "build \"pdm demo\" bitstream (if out of date), plot LUT usage using LogLUTs"  # noqa: E501
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


# RISCOF
def opam_vars():
    out = subprocess.run("opam env", shell=True, stdout=subprocess.PIPE).stdout

    vars = os.environ.copy()
    for var in out.decode().replace("\n", " ").split("; "):
        if "export" in var or not var:
            continue
        tmp = var.split("=")
        k, v = tmp
        vars[k] = v

    return {"env": vars}


def compress(src, dst):
    with open(src, "rb") as fp:
        c_bytes = gzip.compress(fp.read())

    with open(dst, "wb") as fp:
        fp.write(c_bytes)


def decompress(src, dst):
    with open(src, "rb") as fp:
        d_bytes = gzip.decompress(fp.read())

    with open(dst, "wb") as fp:
        fp.write(d_bytes)

    os.chmod(dst, 0o775)


def run_with_env(cmd, cwd, env):
    return subprocess.run(cmd, cwd=cwd, env=env, shell=True).check_returncode()


def task__opam():
    "extract environment vars from opam"
    return {"actions": [(opam_vars,)], "verbosity": 2}


def task__decompress_sail():
    "decompress previously-built SAIL emulator"
    riscof_tests = Path("./tests/riscof/")
    comp_emu = riscof_tests / "bin/riscv_sim_RV32.gz"
    bin_emu = riscof_tests / "bin/riscv_sim_RV32"

    return {
        "actions": [(decompress, (comp_emu, bin_emu))],
        # No file dep to avoid dependency on building SAIL.
        "file_dep": [],
    }


def task__build_sail():
    "build SAIL RISC-V emulators in opam environment, compress"
    riscof_tests = Path("./tests/riscof/")
    emu = riscof_tests / "sail-riscv" / "c_emulator/riscv_sim_RV32"
    # FIXME: Imprecise.
    src_files = [s for s in (riscof_tests / "sail-riscv" / "model").glob("*.sail")]  # noqa: E501
    return {
        # TODO: Maybe make public?
        "title": partial(print_title, title="Building SAIL RISC-V emulators"),
        "actions": [(partial(run_with_env,
                             cmd="make ARCH=RV32 c_emulator/riscv_sim_RV32",
                             cwd=riscof_tests / "sail-riscv")),
                    # This is not a task of it's own because there shouldn't
                    # be a dependency on building SAIL just for running
                    # RISCOF in a just checked-out repo. Delegate to
                    # decompression routine instead. This task should be
                    # run manually.
                    (compress, (emu, riscof_tests / "bin/riscv_sim_RV32.gz"))],
        "verbosity": 2,
        "file_dep": src_files,
        "targets": [emu, riscof_tests / "bin/riscv_sim_RV32.gz"],
        "getargs": {
                "env": ("_opam", "env")
        }
    }


def task__riscof_gen():
    "run RISCOF's testlist command to prepare RISCOF files and directories"
    riscof_tests = Path("./tests/riscof/")
    riscof_work = riscof_tests / "riscof_work"

    sentinel_plugin = riscof_tests / "sentinel"
    config_ini = riscof_tests / "config.ini"

    return {
        "actions": [CmdAction("pdm run riscof testlist --config=config.ini "
                              "--suite=riscv-arch-test/riscv-test-suite/ "
                              "--env=riscv-arch-test/riscv-test-suite/env "
                              "--work-dir=riscof_work",
                              cwd=riscof_tests)],
        "targets": [riscof_work / "sentinel_isa_checked.yaml",
                    riscof_work / "sentinel_platform_checked.yaml",
                    riscof_work / "database.yaml",
                    riscof_work / "test_list.yaml"],
        "file_dep": [config_ini, sentinel_plugin / "sentinel_isa.yaml",
                     sentinel_plugin / "sentinel_platform.yaml"]
    }


# This is required because RISCOF expects dut/ref dirs to not exist.
def task__clean_dut_ref_dirs():
    "remove dut/ref directories from last RISCOF run"

    riscof_tests = Path("./tests/riscof/")
    riscof_work = riscof_tests / "riscof_work"

    dut_dirs = [s for s in riscof_work.glob("**/dut/")]
    ref_dirs = [s for s in riscof_work.glob("**/ref/")]

    return {
        "actions": [(rmtrees, (dut_dirs,)),
                    (rmtrees, (ref_dirs,))]
    }


def save_last_testfile(testfile):
    return {"last_testfile": testfile}


def last_testfile(task, values, testfile):
    with open(testfile, "rb") as fp:
        hash = hashlib.md5(fp.read()).hexdigest()

    task.value_savers.append(partial(save_last_testfile, hash))
    return values.get("last_testfile") == hash


# Task params is required because task-creation time is the only time where
# we can pass a command-line argument into uptodate. AFAICT, this still
# creates one single task regardless of input parameters. Also note that
# the param is still available in action string formatting (though I use
# f-strings instead to create relative paths).
#
# The uptodate check checks whether we've passed the same testfile in
# consecutively _by checking the file's MD5_. If the MD5 changed since the last
# run, then our report is, in fact, out-of-date, regardless of the testfile's
# location. Yes, this is all to support using custom testfiles :).
@task_params([{"name": "testfile", "short": "t",
               "default": "./tests/riscof/riscof_work/test_list.yaml",
               "help": "path to alternate test list"}])
def task_run_riscof(testfile):
    "run RISCOF tests against Sentinel/Sail, and report results, removes previous run's artifacts"  # noqa: E501
    riscof_tests = Path("./tests/riscof/")
    riscof_work = riscof_tests / "riscof_work"

    pyfiles = [s for s in Path("./src/sentinel").glob("*.py")]
    sail_plugin = riscof_tests / "sail_cSim"
    sentinel_plugin = riscof_tests / "sentinel"
    config_ini = riscof_tests / "config.ini"

    sailp_files = [sail_plugin / s for s in ("env/link.ld", "env/model_test.h",
                                             "__init__.py",
                                             "riscof_sail_cSim.py")]
    sentp_files = [sentinel_plugin / s for s in ("riscof_sentinel.py",
                                                 "env/link.ld",
                                                 "env/model_test.h",
                                                 "sentinel_isa.yaml",
                                                 "sentinel_platform.yaml")]

    # Support both absolute and relative paths from dodo.py root for "pdm run"
    # convenience.
    path_tf = Path(testfile)
    if not path_tf.is_absolute():
        path_tf = path_tf.absolute()

    vars = os.environ.copy()
    vars["PATH"] += os.pathsep + str(riscof_tests.absolute() / "bin")
    return {
        "title": partial(print_title, title="Running RISCOF tests"),
        "actions": [CmdAction("pdm run riscof run --config=config.ini "
                              "--suite=riscv-arch-test/riscv-test-suite/ "
                              "--env=riscv-arch-test/riscv-test-suite/env "
                              f"--testfile={path_tf} "
                              "--no-browser --no-clean",
                              cwd=riscof_tests,
                              env=vars)],
        "targets": [riscof_work / "report.html"],
        "verbosity": 2,
        "setup": ["_git_init:sail-riscv",
                  "_git_init:riscv-arch-test",
                  "_decompress_sail",
                  "_riscof_gen",
                  "_clean_dut_ref_dirs"],
        "file_dep": pyfiles + sailp_files + sentp_files + [
                        config_ini, Path("./src/sentinel/microcode.asm")],
        "uptodate": [partial(last_testfile, testfile=testfile)],
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
    "csrw_mip_ch0", "csrc_zero_mip_ch0", "csrw_mie_ch0", "csrc_zero_mie_ch0",
    "csrw_mstatus_ch0", "csrc_const_mstatus_ch0", "csrw_mtvec_ch0",
    "csrc_zero_mtvec_ch0", "csrw_mepc_ch0", "csrc_zero_mepc_ch0",
    "csrw_mvendorid_ch0", "csrc_zero_mvendorid_ch0", "csrw_marchid_ch0",
    "csrc_zero_marchid_ch0", "csrw_mimpid_ch0", "csrc_zero_mimpid_ch0",
    "csrw_mhartid_ch0", "csrc_zero_mhartid_ch0", "csrw_mconfigptr_ch0",
    "csrc_zero_mconfigptr_ch0", "csrw_misa_ch0", "csrc_zero_misa_ch0",
    "csrw_mstatush_ch0", "csrc_zero_mstatush_ch0", "csrw_mcountinhibit_ch0",
    "csrc_zero_mcountinhibit_ch0", "csrw_mtval_ch0", "csrc_zero_mtval_ch0",
    "csrw_mcycle_ch0", "csrc_zero_mcycle_ch0", "csrw_minstret_ch0",
    "csrc_zero_minstret_ch0", "csrw_mhpmcounter3_ch0",
    "csrc_zero_mhpmcounter3_ch0", "csrw_mhpmevent3_ch0",
    "csrc_zero_mhpmevent3_ch0", "csr_ill_eff_ch0", "csr_ill_302_ch0",
    "csr_ill_303_ch0", "csr_ill_306_ch0", "csr_ill_34a_ch0", "csr_ill_34b_ch0",
    "csr_ill_30a_ch0", "csr_ill_31a_ch0"
)


# This task is useful for when hacking on *.py files, but the RISC-V Formal
# config files haven't actually changed (and thus genchecks.py need not be
# run).
def task__formal_gen_sentinel():
    "generate Sentinel subdir and Verilog in RISC-V Formal cores dir"
    formal_tests = Path("./tests/formal/")
    cores_dir = formal_tests / "riscv-formal" / "cores"
    sentinel_dir = cores_dir / "sentinel"
    pyfiles = [s for s in Path("./src/sentinel").glob("*.py")]
    sentinel_v = sentinel_dir / "sentinel.v"

    return {
        "actions": [(create_folder, [cores_dir / "sentinel"]),
                    f"pdm gen -o {sentinel_v} -f"],
        "targets": [sentinel_v],
        "file_dep": pyfiles + [Path("./src/sentinel/microcode.asm")],
    }


def task__formal_gen_files():
    "copy Sentinel files and run RISC-V Formal's genchecks.py script"
    formal_tests = Path("./tests/formal/")
    cores_dir = formal_tests / "riscv-formal" / "cores"
    sentinel_dir = cores_dir / "sentinel"

    genchecks = formal_tests / "riscv-formal" / "checks" / "genchecks.py"
    disasm_py = formal_tests / "disasm.py"
    checks_cfg = formal_tests / "checks.cfg"
    wrapper_sv = formal_tests / "wrapper.sv"

    return {
        "actions": [(copy_, [disasm_py, sentinel_dir / disasm_py.name]),
                    (copy_, [checks_cfg, sentinel_dir / checks_cfg.name]),
                    (copy_, [wrapper_sv, sentinel_dir / wrapper_sv.name]),
                    CmdAction("python3 ../../checks/genchecks.py",
                              cwd=sentinel_dir)],
        "targets": [sentinel_dir / disasm_py.name,
                    sentinel_dir / checks_cfg.name,
                    sentinel_dir / wrapper_sv.name],
        "file_dep": [disasm_py, checks_cfg, wrapper_sv, genchecks]
    }


def maybe_disasm_move_vcd(sentinel_dir, root, sby_file):
    sby_dir: Path = sby_file.with_suffix("")
    trace_names = [t for t in (sby_dir / "engine_0").glob("trace*.vcd")]

    id_re = re.compile("[0-9]*$")
    for tn in trace_names:
        num = id_re.search(str(tn.stem))
        rel_tn = tn.relative_to(sentinel_dir)
        stem_id = sby_file.stem + num[0] if num else ""
        out_path = root / stem_id

        copy2(tn, out_path.with_suffix(".vcd"))
        ret = subprocess.run(["python3", "disasm.py", rel_tn,
                              stem_id], stdout=subprocess.PIPE,
                             cwd=sentinel_dir)
        ret.check_returncode()

        print(ret.stdout.decode("utf-8"))
        with open(out_path.with_suffix(".s"), "wb") as fp:
            fp.write(ret.stdout)


def task_run_sby():
    "run symbiyosys flow on Sentinel, \"doit list --all run_sby\" for choices"
    root = Path(".")
    formal_tests = Path("./tests/formal/")
    cores_dir = formal_tests / "riscv-formal" / "cores"
    sentinel_dir = cores_dir / "sentinel"
    pyfiles = [s for s in Path("./src/sentinel").glob("*.py")]
    genchecks = formal_tests / "riscv-formal" / "checks" / "genchecks.py"
    disasm_py = formal_tests / "disasm.py"
    checks_cfg = formal_tests / "checks.cfg"

    for c in SBY_TESTS:
        sby_file = (sentinel_dir / "checks" / c).with_suffix(".sby")
        yield {
            "name": c,
            "title": partial(print_title,
                             title=f"Running RISC-V Formal Test {c}"),
            "actions": [CmdAction(f"sby -f {sby_file.name}",
                                  cwd=sentinel_dir / "checks"),
                        (maybe_disasm_move_vcd, (sentinel_dir, root,
                                                 sby_file))],
            "targets": [sentinel_dir / "checks" / c / "status"],
            "file_dep": pyfiles + [genchecks, disasm_py, checks_cfg,
                                   Path("./src/sentinel/microcode.asm")],
            "verbosity": 2,
            "setup": ["_git_init:riscv-formal",
                      "_formal_gen_sentinel",
                      "_formal_gen_files"],
        }


# Customize the status task(s) to print all output on a single line.
# Think like autoconf scripts "checking for foo... yes"!
def echo_sby_status(checks_dir, c):
    # TODO: Handle "not run yet" if status doesn't exist? What about
    # "out-of-date"?
    with open(checks_dir / c / "status", "r") as fp:
        res = fp.read()

    if "FAIL" in res:
        print(f"{c}... FAIL")
    else:
        print(f"{c}... PASS")


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


# I figured out the correct invocations for compiling and objdump by running
# the autoconf script, compiling normally, and seeing which flags the compiler
# and objdump are invoked with. It might not be perfect (but seems to work
# fine).
def task_compile_upstream():
    "compile riscv-tests tests to ELF, \"doit list --all compile_upstream\" for choices"  # noqa: E501
    flags = "-march=rv32g -mabi=ilp32 -static -mcmodel=medany \
-fvisibility=hidden -nostdlib -nostartfiles"

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
        "uptodate": [run_once]
    }

    for source_file in chain(isa_dir.glob('*.S'), mmode_dir.glob('*.S')):
        if source_file.stem in UNSUPPORTED_UPSTREAM:
            continue

        elf_file = outdir / source_file.with_suffix(".elf").name
        bin_file = outdir / source_file.with_suffix("").name
        dump_file = elf_file.with_suffix(".dump")
        yield {
            "title": title_with_actions,
            "name": source_file.stem,
            # {dependencies}, {targets}, and {{targets}} don't work
            # for parallel (at least on Windows). But f-strings do.
            "actions": [f"riscv64-unknown-elf-gcc {source_file} {flags} "
                        f"-I {upstream_tests} -I {macros_dir} -I {env_dir} "
                        f"-T {link_file} -o {elf_file}",

                        "riscv64-unknown-elf-objcopy -O binary "
                        f"{elf_file} {bin_file}",

                        f"riscv64-unknown-elf-objdump --disassemble-all "
                        "--disassemble-zeroes --section=.text "
                        "--section=.text.startup --section=.text.init "
                        f"--section=.data {elf_file} > {dump_file}"],
            "file_dep": [source_file, cfg, link_file, submod],
            "targets": [elf_file, bin_file, dump_file],
            "setup": ["compile_upstream:mkdir"]
        }


# Rust firmware development
def task__make_rand_firmware():
    "create a baseline gateware for firmware development"
    pyfiles = [s for s in Path("./src/sentinel").glob("*.py")] + \
              [Path("./examples/attosoc.py")]
    build_dir = Path("./build-rust")
    rand_hex = build_dir / "rand.hex"
    rand_asc = build_dir / "rand.asc"

    return {
        "actions": ["pdm demo -b build-rust -r -x rand"],
        "targets": [rand_hex, rand_asc],
        "file_dep": pyfiles + [Path("./src/sentinel/microcode.asm")]
    }


def task__replace_rust_firmware():
    "compile rust firmware and replace image inside baseline gateware"
    rs_files = [s for s in chain(Path("sentinel-rt/examples").glob("*.rs"),
                                 Path("sentinel-rt/src").glob("*.rs"))] + \
               [s for s in Path(".").glob("*/Cargo.toml")] + \
               [Path("Cargo.toml")]
    attosoc_elf = Path("target/riscv32i-unknown-none-elf/release/examples/attosoc")  # noqa: E501
    build_dir = Path("./build-rust")
    rand_asc = build_dir / "rand.asc"
    rand_hex = build_dir / "rand.hex"
    firmware_hex = build_dir / "firmware.hex"
    top_asc = build_dir / "top.asc"
    top_bin = build_dir / "top.bin"

    return {
        "actions": ["pdm _rust-firmware",
                    f"pdm demo -b build-rust -n -g {attosoc_elf} -x firmware",
                    f"icebram {rand_hex} {firmware_hex} < {rand_asc} > {top_asc}",  # noqa: E501
                    f"icepack {top_asc} {top_bin}"],  # noqa: E501
        "targets": [top_bin],
        "setup": ["_make_rand_firmware"],
        "file_dep": rs_files + [rand_asc]
    }
