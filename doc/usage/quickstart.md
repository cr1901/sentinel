# Quick Start

From a checkout of Sentinel's source, you have a few options to try out
Sentinel risk free! _The below commands assume you and are running commands at
the source code root, and that you've [installed](installation.md#prerequisites)
`pdm`, `yosys`, and possibly `nextpnr-ice40`_:

```
pipx install pdm
git clone https://github.com/cr1901/sentinel.git
cd sentinel
pdm install -G examples
```

If you don't have an external `yosys` or `nextpnr-ice40`, and don't wish to
install them, you can use the [YoWASP flow](installation.md#yosys-and-foss-toolchains)
for this section instead:

```
pipx install pdm
git clone https://github.com/cr1901/sentinel.git
cd sentinel
pdm install -G examples -G yowasp
pdm run use-yowasp
```

```{note}
An alternate take on the Quick Start using YoWASP (which will probably
be seen by more people) is detailed in the "Quick Quick Start" section of the
`README.md` at the [repo root](https://github.com/cr1901/sentinel). The
`README.md` demonstrates creating and destroying a [separate virtual environment](https://pdm-project.org/en/latest/usage/venv/)
for using the YoWASP flow. Both sets of commands should have the same results;
I omit `venv` handling here to keep the docs simpler.
```

## Generate A Verilog Core

To generate Verilog for a Sentinel CPU with a [Wishbone classic](https://cdn.opencores.org/downloads/wbspec_b4.pdf)
bus and an IRQ line, run:

```
pdm gen -o sentinel.v
```

_Verilog generation only generates a CPU, not a full SoC or design._ You must
integrate the Sentinel source file into an larger external HDL project
(Amaranth, Verilog, or otherwise).

## A Full Example SoC In Amaranth

The {mod}`examples.attosoc` module shows one way to create a simple Sentinel
SoC with a UART, timer, and GPIO. _Examples should not be taken as a canonical
way to create Amaranth SoCs._ They are subject to change as Amaranth matures
(and are also a good way for me to experiment :)).

The {class}`~examples.attosoc.AttoSoC` `class` constructs the SoC from various
peripheral `class`es contained within {mod}`~examples.attosoc`. Peripherals
come with either a Wishbone bus {ref}`interface <amaranth:wiring-intro2>` or
a CSR bus interface from [`amaranth-soc`](https://github.com/amaranth-lang/amaranth-soc)
(bridged to Wishbone). The {func}`~examples.attosoc.main` function provides
an {mod}`python:argparse` command-line entry point, and
{func}`~examples.attosoc.demo` actually {ref}`builds <amaranth:intro-build>`
the SoC.

Right now, {mod}`~examples.attosoc` uses Amaranth to build a SoC bitstream for
two {doc}`platforms <amaranth:platform>`:

* [Lattice iCEstick](https://www.latticesemi.com/icestick)
* [iCE40-HX8K Breakout Board](https://www.latticesemi.com/Products/DevelopmentBoardsAndKits/iCE40HX8KBreakoutBoard.aspx)

The `pdm` [scripts](https://pdm-project.org/latest/usage/scripts/)
`demo` and `demo-rust` are thin wrappers over {func}`~examples.attosoc.main`
Extra arguments can be sent by using `pdm demo [more] [args] [here...]`; be
careful of overriding args hardcoded to be sent by the `pdm` script!

### Rust Demo

If you have a Rust compiler {ref}`installed <dep-hints>`, you can create a
demo that prints a [Rule 110](https://en.wikipedia.org/wiki/Rule_110) pattern
to a serial console:

```
pdm demo-rust [args ...]
```

This script compiles a Rule 110 example in the [`sentinel-rt`](../development/support-code.md)
crate and sends the resulting [ELF](https://en.wikipedia.org/wiki/Executable_and_Linkable_Format)
file off to the `demo` function. The output bitstream will be available under
the `build-rust` directory.

### Assembly Demo

If you don't wish to or can't install a Rust compiler, I provide a fallback
firmware written in assembly that requires no external dependencies.

```
pdm demo [args ...]
```

This firmware calculate primes up to 255, and lights up LEDs for each prime
found. The output will be available under the `build` directory.

```{todo}
`demo` parameters are only really documented in passing/prose right now, and
not even all of them at that:

* Punt the remaining params to development sections?
* Prose might be enough?
```

For help on _all_ tweakable parameters, use the `-h` command-line option:

```
pdm gen -h
pdm demo[-rust] -h
```

For use _outside of the source tree_, see the [Reference](./reference.md)
page.
