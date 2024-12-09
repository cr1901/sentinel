# RISCOF Framework Tests

Tests from the [RISCOF Framework](https://github.com/riscv-non-isa/riscv-arch-test)
go here. _The tests in this directory at present only support Linux due to me
having trouble installing `opam`/`ocaml` on Windows._

Make sure `riscof` is installed via `pdm install -G dev -G riscof`. _You must
provide your own copies of `gcc`, `ocaml`, `opam`, and `sail`_. Additionally,
`riscv64-unknown-elf-gcc` must be provided. Then, run the RISCOF framework
tests using `pdm run riscof-all`.

Building the [SAIL RISC-V emulators](https://github.com/riscv/sail-riscv) required
by RISCOF is something of a pain. A gzipped Linux binary of SAIL is provided
under the [bin](bin) directory, and will be decompressed on demand. The 
[`dodo.py`](https://pydoit.org) at the root of this repo provides a
`_build_sail` task for rebuilding the SAIL emulators in an `opam` environment.
However, this should not be relied upon for normal development.

See [Testing Prerequisites](https://sentinel-cpu.readthedocs.io/en/latest/development/testing.html#prerequisites)
and [RISC-V Formal docs](https://sentinel-cpu.readthedocs.io/en/latest/development/testing.html#riscof)
for more information.
