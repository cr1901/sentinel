# Upstream Tests

Tests from the [upstream tests](https://github.com/riscv-software-src/riscv-tests)
are in this directory. AFAICT, the [RISCOF tests](/tests/riscof/README.md)
are (were?) originally derived from this repository and are more comprehensive.
However, this repo looks easier to start with.

Binaries are generated using the [`dodo.py`](https://pydoit.org) at the root of
this repo. If you need to regenerate binaries, use `pdm run compile-upstream`;
although the DoIt tasks are documented, using `pdm` should be preferred over
running `doit` directly.

(Make sure `doit` is installed via `pdm install -G dev`. _You must provide your
own copy of `riscv64-unknown-elf-gcc`_.)
