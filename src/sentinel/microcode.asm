space block_ram: width 48, size 256;

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
  // map: Use address supplied by decoder if test fails. Otherwise, unconditional
  //      direct.
  // direct: Conditionally use address supplied by target field. Otherwise,
  //         cont.
  // direct_zero: Conditionally use address supplied by target field. Otherwise,
  //              0.
  jmp_type: enum { cont = 0; nop = 0; map; direct; direct_zero; }, default cont;

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
  a_src: enum { gp = 0; imm; alu_o; zero; four; }, default gp;
  b_src: enum { gp = 0; pc; imm; one; dat_r; }, default gp;
  // Latch the A/B inputs into the ALU. Contents vaid next cycle.

  alu_op: enum { add = 0; sub; and; or; xor; sll; srl; sra; cmp_ltu; \
                 sextb; sexthw; zextb; zexthw; }, default add;
  // In addition to writing ALU o, write C or D. Valid next cycle.
  // Modify inputs and outputs to ALU.
  alu_i_mod: enum { none = 0; inv_msb_a_b; twos_comp_b; }, default none;
  alu_o_mod: enum { none = 0; inv_lsb_o; clear_lsb_o }, default none;

  // Either read or write a register in the register file. _Which_ register
  // to read/write comes from the decoded insn.
  // Read contents will be on the data bus the next cycle. Written contents
  // will be valid on the next cycle. Reads are transparent.
  reg_read: bool, default 0;
  reg_write: bool, default 0;
  reg_r_sel: enum { insn_rs1 = 0; insn_rs2 = 1; insn_rs1_unregistered }, default insn_rs1;
  reg_w_sel: enum { insn_rd = 0; zero = 1; }, default insn_rd;

  // Start or continue a memory request. For convenience, an ack will
  // automatically stop a memory request for the cycle after ack, even if
  // mem_req is enabled. Valid on current cycle.
  mem_req: bool, default 0;
  mem_sel: enum { auto = 0; byte = 1; hword = 2; word = 3}, default auto;
  // Latch data address register from ALU output.
  latch_adr: bool, default 0;
  latch_data: bool, default 0;
  write_mem: bool, default 0;

  // Current mem request is insn fetch. Valid on current cycle. If set w/
  // mem_req, mem_sel ignored/calculated automatically.
  insn_fetch: bool, default 0;
};

#define INSN_FETCH insn_fetch => 1, mem_req => 1
#define SKIP_WAIT_IF_ACK jmp_type => direct_zero, cond_test => mem_valid, target => check_int
#define JUMP_TO_OP_END(trg) cond_test => true, jmp_type => direct, target => trg
#define LATCH_0_TO_TMP(trg) alu_op => nop, alu_tmp => trg
#define NOT_IMPLEMENTED jmp_type => direct, target => panic
#define NOP target => 0
#define READ_RS1 reg_read => 1, reg_r_sel => insn_rs1
#define READ_RS1_EAGER reg_read => 1, reg_r_sel => insn_rs1_unregistered
#define READ_RS2 reg_read => 1, reg_r_sel => insn_rs2
#define WRITE_RD reg_write => 1
#define READ_RS1_WRITE_RD READ_RS1, reg_write => 1, reg_w_sel => insn_rd
#define CMP_NE alu_op => cmp_eq, alu_o_mod => inv_lsb_o
#define CMP_LT alu_op => cmp_ltu, alu_i_mod => inv_msb_a_b
#define CMP_GEU alu_op => cmp_ltu, alu_o_mod => inv_lsb_o
#define CMP_GE  alu_op => cmp_ltu, alu_i_mod => inv_msb_a_b, alu_o_mod => inv_lsb_o
#define CONDTEST_ALU_CMP_FAILED cond_test => cmp_alu_o_5_lsbs_zero
#define CONDTEST_ALU_O_5_LSBS_NONZERO invert_test => 1, cond_test => cmp_alu_o_5_lsbs_zero

fetch:
wait_for_ack: INSN_FETCH, READ_RS1_EAGER, invert_test => 1, cond_test => mem_valid, \
                  jmp_type => direct, target => wait_for_ack;
              // Illegal insn or insn misaligned exception possible
check_int:    jmp_type => map, a_src => gp, src_op => latch_a, READ_RS2, \
                  cond_test => exception, target => save_pc;
origin 2;
       // Make sure x0 is initialized with 0.
reset: src_op => latch_a_b, b_src => one, a_src => zero;
       alu_op => and;
       jmp_type => direct, reg_write => 1, reg_w_sel => zero, target => fetch;

origin 8;
lb_1: src_op => latch_b, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => lb;
lh_1: src_op => latch_b, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => lh;
lw_1: src_op => latch_b, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => lw;
               NOT_IMPLEMENTED;
