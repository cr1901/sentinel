# Upstream Tests

Tests from the [upstream tests](https://github.com/riscv-software-src/riscv-tests)
are in this directory. It is not clear to me what the difference between these
upstream tests and the RISCOF tests are, but this one looks easier to start
with.

Binaries are generated using the [`dodo.py`](https://pydoit.org) at the root of
this repo. If you need to regenerate binaries, use `pdm run compile-upstream`;
right now, the DoIt tasks are considered private.

(Make sure `doit` is installed via `pdm install --dev`.)
