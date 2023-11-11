# RISCOF Tests Placeholder

Tests from the [RISCOF Framework](https://github.com/riscv-non-isa/riscv-arch-test)
go here. _The tests in this directory at present only support Linux due to me
having trouble installing `opam`/`ocaml` on Windows._

Building the [SAIL RISC-V emulators](https://github.com/riscv/sail-riscv) required
by RISCOF is something of a pain. A gzipped Linux binary of SAIL is provided
under the [bin](bin) directory, and will be decompressed on demand. The 
[`dodo.py`](https://pydoit.org) at the root of this repo provides a
`_build_sail` task for rebuilding the SAIL emulators in an `opam` environment.
However, this should not be relied upon for normal development.

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

Running RISCOF is orchestrated by the [`dodo.py`](https://pydoit.org) at the
root of this repo. To check out the RISCOF submodule and run the tests, run:

```
pdm run riscof-all
```

The above will:

* Check out the RISCOF submodule for you.
* Decompress the SAIL emulator, if necessary.
* Generate a `riscof_work` directory full of config files and tests for you
  using `riscof testfile`, subject to DoIt's dependency management.
* Delete a number of output subdirectories (`dut` and `ref`) under
  `riscof_work; `riscof` expects these to be empty before running a test.
  This will _not_ fail if the various `dut` and `ref` directories don't exist.
* Finally, run RISCOF flow using `riscof run`.

The results of `riscof run` will be available under `riscof_work/report.html`,
and the various `dut` and `ref` subdirectories provided for each test under
`rv32i_m` (ELF files, disassemblies, etc).

One of the files generated in `riscof_work` will be a `test_list.yaml`.
Occassionally, it may be useful to truncate the `test_list.yaml` to run a
subset of generated tests. Since RISCOF currently (as of 11/11/2023)
[doesn't make](https://github.com/riscv-software-src/riscof/issues/100#issuecomment-1806772615)
running individual tests easy, use the following:

```
pdm run riscof-override /path/to/new/test_list.yaml
```

_Note that if the "delete a number of subdirectories" step needs to run, all
`dut` and `ref` subdirectories possibly containing interesting results will
be deleted!_ In addition, checking whether `test_list.yaml` is up-to-date is
hash based; two separate `test_list.yaml` files with the same exact contents
will be considered the same file to `riscof-override`.

Although public and documented, the DoIt tasks should be considered unstable;
`pdm run` should be preferred.

### Other Notes

* Step 2 of [Section 7.1](https://riscof.readthedocs.io/en/latest/arch-tests.html#setup-all-the-dut-and-ref-plugins)
of the RISCOF docs seems incorrect; `riscof` will set up the `sail_cSim` plugin
for you as part of `riscof setup --dutname=sentinel` (although this step should
not be necessary to run normally, and is currently not provided even in
`dodo.py`).

* Like in [SERV](https://github.com/olofk/serv/tree/main/verif), the Sentinel and
SAIL plugins have been modified to expect `riscv64-unknown-elf-gcc`, even for
32-bit.

## Footnotes

1. Since we don't want to _install_ the emulators in the system, it should be
   in principle possible to `cd sail-riscv`, and then do `opam install . --deps-only`.
   However, I [couldn't get that to work](https://stackoverflow.com/questions/50942323/opam-install-error-no-solution-found)...