lbu_1: src_op => latch_b, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => lbu;
lhu_1: src_op => latch_b, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => lhu;

lb: alu_op => add;
    latch_adr => 1;
lb_wait:  b_src => dat_r, src_op => latch_b, mem_req => 1, invert_test => 1, \
              cond_test => mem_valid, mem_sel => byte, jmp_type => direct, \
              target => lb_wait;
          alu_op => sextb, JUMP_TO_OP_END(fast_epilog);

lh: alu_op => add;
    latch_adr => 1;
lh_wait:  b_src => dat_r, src_op => latch_b, mem_req => 1, invert_test => 1, \
              cond_test => mem_valid, mem_sel => hword, jmp_type => direct, \
              target => lh_wait;
          alu_op => sexthw, JUMP_TO_OP_END(fast_epilog);

lw: alu_op => add;
    latch_adr => 1;
lw_wait:  a_src => zero, b_src => dat_r, src_op => latch_a_b, mem_req => 1, invert_test => 1, \
              cond_test => mem_valid, mem_sel => word, jmp_type => direct, \
              target => lw_wait;
          alu_op => add, JUMP_TO_OP_END(fast_epilog);

lbu: alu_op => add;
     latch_adr => 1;
lbu_wait:  b_src => dat_r, src_op => latch_b, mem_req => 1, invert_test => 1, \
              cond_test => mem_valid, mem_sel => byte, jmp_type => direct, \
              target => lbu_wait;
           alu_op => zextb, JUMP_TO_OP_END(fast_epilog);

lhu: alu_op => add;
     latch_adr => 1;
lhu_wait:  b_src => dat_r, src_op => latch_b, mem_req => 1, invert_test => 1, \
              cond_test => mem_valid, mem_sel => hword, jmp_type => direct, \
              target => lhu_wait;
           alu_op => zexthw, JUMP_TO_OP_END(fast_epilog);

origin 0x30;
misc_mem: pc_action => inc, jmp_type => direct, target => fetch;

origin 0x40;
addi_1: src_op => latch_b, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => addi;
slli_1: src_op => latch_b, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => slli;
slti_1: src_op => latch_b, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => slti;
sltiu_1: src_op => latch_b, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => sltiu;
xori_1: src_op => latch_b, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => xori;
srli_1: src_op => latch_b, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => srli;
ori_1: src_op => latch_b, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => ori;
andi_1: src_op => latch_b, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => andi;
              NOT_IMPLEMENTED;  // 0b1000  subi?
              NOT_IMPLEMENTED;  // 0b1001
              NOT_IMPLEMENTED;  // 0b1010
              NOT_IMPLEMENTED;  // 0b1011
              NOT_IMPLEMENTED;  // 0b1100
srai_1: src_op => latch_b, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => srai;

origin 0x50;
auipc: src_op => latch_a_b, a_src => imm, b_src => pc;
       alu_op => add, pc_action => inc;
       WRITE_RD, jmp_type => direct, cond_test => true, target => fetch;
           
addi:         alu_op => add, INSN_FETCH, JUMP_TO_OP_END(fast_epilog);
slti:         CMP_LT, INSN_FETCH, JUMP_TO_OP_END(fast_epilog);
sltiu:        alu_op => cmp_ltu, INSN_FETCH, JUMP_TO_OP_END(fast_epilog);
xori:         alu_op => xor, INSN_FETCH, JUMP_TO_OP_END(fast_epilog);
ori:          alu_op => or, INSN_FETCH, JUMP_TO_OP_END(fast_epilog);
andi:         alu_op => and, INSN_FETCH, JUMP_TO_OP_END(fast_epilog);

              // Need 3-way jump! alu_op => sll, jmp_type => direct, cond_test => alu_ready, target => imm_ops_end;
slli:
              // Re: READ_RS1... reg addresses aren't latched, so if we need
              // reg values again, we need to latch them again.
              READ_RS1, a_src => zero, src_op => latch_a;
              // Bail if shift count was initially zero.
              a_src => gp, b_src => imm, src_op => latch_a_b, alu_op => add;
              READ_RS1, a_src => imm, b_src => one, src_op => latch_a_b, alu_op => sll, \
                  jmp_type => direct, cond_test => cmp_alu_o_5_lsbs_zero, target => shift_zero;
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

srli:
              // Re: READ_RS1... reg addresses aren't latched, so if we need
              // reg values again, we need to latch them again.
              READ_RS1, a_src => zero, src_op => latch_a;
              // Bail if shift count was initially zero.
              a_src => gp, b_src => imm, src_op => latch_a_b, alu_op => add;
              READ_RS1, a_src => imm, b_src => one, src_op => latch_a_b, alu_op => srl,
                  jmp_type => direct, cond_test => cmp_alu_o_5_lsbs_zero, target => shift_zero;
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

