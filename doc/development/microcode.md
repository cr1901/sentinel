# Microcode

This section describes the rationale for using a microcode, as well as
its weaknesses, some terminology, and finally, the various microcode fields of
Sentinel.

If you want a short version for the rationale, and just skip over to the
{ref}`terminology <Terminology>`:

Sentinel is a [horizontally-microcoded](https://en.wikipedia.org/wiki/Microcode#Horizontal_microcode)
CPU design because I wanted to create a conforming `RV32I_Zicsr` CPU with M-Mode
that fits into ~1000 `ICESTORM_LCs` on an iCE40 FPGA. It wasn't- _and still isn't_- clear
to me that I could hit these goals without using some of the FPGA Block RAM
for a microcode instead of LUTs for a hardwired control unit.

## Some References

CPUs implementing a [Reduced Instruction Set](https://en.wikipedia.org/wiki/Reduced_instruction_set_computer),
like RISC-V, are best optimized for speed by using
[dedicated circuitry](https://en.wikipedia.org/wiki/Control_unit#Hardwired_control_unit) to
control the internal components. Today, microcode is generally relegated to special
cases. However, both hardwired and microcoded control fulfill the same general purpose;
"drive 0s and 1s to a CPUs various components to move and manipulate data".

I designed a hardwired CPU for a class many years ago; it took me a while
to wrap my head around how microcode works and find the right people to point
me in the right direction. I found the following resources useful:

* Over the years, the [Wikipedia article](https://en.wikipedia.org/wiki/Microcode#Horizontal_microcode)
  has gotten a lot better.
* The ZPU Stack Machine CPU has a [microcode implementation](https://github.com/zylin/zpu/tree/master/zpu/hdl/avalanche)
  to study.
* In my opinion, the gold standard for microcode design is
  [Bit-slice microprocessor design](http://bitsavers.informatik.uni-stuttgart.de/components/amd/bitslice/Mick_Bit-Slice_Microprocessor_Design_1980.pdf)
  by John Mick and Jim Brick.

  The book was written for with the [Am2900 series](https://en.wikipedia.org/wiki/AMD_Am2900)
  in mind, which are long out-of-production parts. However, the Am2900 series
  were building blocks _designed_ for microcode. As the book teaches you to
  to make a custom CPU [datapath](https://en.wikipedia.org/wiki/Datapath) out
  of Am2900 parts, you by extension learn how to design a microcode.

## Hardwired and Microcoded Rationale

Back in the 80s, microcode allowed for flexibility of implementation and quick
iteration. If there was a bug or a design change, you may only have to swap
the microcode out of [EPROMs](https://en.wikipedia.org/wiki/EPROM)s or RAM;
and the rest of your Am2900 building blocks/glue logic would remain untouched.

Today, [FPGAs](https://en.wikipedia.org/wiki/Field-programmable_gate_array) serve
much the same purpose, and can swap out an _entire_ CPU- not just microcode-
in seconds. In most cases, designing a hardwired control unit on an FPGA will
have acceptable iteration time and flexibility thanks to describing circuits in
code. A hardwired implementation also makes it easier to implement speed
optimizations like tight pipelining, which are difficult to reason about in
microcode[^1]. Thanks to changes in design process, there is _probably_ no
reason to do a performance-oriented microcode RISC-V implementation.

When optimizing for size, you still should probably hardwire your RISC-V core.
There are several perfectly usable hardwired RISC-V CPUs in < 1000 LCs, such as:

* [Award-winning SERV](https://github.com/olofk/serv)
* [FemtoRV32](https://github.com/BrunoLevy/learn-fpga/tree/master/FemtoRV/RTL/PROCESSOR)
* [ice-v](https://github.com/sylefeb/Silice/tree/master/projects/ice-v)
* [VexRiscv](https://github.com/SpinalHDL/VexRiscv)

I could probably design a _minimal_ hardwired Sentinel that doesn't have _that_
much more circuitry than the current microcoded version. However, I set a goal
of a complete RISC-V implementation including M-Mode in ~1000 LCs. It wasn't
clear to me- and still isn't- that a non-microcode RISC-V implementation could 
fit in 1000 LCs without making concessions that I didn't want to[^2], such as:

* Limit datapath width.
* Remove IRQs and M-Mode.
* Do not handle illegal instructions.

Even if I did a hardwired control unit, I knew that I was going to be multicycle
and not tightly pipelined. My own experience is that a basic RISC pipeline 32-bit
CPU takes at least 2000 ICE40 LCs minimum[^3] thanks to pipeline control logic.
At that point, for any design meeting my requirements, I figured the speed of a
microcoded and a hardwired RISC-V without pipeline control would be similar.

Around the same time in late 2020[^4] was when I found out about Mick and Brick.
I found the book fascinating (and still do), so I was already looking for an excuse
to write a microcode for fun. Additionally, I realized could put a microcode to
good use by leveraging FPGA [block RAM](https://nandland.com/lesson-15-what-is-a-block-ram-bram/)
to hold the microcode program. This gave me more precious LUT breathing room
that would otherwise be used by a hardwired implemetation. Since, I _already_ 
wasn't expecting my implementation to be fast, all of a sudden I found the
potential space savings of a microcode very appealing.

Via creative uses of block RAM and microcoding, Sentinel itself reached my goal
of ~1000 LCs while implementing `RV32I_Zicsr` and M-Mode. However, it's still
hit or miss whether a full [SoC](https://en.wikipedia.org/wiki/System_on_a_chip)
fits into my target ICE40HX1K FPGA (1280 LCs max), depending on `yosys`
optimizations and Amaranth changes. We'll see what the future holds.

Additionally, while not every application needs a super fast CPU, _there is
plenty of room for Sentinel and other small RISC-V implementations to coexist!_
Users need to decide for themselves if Sentinel fits their needs.

(terminology)=
## Terminology

Mick and Brick introduces some jargon that I use in Sentinel:

```{note}
This list is probably incomplete.
```

Condition Code Multiplexer
: A multiplexer of various conditional tests. The output of this multiplexer,
  selected by the microcode, becomes an test input to the Sequencer. The
  conditional test result can often be inverted by microcode to double the
  number of possible tests.
  
  Tests conditions used by Sentinel include:

  * Is the ALU output zero/nonzero?
  * Is a memory access complete/incomplete?
  * Did an exception occur/not occur?
  * Unconditionally true/false.

Macroinstruction
: An unit of execution from the CPU's instruction set, composed of
  microinstructions. In Sentinel's case, macroinstructions are RISC-V
  instructions.

Mapping (P)ROM
: A (P)ROM which maps of the macroarchitecture opcode into microprogram
  jump targets. It is the hardware version of a [jump table](https://en.wikipedia.org/wiki/Branch_table),
  where the jump index is retrived from the macroinstruction opcode.

  Each macroinstruction is a loop through the microprogram. The mapping
  (P)ROM jumps from microcode common to all macroinstructions to microcode
  specific to each (group of) macroinstruction(s).

  In Sentinel, the Mapping "(P)ROM" is implemented in combinational logic.

Microinstruction
: A microprogram/microcode instruction. Macroinstructions are composed of
  multiple microinstructions.

Microprogram Counter
: Register whose value is the address of the microcode instruction which
  will execute on the _next_ clock cycle, _assuming the sequencer chooses
  to use it_.

Pipeline Register
: In microcode, the pipeline register _specifically_ refers to a holding
  register containing the bits of the currently-executing microinstruction.

  In Sentinel, the pipeline register is part of the _synchronous_ read port
  of the Block RAM holding the microprogram. The address input to the
  microprogram Block RAM is the output of the sequencer; the data for 
  the microinstruction at this address appears on the read port on the next
  clock cycle.

Sequencer
: Component which supplies the address of the microinstruction which will be
  output on the _next_ clock cycle. It chooses between various sources based
  on a test condition provided by the Condition Code Multiplexer.
  
  Sources used by Sentinel, include:

  * The microprogram counter.
  * An address constant in the microcode instruction.
  * A mapping PROM.
  * An implied constant `0`.


## Microcode Fields

```{eval-rst}
.. automodule:: sentinel.ucodefields
   :member-order: bysource
```

<!-- (microcode-asm)=
## Default Microcode File Contents

```{eval-rst}
.. literalinclude:: ../../src/sentinel/microcode.asm
``` -->

## Footnotes

[^1]: Well, at least for me it's difficult to reason about! I've mulled over
      trying a microcoded 2 or 3 stage pipelined CPU before to see how bad
      the control flow of a microcode program would get. It might be possible
      to implement using `n`-way jumps and checking the pipeline state every
      microinstruction.

[^2]: I already _do_ make a concession in Sentinel's implementation by not
      implementing the Machine Timer. I justify it because the Machine Timer
      is Memory-Mapped I/O and not part of the CPU itself. A 64-bit counter
      is just too much to ask for with everything else going on in 1000 LCs.

[^3]: VexRiscv, a pipelined RISC-V, got LC usage down to 1130 by e.g. [not handling](https://github.com/SpinalHDL/VexRiscv/blob/7f2bccbef256b3ad40fb8dc8ba08a266f9c6256b/src/main/scala/vexriscv/plugin/CsrPlugin.scala#L297-L317)
      illegal instructions and having no interrupts. So that's cool :D.

[^4]: I did not work on Sentinel between fall 2020 and fall 2023. A number of
      things went right in fall 2023 such that I felt prepared to finish and
      maintain Sentinel.
