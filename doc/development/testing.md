# Testing Sentinel

```{todo}
As is [custom](./overview.md#doit-tasks), although public and documented, the
DoIt tasks should be considered unstable; `pdm run [any-script-besides-doit]`
should be preferred. Any advice to use `doit` directly on this page is because
"I haven't made the ergonomics better yet".
```

Sentinel tests are divided into four categories, under the `test` directory
at the root:

|Name/Path |Description                            |Depends On (Nonexhaustive)                                           |
|----------|---------------------------------------|---------------------------------------------------------------------|     
|`sim`     |Bespoke simple tests                   |[`pytest`], {class}`~amaranth:amaranth.sim.Simulator`                |
|`upstream`|RISC-V unit tests maintained [upstream]|[`pytest`], {class}`~amaranth:amaranth.sim.Simulator`                |
|`formal`  |RISC-V Formal test suite               |[`riscv-formal`], [`sby`], [`yosys`], [`boolector`]                  |
|`riscof`  |Tests against RISC-V specification     |[`riscof`], [`sail-riscv`], {class}`~amaranth:amaranth.sim.Simulator`|

Tests categories are roughly ordered in finding the most egregious bugs quickly
before spending more computing effort on more subtle bugs. E.g. if a `sim` test
fails, there is _definitely_ something very wrong such that no other test suite
is likely to pass. `sim`, `upstream`, and a single `riscof` test are likely to
fail quickly if there's something wrong, while `formal` and the full `riscof`
suite will take longer, especially on more subtle bugs not found by `sim` and
`upstream`.

[upstream]: https://github.com/riscv-software-src
[`yosys`]: https://github.com/YosysHQ/yosys
[`pytest`]: https://docs.pytest.org/en/stable/
[`riscv-formal`]: https://github.com/YosysHQ/riscv-formal
[`sby`]: https://github.com/YosysHQ/sby
[`boolector`]: https://github.com/Boolector/boolector
[`riscof`]: https://github.com/riscv-software-src/riscof
[`sail-riscv`]: https://github.com/riscv/sail-riscv

## Prerequisites

Before running tests, make sure all submodules are checked out:

```
git clone --recurse-submodules https://github.com/cr1901/sentinel
```

or

```
git clone https://github.com/cr1901/sentinel
cd sentinel
git submodule update --init --recursive
```

