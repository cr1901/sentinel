# Installation

## Prerequisites

Sentinel requires Python 3.11 or newer. I also highly recommend [`pdm`](https://pdm-project.org)
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

Right now, Sentinel requires an external [`yosys`](https://github.com/YosysHQ/yosys),
as dependencies are not set up to use Amaranth's [`builtin-yosys` feature](https://amaranth-lang.org/docs/amaranth/v0.5.3/install.html#installing-amaranth) or [`yowasp`](https://github.com/YoWASP). If you don't
feel like [building](https://github.com/YosysHQ/yosys/#building-from-source)
`yosys`, binaries are available from [OSS CAD Suite](https://github.com/YosysHQ/oss-cad-suite-build).
_Ensure `LD_PRELOAD` is not set if using OSS CAD Suite._

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

## As A Dependency In A PDM Project

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

Additionally, some Amaranth packages/dependencies are still in flux and are not
don't have a stable release to track on PyPI. Until they do, the `main` branch
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
pdm install --dev
```

Additionally, make sure the following are installed:

* [`boolector`](https://github.com/Boolector/boolector) SMT solver.

  Note that Boolector is no longer maintained. Eventually I will update to
  [Bitwuzla](https://github.com/bitwuzla/bitwuzla).
* [`SymbiYosys`](https://github.com/YosysHQ/sby) verification driver
* `riscv64-unknown-elf-gcc` C/C++ compiler and assembler. 

  The binary name is hardcoded by scripts. In
  principle, the actual toolchain binary doesn't matter, but the scripts
  haven't been updated yet.
* `rustc`/`rustup` with the `riscv32i-unknown-none-elf` target.

  Rust is currently only required for certain example designs.

If you are having trouble finding binaries via package manager, `boolector` and
`SymbiYosys` are provided by [OSS CAD Suite](https://github.com/YosysHQ/oss-cad-suite-build),
and SiFive still provides downloads to usable GCC versions in an [archived repo](https://github.com/YosysHQ/oss-cad-suite-build).

Rather than using the package manager, I suggest installing Rust using the
directions [here](https://rustup.rs/) and then run
`rustup target add riscv32i-unknown-none-elf` to add the RISC-V specific
`libstd`/`libcore`. I think the package manager Rust and the `rustup`-installed
Rust [can coexist](https://rust-lang.github.io/rustup/concepts/toolchains.html).

Next, head over to the {ref}`overview` page for how to hack on Sentinel :).

[`amaranth`]: https://github.com/amaranth-lang/amaranth
[`amaranth-boards`]: https://github.com/amaranth-lang/amaranth-boards
[`amaranth-soc`]: https://github.com/amaranth-lang/amaranth-soc
[`amaranth-stdio`]: https://github.com/amaranth-lang/amaranth-stdio
