<p align="center">
  <img src="doc/White Background Ver.png" 
  alt="Sentinel Logo. A lighthouse is shining its light on a PCB and computer
  chip. The silicon die of the computer chip is visible. The text &quot;Sentinel&quot;
  in a black and gray gradient stretches in parallel with the lighthouse's beam.
  The text covers the base of the lighthouse and is below the chip.">
</p>

<p align="center">
  <strong>Logo by <a href="https://tokinokei.carrd.co/">Tokino Kei</a>.</strong>
</p>

[![Documentation Status](https://readthedocs.org/projects/sentinel-cpu/badge/?version=latest)](https://sentinel-cpu.readthedocs.io/en/latest/?badge=latest)
[![main](https://github.com/cr1901/sentinel/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/cr1901/sentinel/actions/workflows/ci.yml)
[![next](https://github.com/cr1901/sentinel/actions/workflows/ci.yml/badge.svg?branch=next)](https://github.com/cr1901/sentinel/actions/workflows/ci.yml)

# `sentinel`

Sentinel is a small RISC-V CPU (`RV32I_Zicsr`) written in [Amaranth](https://amaranth-lang.org/).
It implements the Machine Mode privileged spec, and is designed to fit into
~1000 4-input LUTs or less on an FPGA. It is a good candidate for control tasks
where a programmable state machine or custom size-tailored core would otherwise
be used.

Unlike most RISC-V implementations, Sentinel is [microcoded](https://en.wikipedia.org/wiki/Microcode),
not pipelined. Instructions require multiple clock cycles to execute. Sentinel
is therefore not necessarily a good fit for applications where high throughput/
IPC is required. Short version: minimum of 4 CPI for basic arithmetic,
maximum of 69 for a 31-bit shift (_yes, shift instructions need work_).

Sentinel has been tested against RISC-V Formal and the RISCOF frameworks, and
passes both. Once I have added [a few extra tests](https://github.com/YosysHQ/riscv-formal/blob/a5443540f965cc948c5cf63321c405474f34ced3/docs/procedure.md#other-checks),
the core can be considered correct with respect to the RISC-V Formal model.
The core is also _probably_ correct with respect to the SAIL golden model.

## Why The Name `sentinel`?

I've like the way the word "sentinel" sounds ever since I first learned of the
word, either from the title of [a book on NJ lighthouses](http://www.down-the-shore.com/sentinl.html),
or on an [enemy](https://shining.fandom.com/wiki/Sentinel_(Shining_in_the_Darkness))
from an [old Sega Genesis RPG](https://en.wikipedia.org/wiki/Shining_in_the_Darkness).
The term has always stuck with me since then, albeit in a much more positive
light than "the soldier golems of the forces of Darkness" :). Since "sentinel"
means "one who stands watch", I think it's an apt name for a CPU intended to
watch over the rest of your silicon, but otherwise stay out of the way. Also,
since lighthouses are indeed "Sentinels Of The Shore", I wanted to shoehorn a
lighthouse into the logo :).

## Quick Quick Start

The absolute fastest way to get started is to check out the source code,
install `pdm`, use `pdm` to create a virtual environment with appropriate
tools, and generate an `.env.toolchain` file that `pdm` uses to set some
environment variables for Amaranth:

```
pipx install pdm
git clone https://github.com/cr1901/sentinel.git
cd sentinel
pdm venv create -n quick-quickstart
pdm install --venv quick-quickstart -G examples -G yowasp
pdm run use-yowasp
```

Use `pip` or `pipx` to install `pdm` depending on your Python install's
[recommendation](https://packaging.python.org/en/latest/specifications/externally-managed-environments/#guide-users-towards-virtual-environments).

Then, to generate Verilog core with a Wishbone Classic bus, and `clk`,
`rst`, and `irq` input pins, run:

```
pdm run --venv quick-quickstart gen
```

To create a demo bitstream that counts primes and sets LEDs accordingly (for the
[iCE40-HX8K Breakout Board](https://www.latticesemi.com/Products/DevelopmentBoardsAndKits/iCE40HX8KBreakoutBoard.aspx)),
run:

```
pdm run --venv quick-quickstart demo -i csr -p ice40_hx8k_b_evn
```

The output will be available in `build/` at the source code root.

If you have [Rust](https://www.rust-lang.org/) [installed](https://rustup.rs/)
with the `riscv32i-unknown-none-elf` [target](https://rust-lang.github.io/rustup/cross-compilation.html),
you can create a [Rule 110](https://en.wikipedia.org/wiki/Rule_110) demo that
prints neat patterns to the serial port:

```
pdm run --venv quick-quickstart demo-rust -i csr -p ice40_hx8k_b_evn
```

The output will be available in `build-rust/` at the source code root.

Run `pdm run --venv quick-quickstart gen -h` and
`pdm run --venv quick-quickstart demo -h` for help, and experiment!

When you're done, unset the environment variables and optionally destroy the
virtual environment, as we will not be using it again:

```
pdm run use-local
pdm venv remove quick-quickstart
```

Note that **extra dependencies are required for development**. See the next
section.

## Quick Doc Links

* To get started with an environment suitable for development, consult the
  [Installation](https://sentinel-cpu.readthedocs.io/en/latest/usage/installation.html) doc page.
* For information on the source code development environment, click
  [here](https://sentinel-cpu.readthedocs.io/en/latest/development/overview.html).
  * Source code guidelines are found on the
    [Development Guidelines](https://sentinel-cpu.readthedocs.io/en/latest/development/guidelines.html)
    page.
* For other use cases, consult the [Quickstart](https://sentinel-cpu.readthedocs.io/en/latest/usage/quickstart.html)
  page. Note that they are a little less quick than the [Quick Quick Start](#quick-quick-start) :).
* Sentinel has multiple test suites. External submodules [have](./tests/formal/README.md)
  [their](./tests/upstream/README.md) [own](./tests/riscof/README.md)
  `README.md`s for context and quick instructions. The [Testing](https://sentinel-cpu.readthedocs.io/en/latest/development/testing.html)
  page and subpages give further instructions and information.
* The Public API has its [own page](https://sentinel-cpu.readthedocs.io/en/latest/usage/reference.html).
  * Internal Amaranth [Components](https://amaranth-lang.org/docs/amaranth/latest/stdlib/wiring.html#amaranth.lib.wiring.Component)
    are documented on the [Internals](https://sentinel-cpu.readthedocs.io/en/latest/development/internals.html)
    page.
* A copy of the below block diagram, detailed instruction cycle counts, and
  implemented CSRs are also on the [Internals](https://sentinel-cpu.readthedocs.io/en/latest/development/internals.html)
  page.
* Microcode information has its [own page](https://sentinel-cpu.readthedocs.io/en/latest/development/microcode.html).

## Block Diagram

![Simplified block diagram of Sentinel. Black arrows are physical connections.
Blue arrows represent microcode ROM outputs to Sentinel components, including
feedback into the microcode ROM as inputs. Purple arrows represent microcode
ROM inputs from the other components.](doc/blockdiag.png)