While I split the dependencies in the table [above](#testing-sentinel), I
assume for testing you'll be focusing on all categories. To that end, make sure
`pytest`, `doit`, `click`, `Verilog_VCD`, `riscof` (_Linux only_), `sby`,
`riscv64-unknown-elf-gcc`, `boolector`, and `yosys` are installed. The first
five can be installed using the following:

```
pdm install -G dev [riscof]
```

See {ref}`here <dep-hints>` for hints on how to get `sby`, `riscv64-unknown-elf-gcc`
`yosys`, and `boolector`. _The [WASM](../usage/installation.md#yosys-and-foss-toolchains)
versions are not supported for testing at this time._

## Sim And Upstream

```{note}
Nominally, I'd want doc tests to _also_ be controlled by `pytest`, using
[`pytest-sphinx`](https://github.com/twmr/pytest-sphinx). However, I
[can't get it to work](https://github.com/twmr/pytest-sphinx/issues/65)
consistently. In the interim, use `pdm doc-test` instead.
```

`sim` and `upstream` tests can be run using the same commands:

```
pdm test [-k ...] [--vcds]
```

or

```
pdm test-quick [-k ...] [--vcds]
```

If the `--vcds` option is provided, `pytest` will create a [VCD file](https://en.wikipedia.org/wiki/Value_change_dump)
with the same name as the test(s) at the Sentinel repo root, regardless of
whether the test(s) failed or not.

`sim` and `upstream` tests are very similar, in that they both are driven by
`pytest` and use an overlapping set of [fixtures](https://docs.pytest.org/en/stable/explanation/fixtures.html).
`pytest` in turn drives Amaranth's {class}`~amaranth:amaranth.sim.Simulator`
via the [`pytest-amaranth-sim`](https://github.com/cr1901/pytest-amaranth-sim)
plugin.

Diferences between `sim` and `upstream` tests include:

* `sim` tests are handcrafted assembly strings using [bronzebeard](https://github.com/theandrew168/bronzebeard).
* `upstream` tests are raw binary _files_ assembled from the [riscv-tests] repo binaries.
* In the `upstream` tests, a fixture waits for each binary to either time
  out, or write a value to a specific address. The test fails if the test times
  out (65536 clocks), or the value written is not expected.
* `sim` tests, on the other hand, will use its own fixtures to run single
  (or batches of) instructions before pausing. During each pause, the simulation
  state is compared to a hand-calculated expected state; the test fails if they
  don't match.

Right now (11/5/2023), the difference between `test` and `test-quick` is
minimal; both commands run `sim` and `upstream` tests.

While tests are run via `pytest`, the [riscv-tests] binaries are generated
using the [`dodo.py`](https://pydoit.org) at the root of this repo. If you
need to regenerate binaries, assuming `riscv64-unknown-elf-gcc` is installed
and on the path already, use `pdm run compile-upstream`. This will also
check out the submodule and for you.

[riscv-tests]: https://github.com/riscv-software-src/riscv-tests

## RISC-V Formal

The RISC-V Formal Framework defines a Verilog [wrapper](https://github.com/YosysHQ/riscv-formal/blob/main/docs/rvfi.md)
over RISC-V designs, along with a [large set](https://github.com/YosysHQ/riscv-formal/tree/main/checks)
of Verilog code. The Verilog code contains `assert`s, which indicate properties
that a compliant RISC-V implementation should satisfy. With additional tooling
(that RISC-V Formal can invoke), it is possible to test that these properties
hold across time (clock cycles) from an initial state, using a technique called
[Bounded Model Checking][BMC] (BMC).

In short, BMC tests that `assert`ions hold by _intelligently_ trying every
combination of inputs during every clock cycle. It's [not known](https://en.wikipedia.org/wiki/P_versus_NP_problem)
whether BMC/[SAT solving](https://en.wikipedia.org/wiki/Boolean_satisfiability_problem)
is always faster than a worst-case brute-force search, but in practice there's
a speedup for real world problems. Testing Sentinel with RISC-V Formal is no
exception.

[BMC]: https://www.cs.cmu.edu/~emc/papers/Papers%20In%20Refereed%20Journals/Bounded%20Model%20Checking%20Using%20Satisfiablility%20Solving.pdf

### Read This First!

Before hacking the formal tests, I suggest reading the
[Procedure](https://github.com/YosysHQ/riscv-formal/blob/7793823fe3c281205093b1c5ac7a3aa772f5e223/docs/procedure.md)
and [Config](https://github.com/YosysHQ/riscv-formal/blob/7793823fe3c281205093b1c5ac7a3aa772f5e223/docs/config.md)
sections of the RISC-V Formal docs to get a feel, as they complement each other.
The Procedure describes the format of `checks.cfg`, while the Config section
list some Verilog macros available to the Verilog wrapper and `checks.cfg`.
Looking at the [quickstart](https://github.com/YosysHQ/riscv-formal/blob/7793823fe3c281205093b1c5ac7a3aa772f5e223/docs/quickstart.md),
and the configs for [PicoRV32](https://github.com/YosysHQ/riscv-formal/tree/7793823fe3c281205093b1c5ac7a3aa772f5e223/cores/picorv32)
and [SERV](https://github.com/YosysHQ/riscv-formal/tree/7793823fe3c281205093b1c5ac7a3aa772f5e223/cores/serv)
also helped me greatly :D. Most in-tree cores seem to follow the same file
structure; I follow suit, but ignore the generated Makefile from
`genchecks.py`.

I'm not sure if this is all documented in one place, but the overall flow of
RISC-V Formal is something like this:

* `genchecks.py` reads `checks.cfg` and generates Verilog and config (`cfg`)
  files for [SymbiYosys](https://github.com/YosysHQ/sby)/`sby`. It also copies
  your CPU and wrapper Verilog files to a place that `sby` can find it, and
  provides a `Makefile` for invoking `sby`.
  
  `sby` is a driver program that automates common verification tasks based
  on `cfg` files. _It is [very doable](https://github.com/cr1901/spi_tb?tab=readme-ov-file#manual-yosys-smtbmc-flow)
  to go without `sby` for your own verification flow_. However, RISC-V Formal
  uses `sby`, and there's no real advantage for me to bypass it using `doit`.
* `sby` calls [`yosys`] to convert the all the Verilog code emitted/copied by
  `genchecks.py` into a description of your circuit in a standardized
  [format](https://smt-lib.org/papers/smt-lib-reference-v2.0-r10.12.21.pdf)
  for [SMT](https://en.wikipedia.org/wiki/Satisfiability_modulo_theories) solvers.
* `sby` then calls [`yosys-smtbmc`] (provided with `yosys`), which annotates
  the SMTv2 file(s) in the previous step to create an SMT problem that
  corresponds to BMC, as described [above](#risc-v-formal).
* `yosys-smtbmc` calls [`boolector`], an SMT solver, and waits for the solver
  to determine whether your design passes BMC.
* Once `boolector` finishes, `yosys-smtbmc` will interpret from `boolector`
  and construct various files describing the results, including VCDs. They
  are written to paths managed by `sby`.
* Optionally, call `disasm.py` to generate disassemblies from VCDs managed by
  `sby`.

Yes, there are a number of dependencies for running RISC-V Formal programs :).

The following sections up to [RISCOF](#riscof) (exclusive) assume some
familiarity with the above docs and the RISC-V Formal flow. 

[`yosys-smtbmc`]: https://github.com/YosysHQ/yosys/blob/main/backends/smt2/smtbmc.py

### Run RISC-V Formal Flow

To run the RISC-V Formal from the Sentinel repo:

```
pdm rvformal-all [-n num_cores]
```

```{note}
`doit` does not provide parallel task synchronization when `-n` is used.
I have a workaround in the `rvformal-all` script to [call](https://pdm-project.org/en/latest/usage/scripts/#composite)
`doit run_sby:setup` and force serialization until all files are generated.
Please do not remove it :).
```

Alternatively, to run a single test, useful for when a single test is failing:

```
pdm rvformal test-name
```

You can run `rvformal-status test-name` or `rvformal-status-all` to query
whether a check whether a previously-run check has succeeded or failed.
_This will run the test if it has not been run yet._

When I originally wrote the `dodo.py`, I had the need to rerun RISC-V Formal
tasks that succeeded without the inputs having meaningully changed (`doit` by
default checks file hashes, not timestamps). I unfortunately don't quite
remember the context, nor whether I fixed this issue or not. But just in case,
you can run `rvformal-force test-name` to force-run a test and ignore
dependency info. Alternatively, `pdm doit forget run_sby` can reset the
dependency logic for _all_ checks.

### How This Repo Invokes RISC-V Formal

Right now, I don't want to commit any specific version of Sentinel to
RISC-V Formal, so I maintain its RISC-V Formal config files in this repo
under `tests/formal`. These include:

* `checks.cfg`- RISC-V Formal config file passed to
  [`genchecks.py`](https://github.com/YosysHQ/riscv-formal/blob/7793823fe3c281205093b1c5ac7a3aa772f5e223/checks/genchecks.py),
  which actually generates the tests.
* `wrapper.sv`- RISC-V Formal wrapper that wraps the generated Verilog of
  {class}`sentinel.formal.FormalTop`.
* `disasm.py`- Create a disassembly from a [VCD file](https://en.wikipedia.org/wiki/Value_change_dump)
  of a failing test. Not actually used by RISC-V Formal itself, but every
  other core has it :). Mine is slightly modified to play nice with `doit`'s
  parallel tasks (generate unique filenames).

The `rvformal` and `rvformal-all` `pdm` scripts perform some housekeeping such
as generating Sentinel's Verilog code and copying the above files into the
`riscv-formal` source tree at `cores/sentinel`; as explicitly stated by RISC-V
Formal's [README.md](https://github.com/YosysHQ/riscv-formal/blob/7793823fe3c281205093b1c5ac7a3aa772f5e223/README.md):

> Out of tree generation with genchecks.py is not currently supported.

`genchecks.py` in turn [creates](https://github.com/YosysHQ/riscv-formal/blob/7793823fe3c281205093b1c5ac7a3aa772f5e223/checks/genchecks.py#L819-L848) many [SymbiYosys](https://github.com/YosysHQ/sby)/`sby` config
files and a `Makefile` in `cores/sentinel/checks` at the `riscv-formal` root.
The generated Makefile is not complicated; it simply invokes `sby [check_cfg_file]`
for each available check, and so I elect to use `pdm`/`doit` to run checks.

If `doit` finds any VCD files in `cores/sentinel/checks` after a test, which
usually, _but not always_ (e.g. `cover`) indicates a failed check, `doit` will
copy the VCD to the Sentinel repo root. Additionally, `doit` will invoke
`disasm.py` to create a disassembly that corresponds to the RISC-V instructions
found in the VCD file. The disassembly and VCD files will have the same name as
the check, but with `.s` and `.vcd` extensions respectively.

The following checks, derived from the `sby` config file names (they
correspond to sections in
[Procedure](https://github.com/YosysHQ/riscv-formal/blob/7793823fe3c281205093b1c5ac7a3aa772f5e223/docs/procedure.md)
nicely enough), are available:

```{note}
This list should reflect the `SBY_TESTS` tuple in `dodo.py`. It may
occassionally be out of date.
```

* `causal_ch0`
* `cover`
* `insn_addi_ch0`
* `insn_add_ch0`
* `insn_andi_ch0`
* `insn_and_ch0`
* `insn_auipc_ch0`
* `insn_beq_ch0`
* `insn_bgeu_ch0`
* `insn_bge_ch0`
* `insn_bltu_ch0`
* `insn_blt_ch0`
* `insn_bne_ch0`
* `insn_jalr_ch0`
* `insn_jal_ch0`
* `insn_lbu_ch0`
* `insn_lb_ch0`
* `insn_lhu_ch0`
* `insn_lh_ch0`
* `insn_lui_ch0`
* `insn_lw_ch0`
* `insn_ori_ch0`
* `insn_or_ch0`
* `insn_sb_ch0`
* `insn_sh_ch0`
* `insn_slli_ch0`
* `insn_sll_ch0`
* `insn_sltiu_ch0`
* `insn_slti_ch0`
* `insn_sltu_ch0`
* `insn_slt_ch0`
* `insn_srai_ch0`
* `insn_sra_ch0`
* `insn_srli_ch0`
* `insn_srl_ch0`
* `insn_sub_ch0`
* `insn_sw_ch0`
* `insn_xori_ch0`
* `insn_xor_ch0`
* `pc_bwd_ch0`
* `pc_fwd_ch0`
* `reg_ch0`
* `unique_ch0`
* `liveness_ch0`
* `csrw_mscratch_ch0`
* `csrc_any_mscratch_ch0`
* `csrw_mcause_ch0`
* `csrw_mip_ch0`
* `csrc_zero_mip_ch0`
* `csrw_mie_ch0`
* `csrc_zero_mie_ch0`
* `csrw_mstatus_ch0`
* `csrc_const_mstatus_ch0`
* `csrw_mtvec_ch0`
* `csrc_zero_mtvec_ch0`
* `csrw_mepc_ch0`
* `csrc_zero_mepc_ch0`
* `csrw_mvendorid_ch0`
* `csrc_zero_mvendorid_ch0`
* `csrw_marchid_ch0`
* `csrc_zero_marchid_ch0`
* `csrw_mimpid_ch0`
* `csrc_zero_mimpid_ch0`
* `csrw_mhartid_ch0`
* `csrc_zero_mhartid_ch0`
* `csrw_mconfigptr_ch0`
* `csrc_zero_mconfigptr_ch0`
* `csrw_misa_ch0`
* `csrc_zero_misa_ch0`
* `csrw_mstatush_ch0`
* `csrc_zero_mstatush_ch0`
* `csrw_mcountinhibit_ch0`
* `csrc_zero_mcountinhibit_ch0`
* `csrw_mtval_ch0`
* `csrc_zero_mtval_ch0`
* `csrw_mcycle_ch0`
* `csrc_zero_mcycle_ch0`
* `csrw_minstret_ch0`
* `csrc_zero_minstret_ch0`
* `csrw_mhpmcounter3_ch0`
* `csrc_zero_mhpmcounter3_ch0`
* `csrw_mhpmevent3_ch0`
* `csrc_zero_mhpmevent3_ch0`
* `csr_ill_eff_ch0`
* `csr_ill_302_ch0`
* `csr_ill_303_ch0`
* `csr_ill_306_ch0`
* `csr_ill_34a_ch0`
* `csr_ill_34b_ch0`
* `csr_ill_30a_ch0`
* `csr_ill_31a_ch0`

### Sentinel Formal Top-Level Module

```{eval-rst}
.. automodule:: sentinel.formal
    :members:
```

## RISCOF

RISCOF, the RISC-V Compatibility Framework, is the test suite that
[RISC-V International](https://riscv.org/) requires implementations to pass as
part of approval for licensing trademarks, etc. I don't plan to get involved
in that stuff right now, but it's nice to be prepared with evidence such that
I can say "Here is Sentinel passing your tests. Now I can say it implements
RISC-V!"

Compared to RISC-V Formal, RISCOF is not comprehensive, and the docs say as
much:

> Passing the RISC-V Architectural Tests does not mean that the design complies
> with the RISC-V Architecture. These are only a basic set of tests checking
> important aspects of the specification without focusing on details.
>
> The RISC-V Architectural Tests are not a substitute for rigorous design
> verification.

(riscof-tests)=
_However_, RISCOF tests are tested against the software version of the RISC-V
specification itself, the [SAIL-RISCV](https://github.com/riscv/sail-riscv)
[Golden Model](https://lists.riscv.org/g/tech-golden-model). AFAICT, the
[RISCOF tests](https://github.com/riscv-non-isa/riscv-arch-test) are based on
the [riscv-tests] I use for the `upstream` category, but modified to support
testing against the SAIL model.

While RISC-V Formal is a well-designed test suite that has helped me find a
number of legitimate bugs, and tests more comprehensively than RISCOF, it
is, AFAIK, an alternate software implementation of the RISC-V specification.
Although unlikely, it is _possible_ in theory for all tests in other categories
to pass while RISCOF tests fail. Such a failure would indicate something
particularly subtle is wrong, including (in somewhat order of most to least
likely):

* Sentinel CPU
* My RISCOF plugin :)
* My other tests
* RISC-V Formal
* RISCOF/SAIL-RISCV/The specification itself

Even if the bug is ultimately in my code, a particularly subtle bug would
require me to talk to other people more directly involved in formalizing the
RISC-V spec to get feedback and advice.

In short, I include RISCOF tests to show that "Sentinel passes the tests that
RISC-V International expects an implementation to pass". If they fail, they
can also help me find bugs in my code as well as others :).

### Run RISCOF Flow

```{todo}
At present, _RISCOF tests presently require Linux to run_ because I had trouble
installing an OCaml toolchain on Windows at the time. In addition, I recall
a few *nix-isms in the RISCOF Python package. I will fix this in the future.
```

Running RISCOF is orchestrated by the [`dodo.py`](https://pydoit.org) at the
root of this repo. To check out the RISCOF submodule and run the flow, run:

```
pdm run riscof-all
```

The above will:

* Check out the RISCOF submodule for you.
* Decompress the SAIL emulator, if necessary.
* Generate a `riscof_work` directory full of config files and tests for you
  using `riscof testfile`, subject to DoIt's dependency management.
* Delete a number of output subdirectories (`dut` and `ref`) under
  `riscof_work`; `riscof` expects these to be empty before running a test.
  This will _not_ fail if the various `dut` and `ref` directories don't exist.
* Finally, run RISCOF flow using `riscof run`.

The results of `riscof run` will be available under `riscof_work/report.html`,
and the various `dut` and `ref` subdirectories provided for each test under
`rv32i_m` (ELF files, disassemblies, etc).

One of the files generated in `riscof_work` will be a `test_list.yaml`.
Occassionally, it may be useful to truncate the `test_list.yaml` to run a
subset of generated tests. Since RISCOF currently (as of 11/11/2023)
[doesn't make](https://github.com/riscv-software-src/riscof/issues/100#issuecomment-1806772615)
running individual tests easy, use the following:

```
pdm run riscof-override /path/to/new/test_list.yaml
```

_Note that if the "delete a number of subdirectories" step needs to run, all
`dut` and `ref` subdirectories possibly containing interesting results will
be deleted!_ In addition, checking whether `test_list.yaml` is up-to-date is
hash based; two separate `test_list.yaml` files with the same exact contents
will be considered the same file to `riscof-override`.

### How This Repo Integrates RISCOF

RISCOF requires {ref}`several inputs <riscof:inputs>` to run. Although you must
have an existing SAIL binary, RISCOF takes care of {ref}`installing <riscof:plugin_models>`
a SAIL plugin and `config.ini` for you. Like in [SERV](https://github.com/olofk/serv/tree/main/verif),
the SAIL (_and Sentinel_) plugins have been modified to expect `riscv64-unknown-elf-gcc`,
even for 32-bit, but otherwise need not be modified further. Additionally,
`config.ini` is set up properly and should also be a pretty static file.

The required [`sail-riscv`][] and [`riscv-arch-test`](https://github.com/riscv-non-isa/riscv-arch-test)
repos are provided as submodules for convenience. It's not clear to me that
RISCOF depends on any particular version of these repos. I haven't tried it
yet, but it should be safe to update these submodules independently of the
rest of RISCOF.

Updating submodules notwithstanding, it seems to me outside of a
full upgrade of RISCOF (not exposed by `pdm` scripts or `doit`), RISCOF input
files are mostly static. Test development focuses on modifying files in the
`sentinel` directory. I've mostly left RISCOF alone after getting it working;
as I upgrade RISCOF and submodules, I'll update these docs based on my
experiences.

The `sentinel` directory implements the {ref}`DUT plugin <riscof:plugins>` for
Sentinel. The files contained within are explained in {ref}`riscof:plugin_directory`.
Similar the the `upstream` tests, the Sentinel {class}`plugin <riscof:riscof.pluginTemplate.pluginTemplate>`
wraps the Amaranth {class}`~amaranth:amaranth.sim.Simulator`. In fact, several
pieces of code (which form the basis of `pytest` fixtures) are imported from
the top-level `test` directory into the plugin! The main _functional_
differences from `upstream` tests are:

* A different set of {ref}`binaries <riscof-tests>` are used for the plugin.
* Instead of searching for a value written to a specific address, the plugin
  dumps its memory state to a file after a write to a specific address. RISCOF
  itself uses these files to compare Sentinel's behavior to the SAIL model. 

All this setup is summarized in {ref}`riscof:arch-tests`, with the following
caveat:

* Step 2 of {ref}`Section 7.1 <riscof:arch-tests>` of the RISCOF docs seems
  incorrect; `riscof` will set up the `sail_cSim` plugin for you as part of
  `riscof setup --dutname=sentinel` (although this step should not be necessary
  to run normally, and is currently not provided even in `dodo.py`).

### Rebuilding the SAIL Golden Model

Building the SAIL RISC-V Model is **tough**. It requires an [OCaml](https://ocaml.org/)
toolchain, and even after getting an environment set up, the C code that OCaml
generates takes 30+ minutes to compile with [LTO](https://en.wikipedia.org/wiki/Interprocedural_optimization).
I didn't want to go through this again, so I include a precompiled gzipped Linux
binary at `riscof/bin/riscv_sim_RV32.gz`. `pdm riscof-all`, `pdm riscof-override`,
and `doit` know how to `gunzip` the binary on demand.

The SAIL RISC-V emulators are written in a mix of C, [OCaml](https://ocaml.org/)
and the [`sail`](https://github.com/rems-project/sail) DSL. From a packaging
standpoint, the SAIL RISC-V emulators are OCaml packages whose dependencies
are described using the [`opam`](https://opam.ocaml.org/) package manager
and [`opam` files](https://opam.ocaml.org/doc/Manual.html#opam). On
Ubuntu 20.04, installing the prerequisites for the emulators looks something
like this:

```
sudo apt-get install opam  build-essential libgmp-dev z3 pkg-config zlib1g-dev
opam init -y --disable-sandboxing
opam switch create create ocaml-base-compiler.4.08.1
opam install sail -y
```

Then, to actually _rebuild_ the SAIL RISC-V emulators in a _hopefully_ turnkey
fashion, run `pdm doit _build_sail`. As with other `doit` tasks, this should
not be relied upon for normal development. Note that the actual build requires
`make`; `opam` only handles installing dependencies, and delegates to `make`
for building.

```{todo}
It'd be nice to remove the immediate dependency on `make`. Since we don't want
to _install_ the emulators in the system, it should be in principle possible to
`cd sail-riscv`, do `opam install . --deps-only`, and then build SAIL manually.
However, I [couldn't get that to work](https://stackoverflow.com/questions/50942323/opam-install-error-no-solution-found)...
```

As of 11/6/2023, the {ref}`build instructions <riscof:quickstart>`
provided by RISCOF documentation for the [SAIL RISC-V emulators](https://github.com/riscv/sail-riscv) are
[out-of-date](https://github.com/riscv-software-src/riscof/issues/88); I
didn't successfully compile the emulator until I did
`opam switch create ocaml-base-compiler.4.08.1`.