srai:
              // Re: READ_RS1... reg addresses aren't latched, so if we need
              // reg values again, we need to latch them again.
              READ_RS1, a_src => zero, src_op => latch_a;
              // Bail if shift count was initially zero.
              a_src => gp, b_src => imm, src_op => latch_a_b, alu_op => add;
              READ_RS1, a_src => imm, b_src => one, src_op => latch_a_b, alu_op => sra,
                  jmp_type => direct, cond_test => cmp_alu_o_5_lsbs_zero, target => shift_zero;
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

shift_zero:   a_src => zero, b_src => gp, src_op => latch_a_b;
              alu_op => add, JUMP_TO_OP_END(fast_epilog);

origin 0x80;
sb_1: READ_RS2, src_op => latch_b, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => sb;
sh_1: READ_RS2, src_op => latch_b, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => sh;
sw_1: READ_RS2, src_op => latch_b, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => sw;

origin 0x88;
branch_ops:
beq_1: src_op => latch_b, b_src => gp, jmp_type => direct, target => beq;
                
bne_1: src_op => latch_b, b_src => gp, jmp_type => direct, target => bne;
                NOT_IMPLEMENTED;
                NOT_IMPLEMENTED;
blt_1: src_op => latch_b, b_src => gp, jmp_type => direct, target => blt;
bge_1: src_op => latch_b, b_src => gp, jmp_type => direct, target => bge;
bltu_1: src_op => latch_b, b_src => gp, jmp_type => direct, target => bltu;
bgeu_1: src_op => latch_b, b_src => gp, jmp_type => direct, target => bgeu;

blt: a_src => imm, b_src => pc, src_op => latch_a_b, CMP_LT, \
        jmp_type => direct, target => branch_epilog;
bge: a_src => imm, b_src => pc, src_op => latch_a_b, CMP_GE, \
        jmp_type => direct, target => branch_epilog;
bltu: a_src => imm, b_src => pc, src_op => latch_a_b, alu_op => cmp_ltu, \
        jmp_type => direct, target => branch_epilog;
bgeu: a_src => imm, b_src => pc, src_op => latch_a_b, CMP_GEU, \
        jmp_type => direct, target => branch_epilog;

branch_epilog: alu_op => add, CONDTEST_ALU_CMP_FAILED, pc_action => inc, \
                  jmp_type => direct, target => fetch;
        jmp_type => direct, cond_test => true, target => fetch, pc_action => load_alu_o;


origin 0x98;
jalr: src_op => latch_a_b, a_src => four, b_src => pc;  // 8
      alu_op => add, reg_read => 1, reg_r_sel => insn_rs_1; // 9
      WRITE_RD, a_src => imm, b_src => gp, src_op => latch_a_b; // A
      alu_op => add, alu_o_mod => clear_lsb_o;
      jmp_type => direct, cond_test => true, target => fetch, pc_action => load_alu_o;

sb: a_src => zero, b_src => gp, src_op => latch_a_b, alu_op => add;
    alu_op => add, latch_adr => 1;
    mem_sel => byte, latch_data => 1;
// For stores/loads, we use a wishbone block cycle (don't deassert cyc in
// between data access and insn fetch)
sb_wait:  mem_req => 1, invert_test => 1, cond_test => mem_valid, \
              mem_sel => byte, write_mem => 1, jmp_type => direct_zero, target => sb_wait;

sh: a_src => zero, b_src => gp, src_op => latch_a_b, alu_op => add;
    alu_op => add, latch_adr => 1;
    mem_sel => hword, latch_data => 1;
// For stores/loads, we use a wishbone block cycle (don't deassert cyc in
// between data access and insn fetch)
sh_wait:  mem_req => 1, invert_test => 1, cond_test => mem_valid, \
              mem_sel => hword, write_mem => 1, jmp_type => direct_zero, target => sh_wait;

sw: a_src => zero, b_src => gp, src_op => latch_a_b, alu_op => add;
    alu_op => add, latch_adr => 1;
    mem_sel => word, latch_data => 1;
// For stores/loads, we use a wishbone block cycle (don't deassert cyc in
// between data access and insn fetch)
sw_wait:  mem_req => 1, invert_test => 1, cond_test => mem_valid, \
              mem_sel => word, write_mem => 1, jmp_type => direct_zero, target => sw_wait;

beq: a_src => imm, b_src => pc, src_op => latch_a_b, alu_op => sub;
     alu_op => add, invert_test => 1, cond_test => cmp_alu_o_zero, pc_action => inc, \
                  jmp_type => direct, target => fetch;
     jmp_type => direct, cond_test => true, target => fetch, pc_action => load_alu_o;

