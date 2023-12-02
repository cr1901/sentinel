<p align="center">
  <img src="doc/White Background Ver.png" 
  alt="Sentinel Logo. A lighthouse is shining its light on a PCB and computer
  chip. The silicon die of the computer chip is visible. The text &quot;Sentinel&quot;
  in a black and gray gradient stretches in parallel with the lighthouse's beam.
  The text covers the base of the lighthouse and is below the chip.">
</p>

<p align="center">
  <strong>Logo by <a href="https://keidavt.carrd.co/">keidaVT</a></strong>.
</p>

[![CI](https://github.com/cr1901/sentinel/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/cr1901/sentinel/actions/workflows/ci.yml)

# `sentinel`

Sentinel is a small RISC-V CPU (`RV32I_Zicsr`) written in [Amaranth](https://amaranth-lang.org/).
It implements the Machine Mode privileged spec, and is designed to fit into
~1000 4-input LUTs or less on an FPGA. It is a good candidate for control tasks
where a programmable state machine or custom size-tailored core would otherwise
be used.

Unlike most RISC-V implementations, Sentinel is [microcoded](https://en.wikipedia.org/wiki/Microcode),
not pipelined. Instructions require multiple clock cycles to execute. Sentinel
is therefore not necessarily a good fit for applications where high throughput/
IPC is required. See [below](#instruction-cycle-counts).

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

## Getting Started

Sentinel uses:

* [PDM](https://pdm.fming.dev/latest/) as its package/dependency manager, and
  to orchestrate all things you can do with this repo.
* [m5meta](https://github.com/brouhaha/m5meta/) microcode assembler, without
  which Sentinel would optimize down to ~0 LUTs :).
* [yosys](https://github.com/YosysHQ/yosys) and [nextpnr](https://github.com/YosysHQ/nextpnr/)
  for size-benchmarking. _The user must provide these._
* [pytest](https://pytest.org) for basic/regression testing.
* [DoIt](https://pydoit.org/) as a lower-level dependency-graph aware task
  orchestrator (called from `pdm`).
* [riscv-tests](https://github.com/riscv-software-src/riscv-tests), an older
  set of unit tests for RISC-V processors. Running these is done via `pytest`.
* [RISC-V Formal](https://github.com/YosysHQ/riscv-formal) to verify that
  desirable properties of Sentinel (such as "instructions write the correct
  destination") hold for all possible inputs over a bounded number of clock
  cycles after reset.
* [RISCOF](https://github.com/riscv-software-src/riscof/), the unit test
  framework that is maintained by RISC-V International themselves. This appears
  to have originally been derived from the `riscv-tests`, but is much more
  comprehensive.

The latter five are only required for development. Additionally for
development, a user must provide:

* `riscv64-unknown-elf-gcc` to compile tests from riscv-tests (I'm not sure
  what the correct way to install the compiler is nowadays, I use 8.3.0.)
* [SymbiYosys](https://github.com/YosysHQ/sby), a driver program for RISC-V
  Formal.
* [Boolector](https://github.com/Boolector/boolector), the SMT Solver that
  RISC-V Formal uses.

RISCOF also requires the [SAIL RISC-V emulator](https://github.com/riscv/sail-riscv).
This is a pain to compile, so I provide a Linux binary (and eventually Windows
if I can get OCaml to behave long enough. I _used_ to be able to install it
just fine :'D!).

**A user must first run the following before anything else:**

```
pdm install -G dev -G examples
```

### Generate A Core

This command will generate a core with a Wishbone Classic bus, and `clk`,
`rst`, and `irq` input pins (Sentinel uses a single clock domain):

```
pdm gen > sentinel.v
```

On reset, Sentinel begins execution at address `0``. See the [CSR](#csrs)
section for information on exception handling (including interrupts).

_The Wishbone bus uses a block xfer to do a back-to-back memory write an
instruction fetch._ Otherwise, the wishbone bus will deassert CYC/STB the cycle
after receipt of ACK. _I may neeed to interface to IP that can't handle block
cycles, so I will probably relax the block cycle requirement in the future via
an option._

For help, run:

```
pdm gen -h
```

### Generate A Demo Bitstream For [Lattice iCEstick](https://www.latticesemi.com/icestick)

```
pdm demo
```

For help, run:

```
pdm demo -h
```

### Run Tests

```
pdm test
```

or

```
pdm test-quick
```

The above will invoke `pytest` and test Sentinel against handcrafted examples,
as well as the riscv-test repo binaries. See the [README.md](tests/upstream/README.md)
in `tests/upstream` for information on how to refresh the binaries.

Right now (11/5/2023), the difference between `test` and `test-quick` is
minimal.

### Run RISC-V Formal Flow

```
pdm rvformal-all [-n num_cores]
```

or

```
pdm rvformal test-name
```

See [README.md](tests/formal/README.md) in `tests/formal` for more information,
including valid/available test names.

### Run RISCOF Flow

```
pdm riscof-all
```

or

```
pdm riscof-override /path/to/test_list.yaml
```

See [README.md](tests/riscof/README.md) in `tests/riscof` for more information.

### List `pdm` Scripts And `doit` Tasks

```
pdm run --list
```

```
pdm doit list [--all] [task]
```

`doit` tasks are documented as a courtesy, and to make sure developers/users
don't get stuck. I am unsure about `doit` tasks' stability, so **prefer running
`pdm` as a wrapper to `doit` rather than running `doit` directly.**

## Block Diagram

![Simplified block diagram of Sentinel. Black arrows are physical connections.
Blue arrows represent microcode ROM outputs to Sentinel components, including
feedback into the microcode ROM as inputs. Purple arrows represent microcode
ROM inputs from the other components.](doc/blockdiag.png)

## Instruction Cycle Counts

**TODO**. I need to create a test that gets latency and throughput for each
instruction type of the core. Some general observations (as of 11/18/2023),
from examining the microcode:

* _There is room for improvement, even without making the core bigger._
* Fetch/Decode takes a _minimum_ of two cycles thanks to Wishbone classic's
  REQ/ACK handshake taking two cycles.
  * When Wishbone ACK is asserted, Decode is taking place.
  * The GP file is a synchronous single read port, single write port. Sentinel
    loads RS1 out of the register file during Decode.
* All instructions share the same operation the cycle after ACK/Decode:
  * Check for exceptions/interrupts, go to exception handler if so.
  * Latch RS1 into the ALU.
  * Load RS2 out of the register file, in anticipation for a "simple"
    instruction.
  * Jump to the instruction-specific microcode block.
* At minimum, an instruction (`addi`, `or`, etc) takes 3 cycles to retire
  after the initial shared cycles. This means Sentinel instructions have a
  minimum latency of 6 cycles per instruction (CPI).
* Sentinel instructions have a maximum throughput of 4 CPI by overlapping the
  2 Fetch/Decode cycles of the _next_ instruction after the initial 3 shared
  cycles of the _current_ instruction when possible ("pipelining").
  * Some instructions overlap one of the Fetch/Decode cycles, some don't
    overlap either of them. In particular, shift instructions with a nonzero
    shift count don't pipeline Fetch/Decode. It may be possible to _always_ 
    overlap at least one cycle, but I haven't tweaked the core yet to ensure
    this is a sound optimization.
* _Shift instructions need work_:
  * For a shift of zero, shift-immediate latency is 10 CPI, throughtput 9 CPI.
    Shift-register latency is 11 CPI, throughput 10 CPI.
  * For a shift of nonzero `n`, shift-immediate _and_ shift-register latency
    and throughput is 7 + 2*`n` CPI.
* Branch-not-taken latency and throughput is 7 CPI. Branch-taken latency and
  throughput is 8 CPI.
* JAL/JALR latency is 9 CPI, throughput is 7 CPI.
* Store latency and throughput is 8 CPI minimum. 2 cycles minimum are spent
  waiting for Wishbone ACK.
  * The core will not release STB/CYC between the store and fetch of the next
    instruction.
* Load latency is 10 CPI minimum, and throughput is 9 CPI. 2 cycles minimum
  are spent waiting for Wishbone ACK.
  * The core _will_ release STB/CYC before fetch of the next instruction.
* CSR instructions require an extra Decode cycle compared to all other
  instructions (to check for legality).
  * At minimum, a read of a read-only zero CSR register has a latency of 7 CPI,
    and a throughput of 6 CPI.
  * At maximum, `csrrc` has a latency of 11 CPI, and a throughput of 10 CPI.
* Entering an exception handler requires 5 clocks from the cycle at which
  the exception condition is detected.
  * `mret` has a latency and throughput of 8 CPI. 

## CSRs

Sentinel physically implements the following CSRs:

* `mscratch`
* `mcause`
  * The core can only physically trigger a subset of defined exceptions:
    * Machine external interrupt
    * Instruction access misaligned
    * Illegal instruction
    * Breakpoint
    * Load address misaligned
    * Store address misaligned
    * Environment call from M-mode

    In particular worth noting:
    * _Misaligned accesses are not implemented in hardware._
    * There is no machine timer (a 64-bit counter is a bit too much to
      ask for right now :(...).
* `mip`
  * Only the `MEIP` bit is implemented. The RISC-V Privileged Spec says:

    > `MEIP` is read-only in `mip`, and is set and cleared by a
    > platform-specific interrupt controller.

    The user must provide their own interrupt controller. One simple
    implementation is to `OR` all external interrupt sources together, and
    query each peripheral when `MEIP` is pending to find which peripherals
    need attention. This is implemented for the serial and timer peripherals
    in the [attosoc](examples/attosoc.py) example.

    In the future, I may implement the high (platform-specific) 16-bits of
    `mip`/`mie` to make interrupt-handling quicker.
* `mie`
  * Only the `MEIE` bit is implemented.
* `mstatus`
  * Only the `MPP`, `MPIE`, and `MIE` bits are implemented.
* `mtvec`
  * The `BASE` is writeable; only the Direct `MODE` setting is implemented.
* `mepc`

Additionally, the following CSRs are implemented as read-only zero (only the
first 5 of the below registers trigger an exception on an attempt to write):

* `mvendorid`
* `marchid`
* `mimpid`
* `mhartid`
* `mconfigptr`
* `misa`
* `mstatush`
* `mcountinhibit`
* `mtval`
* `mcycle`
* `minstret`
* `mhpmcounter3-31`
* `mhpmevent3-31`

All remaining machine-mode CSRs are unimplemented and trigger an exception on
_any_ access:

* `medeleg`
* `mideleg`
* `mcounteren`
* `mtinst`
* `mtval2`
* `menvcfg`
* `menvcfgh`
* `mseccfg`
* `mseccfgh`
