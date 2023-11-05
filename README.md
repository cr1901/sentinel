# `sentinel`

Sentinel is a small RV32I_Zcsr CPU written in [Amaranth](https://amaranth-lang.org/).
It is designed to fit into 1000 4-input LUTs or less on an FPGA, and isa good
candidate for control tasks where a programmable state machine or custom
size-tailored core would otherwise be used.

Unlike most RISC-V implementations, Sentinel is [microcoded](https://en.wikipedia.org/wiki/Microcode),
not pipelined. Instructions require multiple clock cycles to execute. Sentinel
is therefore not necessarily a good fit for applications where high throughput/
IPC is required.

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

The latter four are only required for development. Additionally for
development, a user must provide:

* `riscv64-unknown-elf-gcc` to compile tests from riscv-tests (I'm not sure
  what the correct way to install the compiler is nowadays, I use 8.3.0.)
* [SymbiYosys](https://github.com/YosysHQ/sby), a driver program for RISC-V
  Formal.
* [Boolector](https://github.com/Boolector/boolector), the SMT Solver that
  RISC-V Formal uses.

**A user must first run the following before anything else:**

```
pdm install
```

The [Run Tests](#run-tests) section and below require:

```
pdm install --dev
```

### Generate A Core

To generate

```
pdm gen > sentinel.v
```

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
pdm rvformal-gen
pdm rvformal-all [-n num_cores]
```

See [README.md](tests/formal/README.md) in `tests/formal` for more information.


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
