# RISCV-Formal Tests

Tests from [RISC-V Formal](https://github.com/YosysHQ/riscv-formal) and
support config files/code go here.

Running the solvers used for RISC-V Formal is orchestrated by the [`dodo.py`](https://pydoit.org)
at the root of this repo. If you need to run tests run:

```
pdm run rvformal [name]
```

where `name` is the name of one of [available tests](#available-tests) listed
below. This will:

* Check out the RISC-V Formal submodule for you.
* Generated all files all files to run the formal flow will automatically by
  running RISC-V Formals' [genchecks.py](https://github.com/YosysHQ/riscv-formal/blob/main/checks/genchecks.py),
  subject to DoIt's dependency management.
* Actually run the RISC-V Formal flow.

You can also run `pdm run rvformal-all` to run everything; `rvformal-all`
takes an `-n [num_cores]` option to parallelize the tests. Either command will
generate a VCD file and disassembly for failing tasks at the root of this
repo.

Although public and documented, the DoIt tasks should be considered unstable;
`pdm run` should be preferred. Note that the DoIt tasks might not run unless
input files contents (like the Python source) are meaningfully changed.- i.e.
_not just the timestamp_. Run `pdm run rvformal-force [name]` to force-run an
up-to-date test.

`pdm run rvformal-status [name]` can be used to list whether a test/all tests
passed or failed. _This will run the test if it has not been run yet._

(Make sure `doit` and `click` are installed via `pdm install -G dev`. _You must
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
* `csrw_mvendorid_ch0`
* `csrc_zero_mvendorid_ch0`
* `csrw_marchid_ch0`
* `csrc_zero_marchid_ch0`
* `csrw_mimpid_ch0`
* `csrc_zero_mimpid_ch0`
* `csrw_mhartid_ch0`
* `csrc_zero_mhartid_ch0`
* `csrw_mconfigptr_ch0`
* `csrc_zero_mconfigptr_ch0`
* `csrw_misa_ch0`
* `csrc_zero_misa_ch0`
* `csrw_mstatush_ch0`
* `csrc_zero_mstatush_ch0`
* `csrw_mcountinhibit_ch0`
* `csrc_zero_mcountinhibit_ch0`
* `csrw_mtval_ch0`
* `csrc_zero_mtval_ch0`
* `csrw_mcycle_ch0`
* `csrc_zero_mcycle_ch0`
* `csrw_minstret_ch0`
* `csrc_zero_minstret_ch0`
* `csrw_mhpmcounter3_ch0`
* `csrc_zero_mhpmcounter3_ch0`
* `csrw_mhpmevent3_ch0`
* `csrc_zero_mhpmevent3_ch0`
* `csr_ill_eff_ch0`
* `csr_ill_302_ch0`
* `csr_ill_303_ch0`
* `csr_ill_306_ch0`
* `csr_ill_34a_ch0`
* `csr_ill_34b_ch0`
* `csr_ill_30a_ch0`
* `csr_ill_31a_ch0`

