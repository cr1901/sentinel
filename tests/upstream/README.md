# Upstream Tests

Tests from the [upstream tests](https://github.com/riscv-software-src/riscv-tests)
are in this directory. It is not clear to me what the difference between these
upstream tests and the RISCOF tests are, but this one looks easier to start
with.

Binaries are generated using the [`dodo.py`](https://pydoit.org) at the root of
this repo. If you need to regenerate binaries, use `pdm run compile-upstream`;
although the DoIt tasks are document, using `pdm` should be preferred over
running `doit` directly.

(Make sure `doit` is installed via `pdm install --dev`. _You must provide your
own copy of `riscv64-unknown-elf-gcc`_.)
