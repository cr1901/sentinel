# User Reference

The [Quickstart](./quickstart.md) is a good reference for how to use Sentinel
from the source repo. These next two sections discuss usage outside of the
source tree.

## Generating Verilog From An Installed Package/As A Dependency

If using Sentinel as an installed package in another project, the
[Quickstart](./quickstart.md#generate-a-verilog-core) still applies,
except the command is now:

```
[pdm run] python -m sentinel.gen
```

If you're using `pdm` to handle Python dependencies in e.g. a mixed Python/Verilog
project, and Sentinel is a one of those Python dependencies, you may wish
to use [scripts](https://pdm-project.org/latest/usage/scripts/#pdm-scripts) to
provide a shortcut for Verilog generation in your `pyproject.toml`
(_`call = "python -m sentinel.gen"` does not work!_):

```toml
[tool.pdm.scripts]
gen = { call = "sentinel.gen:generate", help="generate Sentinel Verilog file" }
```

## Use In Amaranth Code

Right now, even from Python, Sentinel consists of rather few tunable knobs.
The only public Sentinel CPU module is the appropriately-named
{py:class}`~sentinel.top.Top`.

`Top` is an [interface object](https://amaranth-lang.org/rfcs/0002-interfaces.html#interface-definition-library-rfc)
whose {py:class}`~amaranth.lib.wiring.Signature` consists of a [Wishbone](https://cdn.opencores.org/downloads/wbspec_b4.pdf)
Classic bus and an Interrupt ReQuest (IRQ) line. All interface members are
synchronous to the `sync` [clock domain](https://amaranth-lang.org/docs/amaranth/latest/guide.html#control-domains).
Explicit `clk` and `rst` lines are generated for the `sync` domain in generated
Verilog code.

I expect most users to only need to `import` from `sentinel.top` to create
their SoC:

```{testcode}
from amaranth import Elaboratable
from sentinel.top import Top

class MySoC(Elaboratable):
    def __init__(self):
        self.cpu = Top()
        ...

    def elaborate(self, plat):
        m = Module()
        m.submodules.cpu = self.cpu
        ...
```

Since the Sentinel top-level is only a CPU, not a full computer system,
_the user must provide some sort of memory, and I/O to effectively run
programs_. One common way to do this is to connect Sentinel's Wishbone bus to
a Wishbone address decoder, behind which memory and I/O live.

See the {class}`~examples.attosoc.AttoSoC` `class`, and the corresponding
[section](./quickstart.md#a-full-example-soc-in-amaranth) in the Quickstart,
for a full working example.

## Public API

```{eval-rst}
.. automodule:: sentinel.top
    :members:
```
