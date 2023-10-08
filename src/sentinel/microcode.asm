space block_ram: width 44, size 256;

space block_ram;
origin 0;

fields block_ram: {
  // Target field for direct jmp_type. The micropc jumps to here next
  // cycle if the test succeeds.
  target: width 8, origin 0, default 0;

  // Various jump types to jump around the microcode program next cycle.
  // cont: Increment upc by 1.
  // nop: Same as cont, but indicate we are using the target field for
  //      something else.
  // map: Use address supplied by opcode if test fails. Otherwise, unconditional
  //      direct.
  // direct: Conditionally use address supplied by target field. Otherwise,
  //         cont.
  // map_funct: Unconditionally jump to address supplied by target field
  //            plus an offset based on the current minor opcode.
  //            See "requested_op" signal.
  // direct_zero: Conditionally use address supplied by target field. Otherwise,
  //              0.
  jmp_type: enum { cont = 0; nop = 0; map; direct; map_funct; direct_zero; }, default cont;

  // Various tests (valid current cycle) for conditional jumps:
  // int: Is interrupt line high?
  // exception: Illegal insn, EBRAK, ECALL, misaligned insn, misaligned ld/st?
  // mem_valid: Is current dat_r valid? Did write finish?
  // true: Unconditionally succeed
  cond_test: enum { intr; exception; cmp_alu_o_5_lsbs_zero; cmp_alu_o_zero; mem_valid; true}, default true;

  // Invert the results of the test above. Valid current cycle.
  invert_test: bool, default 0;

  // Modify the PC for the next cycle.
  pc_action: enum { hold = 0; inc; load_alu_o; }, default hold;

  // ALU src latch/selection.
  src_op: enum { none = 0; latch_a; latch_b; latch_a_b; }, default none;
  a_src: enum { gp = 0; pc; csr; imm; target; alu_o; zero; }, default gp;
  b_src: enum { gp = 0; pc; csr; imm; target; one; }, default gp;
  // Latch the A/B inputs into the ALU. Contents vaid next cycle.

  alu_op: enum { add = 0; sub; and; or; xor; sll; srl; sra; cmp_eq; cmp_ltu; cmp_geu; nop; passthru; }, default nop;
  // In addition to writing ALU o, write C or D. Valid next cycle.
  // Modify inputs and outputs to ALU.
  alu_mod: enum { none = 0; inv_msb_a_b; inv_lsb_o; twos_comp_b; }, default none;

  // Either read or write a register in the register file. _Which_ register
  // to read/write comes either from the decoded insn or from microcode inputs.
  // Read contents will be on the data bus the next cycle. Written contents
  // will be valid on the next cycle. Reads are transparent.
  reg_read: bool, default 0;
  reg_write: bool, default 0;
  // GP regs and scratch registers are multiplexed. Use this bit to choose
  // which set to read/write.
  reg_set: enum { gp = 0; scratch = 1; }, default gp;
  // Insn chooses the register to read or write, or ucode does; this field
  // also provides the top bit. Target 0-3 provides the others.
  reg_r_sel: enum { insn_rs1 = 0; insn_rs2 = 1; ucode0 = 2; ucode1 = 3; insn_rs1_unregistered }, default insn_rs1;
  // Likewise, target 4-7 provides the other bits.
  reg_w_sel: enum { insn_rd = 0; ucode0 = 2; ucode1 = 3}, default insn_rd;

  // Start or continue a memory request. For convenience, an ack will
  // automatically stop a memory request for the cycle after ack, even if
  // mem_req is enabled. Valid on current cycle.
  mem_req: bool, default 0;

  // Current mem request is insn fetch. Valid on current cycle.
  insn_fetch: bool, default 0;
};

#define INSN_FETCH insn_fetch => 1, mem_req => 1
#define SKIP_WAIT_IF_ACK jmp_type => direct_zero, cond_test => mem_valid, target => check_int
#define JUMP_TO_OP_END(trg) cond_test => true, jmp_type => direct, target => trg
#define LATCH_0_TO_TMP(trg) alu_op => nop, alu_tmp => trg
#define NOT_IMPLEMENTED jmp_type => direct, target => panic
#define NOP target => 0
#define READ_RS1 reg_set => 0, reg_read => 1, reg_r_sel => insn_rs1
#define READ_RS1_EAGER reg_set => 0, reg_read => 1, reg_r_sel => insn_rs1_unregistered
#define READ_RS2 reg_set => 0, reg_read => 1, reg_r_sel => insn_rs2
#define WRITE_RD reg_set => 0, reg_write => 1, reg_w_sel => insn_rd
#define READ_RS1_WRITE_RD READ_RS1, reg_write => 1, reg_w_sel => insn_rd
#define CMP_NE alu_op => cmp_eq, alu_mod => inv_lsb_o
#define CMP_LT alu_op => cmp_ltu, alu_mod => inv_msb_a_b
#define SUB alu_op => add, alu_mod => twos_comp_b
#define CONDTEST_ALU_O_5_LSBS_NONZERO invert_test => 1, cond_test => cmp_alu_o_5_lsbs_zero

