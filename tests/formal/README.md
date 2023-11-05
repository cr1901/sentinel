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

You can also run `pdm run rvformal-all` to run everything; `rvformal-all`
takes an `-n [num_cores]` option to parallelize the tests. Either command will
generate a VCD file and disassembly for failing tasks at the root of this
repo.

Although public and documented, the DoIt tasks should be considered unstable;
`pdm run` should be preferred. Note that the DoIt tasks might not run unless
input files contents (like the Python source) are meaningfully changed.- i.e.
_not just the timestamp_.  Run `pdm run rvformal-force [name]` to force-run an
up-to-date test.

`pdm run rvformal-status [name]` can be used to list whether a test/all tests
passed or failed.

(Make sure `doit` and `click` are installed via `pdm install --dev`. _You must
provide your own copy of `sby` and `boolector`_.)


## Available Tests
This list should reflect the `SBY_TESTS` tuple in `dodo.py`. It may
occassionally be out of date:

* `causal_ch0`
* `cover`
* `insn_addi_ch0`
* `insn_add_ch0`
* `insn_andi_ch0`
* `insn_and_ch0`
* `insn_auipc_ch0`
* `insn_beq_ch0`
* `insn_bgeu_ch0`
* `insn_bge_ch0`
* `insn_bltu_ch0`
* `insn_blt_ch0`
* `insn_bne_ch0`
* `insn_jalr_ch0`
* `insn_jal_ch0`
* `insn_lbu_ch0`
* `insn_lb_ch0`
* `insn_lhu_ch0`
* `insn_lh_ch0`
* `insn_lui_ch0`
* `insn_lw_ch0`
* `insn_ori_ch0`
* `insn_or_ch0`
* `insn_sb_ch0`
* `insn_sh_ch0`
* `insn_slli_ch0`
* `insn_sll_ch0`
* `insn_sltiu_ch0`
* `insn_slti_ch0`
* `insn_sltu_ch0`
* `insn_slt_ch0`
* `insn_srai_ch0`
* `insn_sra_ch0`
* `insn_srli_ch0`
* `insn_srl_ch0`
* `insn_sub_ch0`
* `insn_sw_ch0`
* `insn_xori_ch0`
* `insn_xor_ch0`
* `pc_bwd_ch0`
* `pc_fwd_ch0`
* `reg_ch0`
* `unique_ch0`
* `liveness_ch0`
* `csrw_mscratch_ch0`
* `csrc_any_mscratch_ch0`
* `csrw_mcause_ch0`
* `csr_ill_eff_ch0`
* `csrw_mip_ch0`
* `csrc_zero_mip_ch0`
* `csrw_mie_ch0`
* `csrc_zero_mie_ch0`
* `csrw_mstatus_ch0`
* `csrc_const_mstatus_ch0`
* `csrw_mtvec_ch0`
* `csrc_zero_mtvec_ch0`
* `csrw_mepc_ch0`
* `csrc_zero_mepc_ch0`

