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


## [0.1.0-beta] - 2024-01-12

[Amaranth 0.5.4](https://github.com/amaranth-lang/amaranth/tree/v0.5.x) is now
the minimum required version to use Sentinel, either directly from this repo
or as a dependency.

Sentinel still tracks upstream [`amaranth-soc`]. For the time being, use Sentinel
with caution outside of environments without lockfiles, and prefer installing
Sentinel [within a PDM environment](https://sentinel-cpu.readthedocs.io/en/latest/usage/installation.html#in-a-pdm-project): 

```sh
pdm add sentinel@git+https://github.com/cr1901/sentinel@main
```

I also cannot do a PyPI release for the same reason.

Between March and September 2024, I stopped being able to consistently fit
`AttoSoC` onto IceStick; the demo overflows between 1280-1300 ICESTORM_LCs
(maximum 1280 on device). According to bisect, the changes introduced by
Amaranth commit [1d2b9c3](https://github.com/amaranth-lang/amaranth/commit/1d2b9c309e5a0e06487105679eec361472978c5f)
pessimized `AttoSoC` _just_ enough to not fit. However, right now (2024-09-26)
releases are not blocked on the demo fitting on IceStick. _Assume the IceStick
demo is unreliable in this release._ I will look into this later.


### Added
- Add ruff linter to dev dependencies and CI.
  - Releases require linting to pass, _including this release!_
- Set up lint rules for Rust/`rustdoc` and Ruff.
  - This release and future ones will require passing a lint check for code
    and docstrings in CI. Non-release runs won't run the lint step.
  - `lint` PDM composite script can optionally take arguments, like `-e` to
    do Rust lint step on error in Python lint step.
  - Basic fixes can be applied using the `lint-fix` PDM script.
  - `sentinel-rt` is preemptively set up for `cargo fix` to work.
  - `doc` PDM script can optionally take arguments, like `-n` to run
    `sphinx-build` in [nitpicky mode](https://www.sphinx-doc.org/en/master/man/sphinx-build.html#cmdoption-sphinx-build-n).
    This catches more broken yet benign cross-refs than the `doc-auto` script
    will. In the case of Amaranth IP in particular, several broken cross-refs
    are expected due to how `Components` are documented.
- Test only installing production dependencies, importing, and Verilog
  generation in CI.
- Documentation has been written! It is hosted on [ReadTheDocs](https://sentinel-cpu.readthedocs.io/en/latest/).
  - A few doctests have been added for good measure.
  - ReadTheDocs handles building docs. However, this release and future ones
    require docs to build and doctests to pass in CI. Non-release runs won't
    run the docs step.
  - Microcode assembly file is not handled for correctness by [`sphinx`](https://www.sphinx-doc.org).
    Out of date/misleading comments were fixed.
    
    _If microcode and `sphinx` documentation don't match, `sphinx` docs take
    priority unless otherwise noted._
- [YoWASP](https://yowasp.org/) support for `import`ing `Top`, Verilog
  generation and in-tree demos.
  - Minimal prodouction dependencies/Quickstart is tested in CI using YoWASP.
- Allow firmware override/random BRAM content generation for `AttoSoC` demo
  designs which are generated on a remote machine.
- Add `AttoSoC` demo support for [Arty A7 35T](https://digilent.com/shop/arty-a7-100t-artix-7-fpga-development-board/),
  [Cmod S7](https://digilent.com/shop/cmod-s7-breadboardable-spartan-7-fpga-module/), and
  [iCEBreaker v1.0](https://1bitsquared.com/collections/fpga/products/icebreaker)
  boards.


### Changed
- All simulations have been ported to adhere to RFC [#36](https://amaranth-lang.org/rfcs/0036-async-testbench-functions.html)
  and [#62](https://amaranth-lang.org/rfcs/0062-memory-data.html).
  - This resulted in more code-sharing between the handwritten and
    upstream [pytest] simulations, as well as the RISCOF framework tests,
    such as a simulated memory
    [process](https://amaranth-lang.org/docs/amaranth/v0.5.4/simulator.html#amaranth.sim.Simulator.add_process).

    Additionally, except for the appropriately-named `test_soc` file,
    the `AttoSoC` example is no longer used in tests!
- Use [`pytest-amaranth-sim`] plugin for Amaranth-specific fixtures.
- `AttoSoC` example was ported to adhere to [#70](https://amaranth-lang.org/rfcs/0070-soc-memory-map-names.html).
- Current OSS CAD Suite version for CI is [2024-11-01](https://github.com/YosysHQ/oss-cad-suite-build/releases/tag/2024-11-01).
- Example Rust firmware greatly improved- a [Rule 110](https://en.wikipedia.org/wiki/Rule_110)
  visualization over serial port [suggested by @mcclure](https://mastodon.social/@mcc/113244143342550101)!
- Various refactors that do not change code functionality:
  - Rearrange top-level connections based on purpose.
  - Data alignment logic was split into Components.
  - An attempt was made to hoist out muxed inputs to the Datapath. However,
    this did not optimize well. The Component- `DataPathSrcMux`- is kept around
    as dead code in case it optimizes better in future versions.
  - Move ALU source muxes into their own Components.
  - `Insn` class to serve as the moral equivalent of an Amaranth
    [`View`](https://amaranth-lang.org/docs/amaranth/v0.5.4/stdlib/data.html#amaranth.lib.data.View)
    for RISC-V instructions.
  - Decoder was split into several Components. In fact, the decoder was
    _effectively rewritten_; the large Switch statement of the previous
    versions was unreadable. The split components include:
    - CSR Access Control
    - Exception Control
    - Mapping ROM
    - Immediate Generation

    AFAIR, none of the above refactors changed LUT usage meaningfully.
  - Additionally, the Control Unit's `Signature` was overhauled.
- Manually specify the set of files to include in source dist. Specifically,
  exclude submodules and extra test files, and include config files, examples,
  and `sentinel-rt`.
- Tweak Rust firmware DoIt tasks to allow choosing bus type, call `cargo`
  directly instead of invoking `pdm` again.
- _All_ `UCodeROM` fields are now verified against microcode file before
  generating a [`Signature`](https://amaranth-lang.org/docs/amaranth/v0.5.4/stdlib/wiring.html#amaranth.lib.wiring.Signature),
  not just `enum`s.
  - Rename `UCodeROM` `enum_map` constructor parameter to `field_map`.
- Lots of small Ruff and Rust/`rustdoc` lints applied, so that CI passes :).
  - Some files are ignored for lint. See `pyproject.toml` for justifications.
- Development/style guidelines have been refined, and changes made to the
  reflect them:
  - `Component` `Signature`s are now generated using annotations at the class
    level when possible; previously, they were instance attributes. This should
    have no functional change.
  - Nested classes within `Insn` class are public.
  - Most functions of `sentinel.gen` are private.
  - Nest `Signature` object bindings into the objects that "own" them. This
    paves the way to add a few more `Signature` object bindings next release.
- `Control` unit `Signature` has been greatly improved; it uses nested
  `Signature` `Members` to logically organize microcode signals by purpose.

### Fixed
- Use full git hash `a7fa902a5f70c7d53a654d850f745e36821fbb78` for [logLUTs](https://github.com/mattvenn/logLUTs)
  benchmarking dependency (got weird errors trying to get PDM to download it
  using the short hash as of Sept. 2024).
- Fixed UnusedElaboratable warning in `test_ucode_layout_gen` test
  (thanks @kivikkak!)
- Sentinel uses `amaranth_soc.wishbone`, but this wasn't reflected in
  [production dependencies](https://pdm-project.org/latest/usage/dependency/#select-a-subset-of-dependency-groups-to-install).
- Fix `license` field in `pyproject.toml. It was
  [always meant](https://libera.irclog.whitequark.org/amaranth-lang/2023-11-25#35299928)
  to be BSD-2-Clause, but I just accepted the defaults when originally
  initializing the project with PDM :).
- Remove `regfile` module. This was accidentally committed before initial
  release and never used.
- Do not use back-to-back write/read optimization for store instructions
  until it's [clear](https://github.com/fossi-foundation/wishbone/issues/26) to
  me that it's within spec.
- Various fixes where registers/signals did not get appropriate values on
  _non-power-on_ resets:
  - PC would either be initialized to `0` or `4`, depending on instruction.
  - MCAUSE register was not cleared to `0`, as [privileged spec](https://riscv.org/specifications/ratified/)
    requires for implementations that do not distinguish reset conditions.
  - Wishbone `CYC` and `STB` would remain asserted after reset if the reset
    happened in the middle of a bus cycle; WB spec
    [requires](https://wishbone-interconnect.readthedocs.io/en/latest/03_classic.html#reset-operation)
    `CYC` and `STB` to deassert upon `SYSCON` reset.
  - Init code after reset now requires one extra cycle (5 cycles total) before
    fetching the first instruction from the user program.
  - Tests for these cases have been added to CI.
- `doit` tasks would sometimes use the wrong Python interpreter; use `sys.exectuable`
  to indicate "this interpreter" as [recommended](https://docs.python.org/3/library/subprocess.html#subprocess.Popen)
  instead.

### Removed
- Remove special Rust PDM scripts by using .config/cargo.toml.
- Remove the `Simulator` fixture and `--vcds` option to pytest as provided by
  this package. Instead, use equivalent fixtures/options provided by
  [`pytest-amaranth-sim`].
- Flake8 linting has been completely replaced with Ruff. We enable
  [preview mode](https://docs.astral.sh/ruff/preview/) to take advantage of
  [unstable](https://docs.astral.sh/ruff/rules/#error-e) [rules](https://docs.astral.sh/ruff/rules/#pydoclint-doc)
  that were provided by flake8.


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


## [0.1.0-alpha] - 2023-11-29

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
[`pytest-amaranth-sim`]: https://github.com/cr1901/pytest-amaranth-sim

[Unreleased]: https://github.com/cr1901/sentinel/compare/v0.1.0-beta..next
[0.1.0-beta]: https://github.com/cr1901/sentinel/compare/v0.1.0-alpha.1..v0.1.0-beta
[0.1.0-alpha.1]: https://github.com/cr1901/sentinel/compare/v0.1.0-alpha..v0.1.0-alpha.1
[0.1.0-alpha]: https://github.com/cr1901/sentinel/releases/tag/v0.1.0-alpha

<!-- Skeleton generated by git-cliff. Maintained by hand. -->
