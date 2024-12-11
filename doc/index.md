<!-- Sentinel documentation master file, created by
   sphinx-quickstart on Wed Feb  7 00:04:29 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive. -->

# Welcome to Sentinel's documentation!

Sentinel is a [microcoded](https://en.wikipedia.org/wiki/Microcode) RISC-V CPU
(`RV32I_Zicsr`) written in [Amaranth](https://amaranth-lang.org/), implementing
the Machine Mode privileged spec. On FPGAs, it is designed to fit into:

* ~1000 4-input LUTs.
* ~400 FFs or less.
* &ge; 3 256 x 16 bit block RAMs for at least the microcode store (256 x &ge;
  48 bit).

As is normal for microcoded designs, instructions take [multiple](development/internals.md#instruction-cycle-counts)
clock cycles. The core's size and speed makes it well suited for control tasks
and system initialization, where a programmable state machine or custom
size-tailored core would otherwise be used. In essence, the core "stands watch"
over a more complex design, which is how I came up with the name (in addition
to liking the word "Sentinel" from
[other](https://shining.fandom.com/wiki/Sentinel_(Shining_in_the_Darkness))
[sources](http://www.down-the-shore.com/sentinl.html) from my childhood).

Sentinel will eventually be available on [PyPI](https://pypi.org/) under the
package name `sentinel-cpu`. In the interim, use the
[development repo](https://github.com/cr1901/sentinel) instead.

The nice logo was contributed by the lovely [Tokino Kei](https://tokinokei.carrd.co/) :D.

```{toctree}
:maxdepth: 2
:caption: "Contents:"

usage/installation
usage/quickstart
usage/reference
development/overview
CHANGELOG <changes>
TODO List <todo>
```


# Indices and tables

* [](genindex)
* [](modindex)
* [](search)
