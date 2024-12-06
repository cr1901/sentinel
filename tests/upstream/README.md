# Upstream Tests

Tests from the [upstream tests](https://github.com/riscv-software-src/riscv-tests)
are in this directory. AFAICT, the [RISCOF tests](/tests/riscof/README.md)
are (were?) originally derived from this repository and are more comprehensive.
However, this repo looks easier to start with.

Make sure `doit` is installed via `pdm install -G dev`. _You must provide your
own copy of `riscv64-unknown-elf-gcc`_. Then, run using `pdm test` or
`pdm test-quick`.

See [Testing Prerequisites](https://sentinel-cpu.readthedocs.io/en/latest/development/testing.html#prerequisites)
and [Sim And Upstream docs](https://sentinel-cpu.readthedocs.io/en/latest/development/testing.html#sim-and-upstream)
for more information.
