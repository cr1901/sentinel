# Quick Start

```{todo} The README.md contents need to be mostly migrated here.

Right now, this section is bare-minimum just so its not empty.
```

_The below two commands assume you have a checkout of Sentinel's source code
and are running commands at the source code root._

To generate Verilog for a Sentinel CPU with a [Wishbone classic](https://cdn.opencores.org/downloads/wbspec_b4.pdf)
bus and an IRQ line:

```
pdm gen > sentinel.v
```

To generate a SoC that runs a prime counting demo for
[Lattice iCEstick](https://www.latticesemi.com/icestick):

```
pdm demo
```

Verilog and Demo generation have several tweakable parameters. For help, run:

```
pdm gen -h
pdm demo -h
```

For use _outside of the source tree_:

* `[pdm run] python -m sentinel.gen` will generate Verilog.
* See `AttoSoC` class in `examples/attosoc.py` inside the Sentinel source code
  for how to use Sentinel as a Python package in external code.

