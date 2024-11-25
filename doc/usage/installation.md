# Installation

## Prerequisites

Sentinel requires Python 3.11 or newer. It additionally uses [PDM](https://pdm.fming.dev/latest/)
as its package/dependency manager, and to orchestrate all things you can do
with its source code. I highly recommend installing [`pdm`](https://pdm-project.org)
version 2.20 or newer, at least until I work out the details of using Sentinel
without `pdm`. Use either `pip` or `pipx`, depending on your Python installation's
[recommendation](https://packaging.python.org/en/latest/specifications/externally-managed-environments/#guide-users-towards-virtual-environments):

```
pipx install pdm
```

If you don't have Python 3.11 or later installed, and cannot install it locally,
`pdm` can install one for you for any project using Sentinel as a dependency.
See [`pdm python`](https://pdm-project.org/en/latest/usage/project/#install-python-interpreters-with-pdm)
for details.

### Yosys And FOSS Toolchains

Amaranth, and by extension Sentinel, requires [yosys](https://github.com/YosysHQ/yosys),
which is not a Python package. Amaranth itself provides a `yosys` subset as
part of its `builtin-yosys` feature. Additionally, for creating demo
bitstreams, [nextpnr](https://github.com/YosysHQ/nextpnr/) is required.
the [YoWASP](https://yowasp.org/) project provides a
[full yosys binary](https://github.com/YoWASP/yosys) as a
[PyPI package](https://pypi.org/project/yowasp-yosys/). 

While [developing Sentinel](#development-environment), I personally use the
Windows/Linux/etc versions of `yosys` and other tools, for several reasons:

* It's what I am/was used to.
* Sometimes I need to modify the tools to test bug fixes. Rebuilding native
  tools is easier for me than rebuilding WASM tools.
* Tests would not work anyway; there's no [SAIL](https://github.com/riscv/sail-riscv)
  nor `riscv64-unknown-elf-gcc` WASM binaries yet (AFAIK).

_However_, for Verilog and Demo generation (e.g. everything inside the
[Quick Start](./quickstart.md)_, I support using `builtin-yosys`/YoWASP or
local tools. By default, local tools are used. You can install Amaranth with
the `builtin-yosys` feature and YoWASP by running:

```
pdm install -G yowasp
```

To swap from a local toolchain to YoWASP, use:

```
pdm use-yowasp
```

This installs a set of envrionment variables into `.env.toolchain` at the
source root. All commands run via `pdm` [get these variables](https://pdm-project.org/latest/usage/scripts/#env_file),
which in turn Amaranth uses to run Amaranth's `builtin-yosys` functionality
and alternate YoWASP versions of external tools.

To swap from YoWASP to a local toolchain, use:

```
pdm use-local
```

This removes the `.env.toolchain` file if present; `pdm` happily runs
without one.

<!-- ```{tip} You can install both a YoWASP environment and a local environment
separately and swap between them [using `pdm`](https://pdm-project.org/latest/usage/venv/#create-a-virtualenv-yourself)

Many `pdm` commands have a `--venv` parameter to distinguish virtual
environments (including the environment used from not providing `--venv`). This
is demonstrated in the `README.md` provided at the source root.
``` -->

```{todo}
Can `.env.toolchain` somehow be used per virtual environment (to allow
per-virtualenv toolchains)?
```

```{note}
I may eventually add example support for targets without a FOSS toolchain,
such as [Vivado](https://www.amd.com/en/products/software/adaptive-socs-and-fpgas/vivado.html).

I don't anticipate WASM binaries for any of these toolchains anytime soon, so
even if you opt to use the YoWASP flow, you will have to provide proprietary
toolchain binaries (or remote access to them) yourself.
```

If you want to hack on tests, where YoWASP doesn't currently work, and/or don't
feel like [building](https://github.com/YosysHQ/yosys/#building-from-source)
`yosys`, binaries are available from [OSS CAD Suite](https://github.com/YosysHQ/oss-cad-suite-build).
_Ensure `LD_PRELOAD` is not set if using OSS CAD Suite._ And of course, **make
sure `yosys` is on your `PATH`** :).

## As A Dependency

When a PyPI package is available, install Sentinel using:

```
pip install sentinel-cpu
```

In the interim, the main branch can be installed via:

```
pip install git+https://github.com/cr1901/sentinel@main
```

If you wish to follow the development branch, use this command instead:

```
pip install git+https://github.com/cr1901/sentinel@next
```

```{todo}
_I am still working out the details on using Sentinel outside of PDM._ There
are use cases, such as [LiteX](https://github.com/enjoy-digital/litex), but
I've decided to wait to implement this until another release.
```

### In A PDM Project

One intended workflow of Sentinel is in a mixed-language (Verilog, VHDL, Amaranth,
Chisel, etc) environment, where PDM manages the Python code or even the entire
project. In this case, dependencies should be managed by PDM.

When the PyPI package is available, run:

```
pdm add sentinel-cpu
```

at the root of your project. Otherwise, run:

```
pdm add sentinel@git+https://github.com/cr1901/sentinel@main
```

to bring in the main branch, or

```
pdm add sentinel@git+https://github.com/cr1901/sentinel@next
```

to bring in the development branch.

```{warning}
When advantageous, the `next` branch tracks upstream git packages without
pinning to a branch or commit (that's what `pdm.lock` is for). These include:

* [`amaranth`]
* [`amaranth-boards`]
* [`amaranth-soc`]
* [`amaranth-stdio`]

Additionally, some Amaranth packages/dependencies are still in flux and don't
have a stable release to track on PyPI. Until they do, the `main` branch
may _also_ depend on git dependencies without pinning.

However, if installing/using either branch breaks due to immediate dependencies
changing, I will make a release on `main`, and commit on `next` to correct the
breakage (and possibly add more tests to CI). See [here](https://iscinumpy.dev/post/bound-version-constraints/#tldr)
for rationale.
```

## Development Environment

Sentinel's source code is _also_ managed by PDM. To get started, check out a
copy of the source code and then run `pdm install`:

```sh
git clone https://github.com/cr1901/sentinel
cd sentinel
git submodule update --init --recursive
pdm install -G dev -G lint -G examples
```

The commands above will initialize a virtual environment consisting of:

* [Amaranth](https://amaranth-lang.org/), a Python embedded DSL for creating
  digital circuits.
* [m5meta](https://github.com/brouhaha/m5meta/) microcode assembler, without
  which Sentinel would optimize down to ~0 LUTs :).
* [pytest](https://pytest.org) for basic/regression testing.
* [DoIt](https://pydoit.org/) as a lower-level dependency-graph aware task
  orchestrator (called from `pdm`).
* [riscv-tests](https://github.com/riscv-software-src/riscv-tests), an older
  set of unit tests for RISC-V processors. Running these is done via `pytest`.
* [RISC-V Formal](https://github.com/YosysHQ/riscv-formal) to verify that
  desirable properties of Sentinel (such as "instructions write the correct
  destination") hold for all possible inputs over a bounded number of clock
  cycles after reset.
* [RISCOF](https://github.com/riscv-software-src/riscof/), the unit test
  framework that is maintained by RISC-V International themselves. This appears
  to have originally been derived from the `riscv-tests`, but is much more
  comprehensive.

Additionally, make sure the following are installed:

* [`yosys`](https://github.com/YosysHQ/yosys) and
  [`nextpnr-ice40`](https://github.com/YosysHQ/nextpnr/), as described [above](#yosys-and-foss-toolchains).
* [`boolector`](https://github.com/Boolector/boolector) SMT solver.

  ```{note} Boolector is no longer maintained. Eventually I will update to
  [Bitwuzla](https://github.com/bitwuzla/bitwuzla).
  ```
* [`SymbiYosys`](https://github.com/YosysHQ/sby) verification driver.
* `riscv64-unknown-elf-gcc` C/C++ compiler and assembler. 

  The binary name is hardcoded by scripts. In
  principle, the actual toolchain binary doesn't matter, but the scripts
  haven't been updated yet.
* `rustc`/`rustup` with the `riscv32i-unknown-none-elf` target.

  Rust is currently only required for certain example designs.
* The RISCOF tests also requires the [SAIL RISC-V emulator](https://github.com/riscv/sail-riscv).
  This is a pain to compile, so I provide a Linux binary (and eventually Windows
  if I can get OCaml to behave long enough. I _used_ to be able to install it
  just fine :'D!).

If you are having trouble finding binaries via package manager, `boolector` and
`SymbiYosys` are provided by [OSS CAD Suite](https://github.com/YosysHQ/oss-cad-suite-build),
and SiFive still provides downloads to usable GCC versions in an [archived repo](https://github.com/YosysHQ/oss-cad-suite-build).

Rather than using your distro's package manager, I suggest installing Rust using the
directions [here](https://rustup.rs/) and then run
`rustup target add riscv32i-unknown-none-elf` to add the RISC-V specific
`libstd`/`libcore`. I think the package manager Rust and the `rustup`-installed
Rust [can coexist](https://rust-lang.github.io/rustup/concepts/toolchains.html).

Next, head over to the {ref}`overview` page for how to hack on Sentinel :).

[`amaranth`]: https://github.com/amaranth-lang/amaranth
[`amaranth-boards`]: https://github.com/amaranth-lang/amaranth-boards
[`amaranth-soc`]: https://github.com/amaranth-lang/amaranth-soc
[`amaranth-stdio`]: https://github.com/amaranth-lang/amaranth-stdio
