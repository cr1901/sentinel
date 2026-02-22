# Quick Start

## Pre-Generated Verilog

### From Releases

Each [Github Release](https://github.com/cr1901/sentinel/releases) contains a
standalone generated Verilog file of Sentinel CPU. If you opt to download the
Verilog from releases, **you do not need Python installed to use Sentinel**.
You can automate downloading the Verilog with a script like this:

```
SENTINEL_VER=v0.1.0-beta

wget -O sentinel-v-$SENTINEL_VER.zip https://github.com/cr1901/sentinel/releases/download/$SENTINEL_VER/sentinel-v-$SENTINEL_VER.zip
unzip sentinel-v-$SENTINEL_VER.zip
```

### From Arbitrary Commits

Generating Verilog of development versions- or any commit without a release-
requires a bit of extra setup. However, it still has the advantage of not
needing to (directly) interact with a source checkout if all you want is 
some Verilog to vendor/use as part of a non-Amaranth project. To generate 
the Verilog, you can use a script similar to this, substituting `next` with any
desired branch, tag, or commit:

```python
"""Create a script for generating Sentinel Verilog."""

# /// script
# requires-python = ">=3.11"
# dependencies = [
#    "sentinel @ git+https://github.com/cr1901/sentinel@next",
#    "amaranth[builtin-yosys]>=0.5.4",
# ]
# ///

import sentinel.gen

if __name__ == "__main__":
    sentinel.gen._main()
```

Note from the `script` metadata comment block that **the above Python script
must be run using a tool that understand [PEP 723](https://peps.python.org/pep-0723/)
metadata**. Such tools include `pipx`, `pdm`, or `hatch`, or `uv`. Assuming you
saved the above script as a file called `download-sentinel.py`, you can
generate Verilog with:

```{todo}
Put other tool invocations here.
```

```
pdm run download-sentinel.py -o sentinel.v
```

````{tip}
The `download-sentinel.py` script takes arguments to customize generation! You
can get help by using:

```{todo}
Put other tool invocations here.
```

```{code-block} sh
pdm run download-sentinel.py --help
```
````


<!-- ```{tip}
The above script could possibly be represented as a Heredoc parameterized on
`next` to dynamically choose which version of the Sentinel source code is
checked out!
``` -->


```{note}
Unfortunately, it is [normal](https://github.com/cr1901/sentinel/issues/65)
for Verilog generation to take a long time when the PEP 723 tool has to download
the Sentinel git repo- it takes upwards of 30 seconds from starting the script
to getting Verilog output.

I will continue to look into why it's so slow; I believe submodules are to
blame. In the meantime, keep the performance in mind, and avoid frequent
regeneration, maybe a maximum of once per day.

Thankfully, needing _only_ the Verilog of a development version of Sentinel
should be rare. Using the above PEP 723 script with PyPI wheels should be
unaffected, although you can directly download Verilog from the equivalent release. 
```

## Using The Source

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
several {doc}`platforms <amaranth:platform>`:

* [Lattice iCEstick](https://www.latticesemi.com/icestick), _if the demo fits!_
  If when running the demo with iCEstick, you see an error like:

  ```
  ERROR: Failed to expand region (0, 0) |_> (13, 17) of 1303 ICESTORM_LCs
  ```

  that means the demo has decided it doesn't want to fit :). See [this issue](https://github.com/cr1901/sentinel/issues/2).
* [iCE40-HX8K Breakout Board](https://www.latticesemi.com/Products/DevelopmentBoardsAndKits/iCE40HX8KBreakoutBoard.aspx)
* [Arty A7 35T](https://digilent.com/shop/arty-a7-100t-artix-7-fpga-development-board/)
* [Cmod S7](https://digilent.com/shop/cmod-s7-breadboardable-spartan-7-fpga-module/)
* [iCEBreaker v1.0](https://1bitsquared.com/collections/fpga/products/icebreaker)

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