fetch:
wait_for_ack: INSN_FETCH, READ_RS1_EAGER, invert_test => 1, cond_test => mem_valid, \
                  jmp_type => direct, target => wait_for_ack;
              // Illegal insn or insn misaligned exception possible
check_int:    jmp_type => map, a_src => gp, src_op => latch_a, READ_RS2, \
                  cond_test => exception, target => save_pc;

origin 8;
imm_prolog: src_op => latch_b, b_src => imm, pc_action => inc, jmp_type => map_funct, \
                target => imm_ops;
reg_prolog: src_op => latch_b, b_src => gp, pc_action => inc, jmp_type => map_funct, \
                target => reg_ops;
lui_prolog: a_src => zero, b_src => imm, src_op => latch_a_b, pc_action => inc,
                jmp_type => direct, target => addi;

imm_ops:
addi:         alu_op => add, INSN_FETCH, JUMP_TO_OP_END(fast_epilog);
// Trampolines for multicycle ops are almost zero-cost except for microcode space.
slli_trampoline:
              // Re: READ_RS1... reg addresses aren't latched, so if we need
              // reg values again, we need to latch them again.
              READ_RS1, a_src => zero, src_op => latch_a, \
                  jmp_type => direct, target => slli_prolog;
slti:         CMP_LT, INSN_FETCH, JUMP_TO_OP_END(fast_epilog);
sltiu:        alu_op => cmp_ltu, INSN_FETCH, JUMP_TO_OP_END(fast_epilog);
xori:         alu_op => xor, INSN_FETCH, JUMP_TO_OP_END(fast_epilog);
srli_trampoline: READ_RS1, a_src => zero, src_op => latch_a, \
                    jmp_type => direct, target => srli_prolog;
ori:          alu_op => or, INSN_FETCH, JUMP_TO_OP_END(fast_epilog);
andi:         alu_op => and, INSN_FETCH, JUMP_TO_OP_END(fast_epilog);
subi:         NOT_IMPLEMENTED;  // 0b1000
              NOT_IMPLEMENTED;  // 0b1001
              NOT_IMPLEMENTED;  // 0b1010
              NOT_IMPLEMENTED;  // 0b1011
              NOT_IMPLEMENTED;  // 0b1100
srai_trampoline: READ_RS1, a_src => zero, src_op => latch_a, \
                    jmp_type => direct, target => srai_prolog;

              // Need 3-way jump! alu_op => sll, jmp_type => direct, cond_test => alu_ready, target => imm_ops_end;
slli_prolog:
              // Bail if shift count was initially zero.
              a_src => gp, b_src => imm, src_op => latch_a_b, alu_op => cmp_eq;
              a_src => imm, b_src => one, src_op => latch_a_b, alu_op => sll, \
                  jmp_type => direct, CONDTEST_ALU_O_5_LSBS_NONZERO, target => fetch;
sll_loop:
              // Subtract 1 from shift cnt, preliminarily save shift results
              // in case we bail (microcode cannot be interrupted, so user
              // will never see this intermediate result).
              // Also write the previous shift, either from prolog or last
              // loop iteration.
              alu_op => sub, a_src => alu_o, src_op => latch_a, WRITE_RD;
              // Then, do the shift, and bail if the shift cnt reached zero.
              alu_op => sll, a_src => alu_o, b_src => one, src_op => latch_a_b, \
                  jmp_type => direct_zero, CONDTEST_ALU_O_5_LSBS_NONZERO, target => sll_loop;

srli_prolog:
              // Bail if shift count was initially zero.
              a_src => gp, b_src => imm, src_op => latch_a_b, alu_op => cmp_eq;
              a_src => imm, b_src => one, src_op => latch_a_b, alu_op => srl,
                  jmp_type => direct, CONDTEST_ALU_O_5_LSBS_NONZERO, target => fetch;
