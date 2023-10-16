# RISCV-Formal Tests

Tests from [RISC-V Formal](https://github.com/YosysHQ/riscv-formal) and
support config files/code go here.

Running the solvers used for RISC-V Formal is orchestrated by the [`dodo.py`](https://pydoit.org)
at the root of this repo. If you need to run tests, first run:

```
pdm run rvformal-gen
```

and then run:

```
pdm run rvformal [name]
```

where `name` is the name of one of the `.sby` files _minus the extension_
under `riscv-formal/cores/sentinel/checks` (generated in `rvformal-gen`).

You can also run `pdm run rvformal-all` to run everything. Either command will
generate a VCD file and disassembly for failing tasks.

The DoIt tasks are considered private despite not being named with a leading
underscore (so that the custom `title`s print out). Note that the DoIt tasks
might not run unless input files contents (like the Python source)- _not just
the timestamp_- are meaningfully changed.
