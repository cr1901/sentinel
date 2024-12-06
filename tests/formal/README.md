# RISCV-Formal Tests

Tests from [RISC-V Formal](https://github.com/YosysHQ/riscv-formal) and
support config files/code go here. Running the solvers used for RISC-V Formal
is orchestrated by the [`dodo.py`](https://pydoit.org) at the root of this
repo.

Make sure `doit` and `click` are installed via `pdm install -G dev`. _You must
provide your own copy of `yosys`, `sby` and `boolector`_. Then, run the
RISC-V Formal suite using `pdm run rvformal-all [-n num_cores]`.

See [Testing Prerequisites](https://sentinel-cpu.readthedocs.io/en/latest/development/testing.html#prerequisites)
and [RISC-V Formal docs](https://sentinel-cpu.readthedocs.io/en/latest/development/testing.html#risc-v-formal)
for more information.
