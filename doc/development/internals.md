# Sentinel Internals

<!-- Click each block in the below image to go to documentation for (_roughly_) each
{py:class}`~amaranth.lib.wiring.Component` of Sentinel. -->

Below is a simplified block diagram of Sentinel, showing how the main {py:class}`~amaranth.lib.wiring.Component`s
connect to each other. Behavior of `Components` not represented in the block
diagram will be explained in the next sections.

<img src="../_static/blockdiag.png"
    alt="Block diagram of Sentinel CPU, showing the various components described
    on the remainder of this page."> 

Blue arrows represent outputs from the microcode ROM's data [Signal](https://amaranth-lang.org/docs/amaranth/latest/guide.html#signals)s,
while purple arrows represents inputs from each `Component` back to the
microcode ROM address `Signal`s. A blue arrow _into_ the microcode ROM reflects
the fact that some microcode data outputs feed back into the ROM's
address as inputs.

<!-- TODO: Block Diagram Map. Use the below as a starting point.

<map name="blockdiag">
    <area shape="rect" coords="517,116,648,242" href="#microcode-rom">
    <area shape="rect" coords="242,116,446,200" href="#register-file">
    <area shape="rect" coords="290,248,380,290" href="#sentinel.datapath.ProgramCounter">
    <area shape="rect" coords="356,16,518,84" href="#instruction-decoder">
    <area shape="rect" coords="60,362,210,438" href="#arithmetic-logic-unit-alu">
    <area shape="rect" coords="30,170,260,372" href="#alu-sources">
    <area shape="rect" coords="372,364,575,472" href="#fetch-load-store-unit">
</map>

<img usemap="#blockdiag" src="../_static/blockdiag.png"
    alt="Block diagram of Sentinel CPU, showing the various components described
    on the remainder of this page."> -->


## Register File

```{eval-rst}
.. automodule:: sentinel.datapath
    :members:
```

## Microcode ROM

```{eval-rst}
.. automodule:: sentinel.ucoderom
    :members:
    :exclude-members: enum_map
```

```{eval-rst}
.. automodule:: sentinel.control
    :members:
```

## Instruction Decoder

```{eval-rst}
.. automodule:: sentinel.decode
    :members:
```

## Arithmetic Logic Unit (ALU)

```{eval-rst}
.. automodule:: sentinel.alu
    :exclude-members: ASrcMux, BSrcMux
```

## Exception Control

Exception control has not yet been incorporated into the above block diagram.

```{eval-rst}
.. automodule:: sentinel.exception
    :members:
```

## ALU Sources

The {py:class}`~sentinel.alu.ALU`'s two inputs `A` and `B` are fed by two
separate muxes. Each mux can choose from one of up to 8 data sources. Not all
data sources are shared between the two muxes.

```{eval-rst}
.. autoclass:: sentinel.alu.ASrcMux
    :members:
```

```{eval-rst}
.. autoclass:: sentinel.alu.BSrcMux
    :members:
```

These muxes and latches live in the implementation of {py:class}`~sentinel.top.Top`.

## Fetch/Load/Store Unit

The Fetch/Load/Store Unit is implemented in-line in {py:class}`~sentinel.top.Top`
using the components from the {py:mod}`~sentinel.align` module.

```{eval-rst}
.. automodule:: sentinel.align
    :members: 
```

Aside from aligning, the glue logic for latching addresses, read data, and
write data is minimal and controlled directly by microcode signals.
