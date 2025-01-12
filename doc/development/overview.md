# Development Guide

(overview)=
## Overview

Sentinel uses a combination of the [PDM](https://pdm-project.org/en/latest/)
package/virtual environment manager and [DoIt](https://pydoit.org/) task runnner
for development. 

PDM and DoIt complement each other:

* In addition to managing packages and virtual environments, PDM leverages the
  [`[tool.pdm.scripts]` table](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/#writing-your-pyproject-toml)
  of `pyproject.toml` to create [shortcuts](https://pdm-project.org/en/latest/usage/scripts/)
  for running arbitrary commands/save typing. However, PDM by itself does not
  manage dependency/up-to-date information, and the command strings you can
  create are limited.
* DoIt, on the other hand, allows one to run arbitrary commands of arbitrary
  complexity, _and_ manage dependency up-to-date information via a
  [`dodo.py` file](https://pydoit.org/tasks.html#intro) and [database files](https://pydoit.org/globals.html).
  However, DoIt by itself knows nothing about package management.

I leverage both PDM and DoIt for increased flexibility to run tests, benchmarks,
and generate examples.

### PDM Scripts

Scripts defined in `[tool.pdm.scripts]` are the main
entry points for users and developers. Type `pdm run --list` for a list of
scripts. Example output is below:

```{prompt}
:language: text
:prompts: William@DESKTOP-3H1DSBV MINGW64 ~/Projects/FPGA/amaranth/sentinel,$
:modifiers: auto
William@DESKTOP-3H1DSBV MINGW64 ~/Projects/FPGA/amaranth/sentinel
$ pdm run --list
╭─────────────────────┬───────────┬────────────────────────────────────────────────────────╮
│ Name                │ Type      │ Description                                            │
├─────────────────────┼───────────┼────────────────────────────────────────────────────────┤
│ bench-luts          │ cmd       │ add stats to LUTs.csv                                  │
│ compile-upstream    │ cmd       │ regnerate riscv-test binaries                          │
│ demo                │ cmd       │ create AttoSoC Sentinel demo bitstream                 │
│ demo-rust           │ composite │ create AttoSoC Sentinel demo bitstream (Rust version)  │
│ doc                 │ cmd       │ sphinx-build doc/ doc/_build/                          │
│ doc-auto            │ cmd       │ sphinx-autobuild doc/ doc/_build/ --watch src/sentinel │
│ doc-linkck          │ cmd       │ sphinx-build doc/ doc/_linkcheck/ -b linkcheck         │
│ doit                │ cmd       │ escape hatch to call doit directly                     │
│ gen                 │ call      │ generate Sentinel Verilog file                         │
│ lint                │ composite │ lint Python and Rust sources                           │
│ plot-luts           │ cmd       │ plot LUTs.csv                                          │
│ riscof-all          │ cmd       │ run all RISCOF tests                                   │
│ riscof-override     │ cmd       │ run RISCOF with custom testfile                        │
│ rvformal            │ cmd       │ run a single RISC-V Formal test                        │
│ rvformal-all        │ composite │ run all RISC-V Formal tests                            │
│ rvformal-force      │ composite │ force-run a single RISC-V Formal test                  │
│ rvformal-status     │ cmd       │ list a single RISC-V Formal test's status              │
│ rvformal-status-all │ cmd       │ list all RISC-V Formal tests' status                   │
│ test                │ cmd       │ run all pytest tests                                   │
│ test-quick          │ cmd       │ run quick subset of pytest tests                       │
│ ucode               │ cmd       │ generate supplementary microcode files                 │
╰─────────────────────┴───────────┴────────────────────────────────────────────────────────╯
```

```{todo}
Use [`sphinxcontrib.programoutput`](https://sphinxcontrib-programoutput.readthedocs.io/en/latest/)
to generate an up-to-date list of commands?
```

_Not all scripts listed above are commonly used._ In particular, the following
scripts must pass as part of CI:

* `lint`: Lint using [`ruff`](https://docs.astral.sh/ruff/). Tested on releases
  only.
* `gen`, `demo`, `demo-rust`: Check that code/demo generation works. Tested
  with [both](../usage/installation.md#yosys-and-foss-toolchains) [YoWASP](https://yowasp.org/)
  and [OSS CAD Suite](https://github.com/YosysHQ/oss-cad-suite-build). I test
  the demos on:
  
  * [Lattice iCEstick](https://www.latticesemi.com/icestick) (not required
    to pass, because the demo [doesn't always fit!](../usage/quickstart.md#a-full-example-soc-in-amaranth))
  * [iCE40-HX8K Breakout Board](https://www.latticesemi.com/Products/DevelopmentBoardsAndKits/iCE40HX8KBreakoutBoard.aspx)
* `test-quick`, `rvformal-all`, and `riscof-all`: Run tests. Tested with
  [OSS CAD Suite](https://github.com/YosysHQ/oss-cad-suite-build). In
  particular, I have [issues with](testing.md#run-riscof-flow) testing RISCOF
  on Windows, so CI is Linux only for now.
* `doc`, `doc-test`: Check that docs build and doc tests pass. Tested on
  releases only, mainly as a lint since [ReadTheDocs](https://sentinel-cpu.readthedocs.io/en/latest/)
  builds docs automatically.

If necessary, the above PDM scripts invoke `doit`, which reads the `dodo.py`
file to find out how to do the actual work.[^1]

### DoIt Tasks

`doit` tasks are "low-level" tasks wrapped by the PDM scripts [above](#pdm-scripts).
_They should be treated as a private and subject to change._ Howevever, I provide
a `doit` PDM script to call `doit` directly if necessary. For instance, to
list available `doit` tasks (_including [private tasks](https://pydoit.org/tasks.html#private-hidden-tasks)_),
run `pdm doit list -p`:

```{prompt}
:language: text
:prompts: William@DESKTOP-3H1DSBV MINGW64 ~/Projects/FPGA/amaranth/sentinel,$
:modifiers: auto
William@DESKTOP-3H1DSBV MINGW64 ~/Projects/FPGA/amaranth/sentinel
$ pdm doit list -p
_build_sail              build SAIL RISC-V emulators in opam environment, compress
_clean_dut_ref_dirs      remove dut/ref directories from last RISCOF run
_compile_rust_firmware   compile Rust firmware and show size
_decompress_sail         decompress previously-built SAIL emulator
_demo                    create a demo bitstream (for benchmarking)
_formal_gen_files        copy Sentinel files and run RISC-V Formal's genchecks.py script
_formal_gen_sentinel     generate Sentinel subdir and Verilog in RISC-V Formal cores dir
_git_init                initialize git submodules, "doit list --all -p _git_init" for choices
_git_rev                 get git revision
_make_rand_firmware      create a baseline gateware for firmware development
_opam                    extract environment vars from opam
_program_rust_firmware   load Rust firmware image onto FPGA
_replace_rust_firmware   replace random firmware image inside baseline gateware with Rust program
_riscof_gen              run RISCOF's testlist command to prepare RISCOF files and directories
bench_luts               build "pdm demo" bitstream (if out of date), record LUT usage using LogLUTs
compile_upstream         compile riscv-tests tests to ELF, "doit list --all compile_upstream" for choices
list_sby_status          list "run_sby" subtasks' status, "doit list --all list_sby_status" for choices
plot_luts                build "pdm demo" bitstream (if out of date), plot LUT usage using LogLUTs
run_riscof               run RISCOF tests against Sentinel/Sail, and report results, removes previous run's artifacts
run_sby                  run symbiyosys flow on Sentinel, "doit list --all run_sby" for choices
ucode                    assemble microcode and copy non-bin artifacts to root
```

I've documented the `doit` tasks (but not subtasks) as a courtesy, and to make sure
developers/users don't get stuck. That said, **prefer running `pdm` as a
wrapper to `doit` rather than running `doit` directly.** 

```{note}
I make heavy use of [DoIt subtasks](https://pydoit.org/tasks.html#sub-tasks).
These are understandably excluded from default help output. Run
`pdm doit list --all [task]` to see all sub-tasks for a higher-level task.

For instance, the `run_sby:reg_ch0` subtask runs the [Register Check](https://github.com/YosysHQ/riscv-formal/blob/main/docs/procedure.md#register-checks)
for `riscv-formal`.
```

```{todo}
Decide whether to commit to treat all `doit` tasks as private/hidden or expose a set
to a user/developer (no leading underscore). Right now, I am not being consistent.

For instance, `_build_sail` is a command a developer might manually run in rare
cases, but is still currently private b/c of its niche use-case. Where's the
cutoff for marking private vs public?
```

```{todo}
Use [`sphinxcontrib.programoutput`](https://sphinxcontrib-programoutput.readthedocs.io/en/latest/)
to generate an up-to-date list of commands?
```

## Detailed Reference

Using PDM and DoIt to orchestrate changes, hacking on Sentinel can be
divided into roughly four areas:

1. Internals
2. Microcode
3. Support Code
4. Test Code

These, plus development guidelines, all have their own sections:

```{toctree}
:maxdepth: 2

Internal Structure <internals>
Microcode Primer <microcode>
support-code
Maintaining Tests <testing>
guidelines
```

## Footnotes
[^1]: `doit` tasks may invoke `pdm` again. _However, any further recursion
      than that is a bug :)._