bne: a_src => imm, b_src => pc, src_op => latch_a_b, alu_op => sub;
     alu_op => add, cond_test => cmp_alu_o_zero, pc_action => inc, \
                  jmp_type => direct, target => fetch;
     jmp_type => direct, cond_test => true, target => fetch, pc_action => load_alu_o;

origin 0xB0;
jal: src_op => latch_a_b, a_src => four, b_src => pc;
     alu_op => add, a_src => imm, b_src => pc, src_op => latch_a_b;
     WRITE_RD, alu_op => add;
     jmp_type => direct, cond_test => true, target => fetch, pc_action => load_alu_o;

fast_epilog: WRITE_RD, INSN_FETCH, reg_read => 1, reg_r_sel => insn_rs1_unregistered, \
                  SKIP_WAIT_IF_ACK;

origin 0xc0;
add_1:        src_op => latch_b, b_src => gp, pc_action => inc, jmp_type => direct, \
                    target => add;
sll_1:        src_op => latch_b, b_src => gp, pc_action => inc, jmp_type => direct, \
                    target => sll;
slt_1:        src_op => latch_b, b_src => gp, pc_action => inc, jmp_type => direct, \
                    target => slt;
sltu_1:       src_op => latch_b, b_src => gp, pc_action => inc, jmp_type => direct, \
                    target => sltu;
xor_1:        src_op => latch_b, b_src => gp, pc_action => inc, jmp_type => direct, \
                    target => xor;
srl_1:        src_op => latch_b, b_src => gp, pc_action => inc, jmp_type => direct, \
                    target => srl;
or_1:         src_op => latch_b, b_src => gp, pc_action => inc, jmp_type => direct, \
                    target => or;
and_1:        src_op => latch_b, b_src => gp, pc_action => inc, jmp_type => direct, \
                    target => and;
sub_1:        src_op => latch_b, b_src => gp, pc_action => inc, jmp_type => direct, \
                    target => sub;  // 0b1000
              NOT_IMPLEMENTED;  // 0b1001
              NOT_IMPLEMENTED;  // 0b1010
              NOT_IMPLEMENTED;  // 0b1011
              NOT_IMPLEMENTED;  // 0b1101
sra_1:        src_op => latch_b, b_src => gp, pc_action => inc, jmp_type => direct, \
                    target => sra;

origin 0xd0;
lui:    a_src => zero, b_src => imm, src_op => latch_a_b, pc_action => inc, \
            jmp_type => direct, target => addi;


add:          alu_op => add, INSN_FETCH, JUMP_TO_OP_END(fast_epilog);
slt:          CMP_LT, INSN_FETCH, JUMP_TO_OP_END(fast_epilog);
sltu:         alu_op => cmp_ltu, INSN_FETCH, JUMP_TO_OP_END(fast_epilog);
xor:          alu_op => xor, INSN_FETCH, JUMP_TO_OP_END(fast_epilog);
or:           alu_op => or, INSN_FETCH, JUMP_TO_OP_END(fast_epilog);
and:          alu_op => and, INSN_FETCH, JUMP_TO_OP_END(fast_epilog);
sub:          alu_op => sub, INSN_FETCH, JUMP_TO_OP_END(fast_epilog);

             // Re: add; pass through RS2 unmodified, and check whether 5 LSBs
             // were zero. The shift loops above can be reused once we do
             // the initial zero check.
sll:  
             READ_RS1, a_src => zero, src_op => latch_a;
             READ_RS2, a_src => gp, src_op => latch_a, alu_op => add;
             a_src => gp, b_src => one, src_op => latch_a_b, alu_op => sll,
                  jmp_type => direct, CONDTEST_ALU_O_5_LSBS_NONZERO, target => sll_loop;
             READ_RS1, jmp_type => direct, target => shift_zero;

srl:  
             READ_RS1, a_src => zero, src_op => latch_a;
             READ_RS2, a_src => gp, src_op => latch_a, alu_op => add;
             a_src => gp, b_src => one, src_op => latch_a_b, alu_op => srl,
                  jmp_type => direct, CONDTEST_ALU_O_5_LSBS_NONZERO, target => srl_loop;
             READ_RS1, jmp_type => direct, target => shift_zero;

sra:  
             READ_RS1, a_src => zero, src_op => latch_a;
             READ_RS2, a_src => gp, src_op => latch_a, alu_op => add;
             a_src => gp, b_src => one, src_op => latch_a_b, alu_op => sra,
                  jmp_type => direct, CONDTEST_ALU_O_5_LSBS_NONZERO, target => sra_loop;
             READ_RS1, jmp_type => direct, target => shift_zero;

// Interrupt handler.
origin 0xf0;
NOT_IMPLEMENTED;
// Send PC through ALU
// save_pc: a_src => pc, b_src => target, jmp_type => nop, target => 0;

// Misc?
origin 248;
panic: jmp_type => direct, target => panic
