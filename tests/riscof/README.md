# RISCOF Tests Placeholder

Tests from the [RISCOF Framework](https://github.com/riscv-non-isa/riscv-arch-test)
go here. _The tests in this directory at present only support Linux._

Building the [SAIL RISC-V emulators](https://github.com/riscv/sail-riscv) required
by RISCOF is something of a pain. For now, unlike for the [upstream](/tests/upstream/README.md)
binaries, the [`dodo.py`](https://pydoit.org) only minimally automates compilation
(but does at least set up `eval $(opam env)` environment variables for you).
GNU Make is required to build the emulators until I am comfortable automating
the flow myself from within DoIt.

## Context For Building SAIL RISC-V

The SAIL RISC-V emulators are written in a mix of C, [OCaml](https://ocaml.org/)
and the [`sail`](https://github.com/rems-project/sail) DSL. From a packaging
standpoint, the SAIL RISC-V emulators are OCaml packages whose dependencies
are described using the [`opam`](https://opam.ocaml.org/) package manager
and [`opam` files](https://opam.ocaml.org/doc/Manual.html#opam). On
Ubuntu 20.04, installing the prerequisites for the emulators looks something
like this:

```
sudo apt-get install opam  build-essential libgmp-dev z3 pkg-config zlib1g-dev
opam init -y --disable-sandboxing
opam switch create create ocaml-base-compiler.4.08.1
opam install sail -y
```

Note that the actual build requires `make`; `opam` only handles installing
dependencies, and delegates to `make` for building.<sup>1</sup>

As of 11/6/2023, the [build instructions](https://riscof.readthedocs.io/en/latest/installation.html#install-plugin-models)
provided by RISCOF documentation for the [SAIL RISC-V emulators](https://github.com/riscv/sail-riscv) are
[out-of-date](https://github.com/riscv-software-src/riscof/issues/88); I
didn't successfully compile the emulator until I did `opam switch create ocaml-base-compiler.4.08.1`.

(Make sure `riscof` is installed via `pdm install -G dev G riscof`. _You must
provide your own copies of `gcc`, `ocaml`, `opam`, and `sail`, as described
above_. Additionally, `riscv64-unknown-elf-gcc` must be provided.)

## Running RISCOF

Step 2 of [Section 7.1](https://riscof.readthedocs.io/en/latest/arch-tests.html#setup-all-the-dut-and-ref-plugins)
seems incorrect; `riscof` will set up the `sail_cSim` plugin for you as
part of `riscof setup --dutname=sentinel`.

Like in [SERV](https://github.com/olofk/serv/tree/main/verif), the Sentinel and
SAIL plugins have been modified to expect `riscv64-unknown-elf-gcc`, even for
32-bit.


## Footnotes

1. Since we don't want to _install_ the emulators in the system, it should be
   in principle possible to `cd sail-riscv`, and then do `opam install . --deps-only`.
   However, I [couldn't get that to work](https://stackoverflow.com/questions/50942323/opam-install-error-no-solution-found)...
