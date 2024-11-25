# Testing Sentinel

```{todo}
This section needs to be fleshed-out, and is an import of the old `README.md`
right now.
```

## Run Tests

```
pdm test
```

or

```
pdm test-quick
```

The above will invoke `pytest` and test Sentinel against handcrafted examples,
as well as the riscv-test repo binaries. See the `README.md`
in `tests/upstream` for information on how to refresh the binaries.

Right now (11/5/2023), the difference between `test` and `test-quick` is
minimal.

## Run RISC-V Formal Flow

```
pdm rvformal-all [-n num_cores]
```

or

```
pdm rvformal test-name
```

See `README.md` in `tests/formal` for more information, including
valid/available test names.

## Run RISCOF Flow

```
pdm riscof-all
```

or

```
pdm riscof-override /path/to/test_list.yaml
```

See `README.md` in `tests/riscof` for more information.
