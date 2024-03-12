# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

_Note that the Python ecosystem itself [doesn't really](https://iscinumpy.dev/post/bound-version-constraints/)
adhere to Semantic Versioning._ Dependency updates are automatically managed
with [Renovate Bot](https://www.mend.io/renovate/) on Sentinel's two branches
to detect dependency breakage that warrants a new release/yank.

The Sentinel repository has two active branches: `main` and `next`. Releases
and patches live on `main`, and development takes place on `next`. `next` is
developed against the upstream/git versions of [Amaranth] and associated
packages. These include, but are not limited to:

* [`amaranth`]
* [`amaranth-boards`]
* [`amaranth-soc`]
* [`amaranth-stdio`]

If necessary, patches from `main` can be forward-ported to `next`, and commits
from `next` and be backported to `main` for a point-release. _When possible_,
releases are made against Amaranth packages on [PyPI](https://pypi.org/), even
though development is done against the Amaranth git repos.


## [Unreleased]


## [0.1.0-alpha.1] - 2024-03-12

First release after the `next`/`main` split.

### Added
- Test gateware generation in CI.
- Updates available for dependencies are tracked with [Renovate Bot](https://www.mend.io/renovate/).
  - Applies to both `main` and `next`.
- The `yosys` version for Verilog/RTLIL/gateware generation is also tracked in
  CI using a [new workflow](https://github.com/cr1901/sentinel/actions/workflows/update-yosys.yml).
  - Current OSS CAD Suite version is [2024-03-01](https://github.com/YosysHQ/oss-cad-suite-build/releases/tag/2024-03-01).
- Demo SoC example can optionally use peripherals whose registers are
  implemented using the [`amaranth-soc`] CSR bus.
  - Only fits on HX8K Evaluation board at present.
  - Peripherals are at different addresses when using the CSR bus; the Rust
    firmware can detect which version of the gateware is loaded by querying
    the `MIP` register after reset.
- Demo prints addresses of peripherals in table format.
- Rust Demo SoC can be simulated as part of [Pytest] tests.
  - Disabled by default, pass `--runsoc` to `pytest` to enabled.
- Implement remote Demo SoC builds using [`paramiko`](https://www.paramiko.org/index.html).
- Add usage as a Python dependency in README.md.


### Changed
- Replace ELF generator with [`pyelftools`](https://github.com/eliben/pyelftools).
  - This simplifies the inline objcopy implementation.
- GPIO peripheral in SoC demo has input, output, and output-enable ports now.
- Use a dynamic Python version (_no releases ever saw the manual behavior_).
- [`dodo.py`](https://pydoit.org/) dependency graph has been cleaned up a bit.
- Start improving [Signatures](https://amaranth-lang.org/docs/amaranth/latest/stdlib/wiring.html#signatures)
  used throughout Sentinel core.
  - Mostly limited to Decoder, ExceptionRouter, and ALU for now.
  - Many signals remain to be wired up to formal harness via Signatures, rather
    that the formal harness reaching into Sentinel.
- Python, Rust, and CI dependencies have been updated to most recent versions.
- Rust firmware development [DoIt] tasks are no longer targeted to IceStick
  only.
  - HX8K development board support is up to parity with IceStick.


### Fixed
- All Amaranth [deprecations](https://amaranth-lang.org/docs/amaranth/latest/changes.html#migrating-from-version-0-4)
  for the upcoming version 0.5 have been addressed, up to commit [715a8d4](https://github.com/amaranth-lang/amaranth/tree/715a8d4).
- Correct `gen` usage outside pdm in README.md.
- `dodo.py` no longer errors when removing directory trees that don't exist.
  - Removing dirs is required as part of RISCOF test cleanup.
- Load-bearing optimization implemented in [39005c1](https://github.com/cr1901/sentinel/tree/39005c1)
  that saves ~30 LUTs in SoC demo.
  - Check to see if this can be removed/is no longer necessary.


## [v0.1.0-alpha] - 2023-11-29

Initial release. This is a retroactive release, created just before the
`next`/`main` split.

[PDM](https://pdm-project.org) should be used for interacting with this repo;
type `pdm run --list` for a list of commands. `pdm` will defer to [DoIt] for
complex tasks such as orchestrating [RISC-V Formal](https://github.com/YosysHQ/riscv-formal).

[Pytest](https://pytest.org) is used for basic testing, and [Flake8](https://flake8.pycqa.org)
is used for linting. Due to code cleanups required, as well as some tooling
still being in flux, _no documentation beyond the CHANGELOG.md and README.md
is provided yet._

**Due to git dependencies, this release is only usable within the `pdm`
environment**. Specifically, the SoC example, tests, and Verilog generation
works, but using Sentinel as a dependency of another Python/[Amaranth]/`pdm`
project _does not work_.

### Added
- Working SoC example for [Lattice IceStick](https://www.latticesemi.com/icestick)
  and [iCE40-HX8K Breakout Board](https://www.latticesemi.com/Products/DevelopmentBoardsAndKits/iCE40HX8KBreakoutBoard.aspx).
  - Includes custom Amaranth peripherals and a contrived [Rust](https://www.rust-lang.org/)
    firmware.
    
    Run using `pdm demo` (Assembly firmware) or `pdm demo-rust` (Rust firmware).
  - Demo is using [special options](https://libera.irclog.whitequark.org/yosys/2023-11-20#1700497858-1700497760)
    to [yosys](https://yosyshq.net/yosys/) to make Sentinel fit onto IceStick.
  - Microcode written using the [m5meta](https://github.com/brouhaha/m5meta/)
    microcode assembler, version 1.x.
    - An upcoming version 2.x of `m5meta` is expected in the moderate-near
      future. I plan to rewrite the microcode then, and _the rewrite will not
      be compatible with version 1.x._
- Working RISC-V soft-core implementing the [RV32I_Zcsr specification](https://github.com/riscv/riscv-isa-manual/releases/tag/Ratified-IMAFDQC).
  - Core passes the RISC-V Formal verification tests, as well as the [tests](https://github.com/riscv-non-isa/riscv-arch-test)
    used by RISC-V International as part of the [RISCOF framework](https://github.com/riscv-software-src/riscof).
- Bespoke test suite with my own custom tests and [pytest] fixtures for
  simulating Sentinel with Amaranth's Python simulator.
  - Many of the pytest test come from an [older test suite](https://github.com/riscv-software-src/riscv-tests)
    no-longer used by RISC-V International. I feel they are fine as a first
    layer of tests to detect immediate breakage of Sentinel.
- CI using [Github Actions](https://github.com/cr1901/sentinel/actions) tests
  using pytest, RISC-V Formal, RISCOF, and demo synthesis every push and PR.
  - The demo test is allowed to fail due to lack of space on Icestick due to
    different compilers optimizing `yosys` slightly differently. See
    [#2](https://github.com/cr1901/sentinel/issues/2).
- A nice logo by [Tokino Kei](https://tokinokei.carrd.co/) :).

[Amaranth]: https://amaranth-lang.org/
[`amaranth`]: https://github.com/amaranth-lang/amaranth
[`amaranth-boards`]: https://github.com/amaranth-lang/amaranth-boards
[`amaranth-soc`]: https://github.com/amaranth-lang/amaranth-soc
[`amaranth-stdio`]: https://github.com/amaranth-lang/amaranth-stdio
[DoIt]: https://pydoit.org/
[pytest]: https://pytest.org

[Unreleased]: https://github.com/cr1901/sentinel/compare/v0.1.0-alpha.1..HEAD
[0.1.0-alpha.1]: https://github.com/cr1901/sentinel/compare/v0.1.0-alpha..v0.1.0-alpha.1
[v0.1.0-alpha]: https://github.com/cr1901/sentinel/releases/tag/v0.1.0-alpha

<!-- Skeleton generated by git-cliff. Maintained by hand. -->