srl_loop:
              // Subtract 1 from shift cnt, preliminarily save shift results
              // in case we bail (microcode cannot be interrupted, so user
              // will never see this intermediate result).
              // Also write the previous shift, either from prolog or last
              // loop iteration.
              alu_op => sub, a_src => alu_o, src_op => latch_a, WRITE_RD;
              // Then, do the shift, and bail if the shift cnt reached zero.
              alu_op => srl, a_src => alu_o, b_src => one, src_op => latch_a_b, \
                  jmp_type => direct_zero, CONDTEST_ALU_O_5_LSBS_NONZERO, target => srl_loop;

srai_prolog:
              // Bail if shift count was initially zero.
              a_src => gp, b_src => imm, src_op => latch_a_b, alu_op => cmp_eq;
              a_src => imm, b_src => one, src_op => latch_a_b, alu_op => sra,
                  jmp_type => direct, CONDTEST_ALU_O_5_LSBS_NONZERO, target => fetch;
sra_loop:
              // Subtract 1 from shift cnt, preliminarily save shift results
              // in case we bail (microcode cannot be interrupted, so user
              // will never see this intermediate result).
              // Also write the previous shift, either from prolog or last
              // loop iteration.
              alu_op => sub, a_src => alu_o, src_op => latch_a, WRITE_RD;
              // Then, do the shift, and bail if the shift cnt reached zero.
              alu_op => sra, a_src => alu_o, b_src => one, src_op => latch_a_b, \
                  jmp_type => direct_zero, CONDTEST_ALU_O_5_LSBS_NONZERO, target => sra_loop;

reg_ops:
add:          alu_op => add, INSN_FETCH, JUMP_TO_OP_END(fast_epilog);
sll_trampoline: READ_RS1, a_src => zero, src_op => latch_a, \
                    jmp_type => direct, target => sll_prolog;
slt:          CMP_LT, INSN_FETCH, JUMP_TO_OP_END(fast_epilog);
sltu:         alu_op => cmp_ltu, INSN_FETCH, JUMP_TO_OP_END(fast_epilog);
xor:          alu_op => xor, INSN_FETCH, JUMP_TO_OP_END(fast_epilog);
srl_trampoline: READ_RS1, a_src => zero, src_op => latch_a, \
                    jmp_type => direct, target => srl_prolog;
or:           alu_op => or, INSN_FETCH, JUMP_TO_OP_END(fast_epilog);
and:          alu_op => and, INSN_FETCH, JUMP_TO_OP_END(fast_epilog);
sub:          alu_op => sub, INSN_FETCH, JUMP_TO_OP_END(fast_epilog);  // 0b1000
              NOT_IMPLEMENTED;  // 0b1001
              NOT_IMPLEMENTED;  // 0b1010
              NOT_IMPLEMENTED;  // 0b1011
              NOT_IMPLEMENTED;  // 0b1101
sra_trampoline: READ_RS1, a_src => zero, src_op => latch_a, \
                    jmp_type => direct, target => sra_prolog;

             // Re: add; pass through RS2 unmodified, and check whether 5 LSBs
             // were zero. The shift loops above can be reused once we do
             // the initial zero check.
sll_prolog:  READ_RS2, a_src => gp, src_op => latch_a, alu_op => add;
             a_src => gp, b_src => one, src_op => latch_a_b, alu_op => sll,
                  jmp_type => direct_zero, CONDTEST_ALU_O_5_LSBS_NONZERO, target => sll_loop;

srl_prolog:  READ_RS2, a_src => gp, src_op => latch_a, alu_op => add;
             a_src => gp, b_src => one, src_op => latch_a_b, alu_op => srl,
                  jmp_type => direct_zero, CONDTEST_ALU_O_5_LSBS_NONZERO, target => srl_loop;

sra_prolog:  READ_RS2, a_src => gp, src_op => latch_a, alu_op => add;
             a_src => gp, b_src => one, src_op => latch_a_b, alu_op => sra,
                  jmp_type => direct_zero, CONDTEST_ALU_O_5_LSBS_NONZERO, target => sra_loop;

fast_epilog:
              WRITE_RD, INSN_FETCH, reg_read => 1, reg_r_sel => insn_rs1_unregistered, \
                  SKIP_WAIT_IF_ACK;

// Interrupt handler.
origin 224;
// Send PC through ALU
save_pc: a_src => pc, b_src => target, jmp_type => nop, target => 0;

// Misc?
origin 248;
panic: jmp_type => direct, target => panic
