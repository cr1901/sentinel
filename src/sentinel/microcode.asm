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
  cond_test: enum { exception; cmp_alu_o_zero; mem_valid; true}, default true;

  // Invert the results of the test above. Valid current cycle.
  invert_test: bool, default 0;

  // Modify the PC for the next cycle.
  pc_action: enum { hold = 0; inc; load_alu_o; }, default hold;

  // ALU src latch/selection.
  latch_a: bool, default 0;
  latch_b: bool, default 0;
  a_src: enum { gp = 0; imm; alu_o; zero; four; neg_one; thirty_one; }, default gp;
  b_src: enum { gp = 0; pc; imm; one; dat_r; csr_imm; csr }, default gp;
  // Latch the A/B inputs into the ALU. Contents vaid next cycle.

  alu_op: enum { add = 0; sub; and; or; xor; sll; srl; sra; cmp_ltu; }, default add;
  // In addition to writing ALU o, write C or D. Valid next cycle.
  // Modify inputs and outputs to ALU.
  alu_i_mod: enum { none = 0; inv_msb_a_b; }, default none;

  // Either read or write a register in the register file. _Which_ register
  // to read/write comes from the decoded insn.
  // Read contents will be on the data bus the next cycle, _except_
  // when insn_rs1 is paired with insn_fetch (in which contents are valid
  // on the current cycle). Written contents will be valid on the next cycle.
  // Reads are transparent.
  reg_read: bool, default 0;
  reg_write: bool, default 0;
  reg_r_sel: enum { insn_rs1 = 0; insn_rs2 = 1; }, default insn_rs1;
  reg_w_sel: enum { insn_rd = 0; zero = 1; }, default insn_rd;

  // CSR regs can either be read or written in a given cycle, but not both.
  // CSR ops override reg_ops. This is technically a union.
  csr_op: enum { none = 0; read_csr; write_csr }, default none;
  csr_sel: enum { insn_csr; trg_csr }, default insn_csr;

  // Start or continue a memory request. For convenience, an ack will
  // automatically stop a memory request for the cycle after ack, even if
  // mem_req is enabled. Valid on current cycle.
  mem_req: bool, default 0;
  mem_sel: enum { auto = 0; byte = 1; hword = 2; word = 3; }, default auto;
  mem_extend: enum { zero = 0; sign = 1}, default zero;

  // Latch data address register from ALU output.
  latch_adr: bool, default 0;
  latch_data: bool, default 0;
  write_mem: bool, default 0;

  // Current mem request is insn fetch. Valid on current cycle. If set w/
  // mem_req, mem_sel ignored/calculated automatically.
  insn_fetch: bool, default 0;

  except_ctl: enum { none; latch_decoder; latch_jal; latch_adr; enter_int; \
                     leave_int }, default none;
};

#define INSN_FETCH insn_fetch => 1, mem_req => 1
#define INSN_FETCH_EAGER_READ_RS1 INSN_FETCH, READ_RS1
#define SKIP_WAIT_IF_ACK jmp_type => direct_zero, cond_test => mem_valid, target => check_int
#define JUMP_TO_OP_END(trg) cond_test => true, jmp_type => direct, target => trg
#define NOT_IMPLEMENTED jmp_type => direct, target => panic
#define NOP target => 0
#define READ_RS1 reg_read => 1, reg_r_sel => insn_rs1
#define READ_RS2 reg_read => 1, reg_r_sel => insn_rs2
#define WRITE_RD reg_write => 1
#define WRITE_RD_CSR csr_op => write_csr
#define READ_RS1_WRITE_RD READ_RS1, reg_write => 1, reg_w_sel => insn_rd
#define CMP_LT alu_op => cmp_ltu, alu_i_mod => inv_msb_a_b
#define CONDTEST_ALU_NONZERO invert_test => 1, cond_test => cmp_alu_o_zero

fetch:
wait_for_ack: INSN_FETCH_EAGER_READ_RS1, invert_test => 1, cond_test => mem_valid, \
                  jmp_type => direct, target => wait_for_ack;
              // Illegal insn or insn misaligned exception possible
check_int:    jmp_type => map, a_src => gp, latch_a => 1, READ_RS2, \
                  cond_test => exception, target => save_pc;
origin 2;
       // Make sure x0 is initialized with 0.
reset: latch_a => 1, latch_b => 1, b_src => one, a_src => zero;
       alu_op => and;
       jmp_type => direct, reg_write => 1, reg_w_sel => zero, target => fetch;

origin 8;
lb_1: latch_b => 1, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => lb;
lh_1: latch_b => 1, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => lh;
lw_1: latch_b => 1, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => lw;
               NOT_IMPLEMENTED;
lbu_1: latch_b => 1, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => lbu;
lhu_1: latch_b => 1, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => lhu;

lb: alu_op => add;
    latch_adr => 1;
lb_wait:  a_src => zero, b_src => dat_r, latch_a => 1, latch_b => 1, mem_req => 1, invert_test => 1, \
              cond_test => mem_valid, mem_sel => byte, mem_extend => sign, jmp_type => direct, \
              target => lb_wait;
          alu_op => add, JUMP_TO_OP_END(fast_epilog);

lh: alu_op => add;
    latch_adr => 1;
lh_wait:  a_src => zero, b_src => dat_r, latch_a => 1, latch_b => 1, mem_req => 1, invert_test => 1, \
              cond_test => mem_valid, mem_sel => hword, mem_extend => sign, jmp_type => direct, \
              target => lh_wait;
          alu_op => add, JUMP_TO_OP_END(fast_epilog);

lw: alu_op => add;
    latch_adr => 1;
lw_wait:  a_src => zero, b_src => dat_r, latch_a => 1, latch_b => 1, mem_req => 1, invert_test => 1, \
              cond_test => mem_valid, mem_sel => word, jmp_type => direct, \
              target => lw_wait;
          alu_op => add, JUMP_TO_OP_END(fast_epilog);

lbu: alu_op => add;
     latch_adr => 1;
lbu_wait:  a_src => zero, b_src => dat_r, latch_a => 1, latch_b => 1, mem_req => 1, invert_test => 1, \
              cond_test => mem_valid, mem_sel => byte, jmp_type => direct, \
              target => lbu_wait;
           alu_op => add, JUMP_TO_OP_END(fast_epilog);

lhu: alu_op => add;
     latch_adr => 1;
lhu_wait:  a_src => zero, b_src => dat_r, latch_a => 1, latch_b => 1, mem_req => 1, invert_test => 1, \
              cond_test => mem_valid, mem_sel => hword, jmp_type => direct, \
              target => lhu_wait;
           alu_op => add, JUMP_TO_OP_END(fast_epilog);

origin 0x24;
// CSR ops take two cycles to decode. This is effectively a no-op in case
// there's an illegal CSR access or something.
csr_trampoline: jmp_type => map, cond_test => exception, target => save_pc;
csrro0_1: a_src => zero, b_src => one, latch_a => 1, latch_b => 1, pc_action => inc, \
            jmp_type => direct, target => csrro0;
csrw_1: NOT_IMPLEMENTED;  // reg_read => 1, reg_r_sel => insn_csr, 
csrrw_1: NOT_IMPLEMENTED;
csrr_1: NOT_IMPLEMENTED;
csrrs_1: NOT_IMPLEMENTED;
csrrc_1: NOT_IMPLEMENTED;
csrwi_1: a_src => zero, b_src => csr_imm, latch_a => 1, latch_b => 1, pc_action => inc, \
            jmp_type => direct, target => csrwi;
csrrwi_1: csr_op => read_csr, csr_sel => insn_csr, a_src => zero, b_src => csr_imm, \
            latch_a => 1, latch_b => 1, pc_action => inc, jmp_type => direct, \
            target => csrrwi;
csrrsi_1: NOT_IMPLEMENTED;
csrrci_1: csr_op => read_csr, csr_sel => insn_csr, a_src => zero, latch_a => 1, \
            pc_action => inc, jmp_type => direct, target => csrrci;

origin 0x30;
misc_mem: pc_action => inc, jmp_type => direct, target => fetch;

csrro0: alu_op => and, JUMP_TO_OP_END(fast_epilog);
csrwi: alu_op => add, JUMP_TO_OP_END(fast_epilog_csr);
csrrwi: alu_op => add, latch_b => 1, b_src => csr; // Latch old CSR value, pass thru new.
        WRITE_RD_CSR, alu_op => add, JUMP_TO_OP_END(fast_epilog);  
csrrci: latch_b => 1, b_src => csr;
        alu_op => add, a_src => neg_one, b_src => csr_imm, latch_a => 1, latch_b => 1; 
        WRITE_RD, b_src => gp, latch_b => 1, alu_op => xor; // Bit Clear = A & ~B
        a_src => alu_o, latch_a => 1;
        alu_op => and, JUMP_TO_OP_END(fast_epilog_csr);

origin 0x40;
addi_1: latch_b => 1, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => addi;
slli_1: latch_b => 1, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => slli;
slti_1: latch_b => 1, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => slti;
sltiu_1: latch_b => 1, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => sltiu;
xori_1: latch_b => 1, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => xori;
srli_1: latch_b => 1, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => srli;
ori_1: latch_b => 1, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => ori;
andi_1: latch_b => 1, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => andi;
              NOT_IMPLEMENTED;  // 0b1000  subi?
              NOT_IMPLEMENTED;  // 0b1001
              NOT_IMPLEMENTED;  // 0b1010
              NOT_IMPLEMENTED;  // 0b1011
              NOT_IMPLEMENTED;  // 0b1100
srai_1: latch_b => 1, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => srai;

origin 0x50;
auipc: latch_a => 1, latch_b => 1, a_src => imm, b_src => pc;
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
              READ_RS1, a_src => zero, latch_a => 1;
              // Bail if shift count was initially zero.
              a_src => gp, b_src => imm, latch_a => 1, latch_b => 1, alu_op => add;
              READ_RS1, a_src => imm, b_src => one, latch_a => 1, latch_b => 1, alu_op => sll, \
                  jmp_type => direct, cond_test => cmp_alu_o_zero, target => shift_zero;
sll_loop:
              // Subtract 1 from shift cnt, preliminarily save shift results
              // in case we bail (microcode cannot be interrupted, so user
              // will never see this intermediate result).
              // Also write the previous shift, either from prolog or last
              // loop iteration.
              alu_op => sub, a_src => alu_o, latch_a => 1, WRITE_RD;
              // Then, do the shift, and bail if the shift cnt reached zero.
              alu_op => sll, a_src => alu_o, b_src => one, latch_a => 1, latch_b => 1, \
                  jmp_type => direct_zero, CONDTEST_ALU_NONZERO, target => sll_loop;

srli:
              // Re: READ_RS1... reg addresses aren't latched, so if we need
              // reg values again, we need to latch them again.
              READ_RS1, a_src => zero, latch_a => 1;
              // Bail if shift count was initially zero.
              a_src => gp, b_src => imm, latch_a => 1, latch_b => 1, alu_op => add;
              READ_RS1, a_src => imm, b_src => one, latch_a => 1, latch_b => 1, alu_op => srl,
                  jmp_type => direct, cond_test => cmp_alu_o_zero, target => shift_zero;
srl_loop:
              // Subtract 1 from shift cnt, preliminarily save shift results
              // in case we bail (microcode cannot be interrupted, so user
              // will never see this intermediate result).
              // Also write the previous shift, either from prolog or last
              // loop iteration.
              alu_op => sub, a_src => alu_o, latch_a => 1, WRITE_RD;
              // Then, do the shift, and bail if the shift cnt reached zero.
              alu_op => srl, a_src => alu_o, b_src => one, latch_a => 1, latch_b => 1, \
                  jmp_type => direct_zero, CONDTEST_ALU_NONZERO, target => srl_loop;

srai:
              // Re: READ_RS1... reg addresses aren't latched, so if we need
              // reg values again, we need to latch them again.
              // We AND here because imm12 will have a hardcoded "1" outside
              // the 5 LSBs.
              READ_RS1, a_src => thirty_one, latch_a => 1;
              // Bail if shift count was initially zero.
              a_src => gp, latch_a => 1, alu_op => and;
              READ_RS1, a_src => alu_o, b_src => one, latch_a => 1, latch_b => 1, alu_op => sra,
                  jmp_type => direct, cond_test => cmp_alu_o_zero, target => shift_zero;
sra_loop:
              // Subtract 1 from shift cnt, preliminarily save shift results
              // in case we bail (microcode cannot be interrupted, so user
              // will never see this intermediate result).
              // Also write the previous shift, either from prolog or last
              // loop iteration.
              alu_op => sub, a_src => alu_o, latch_a => 1, WRITE_RD;
              // Then, do the shift, and bail if the shift cnt reached zero.
              alu_op => sra, a_src => alu_o, b_src => one, latch_a => 1, latch_b => 1, \
                  jmp_type => direct_zero, CONDTEST_ALU_NONZERO, target => sra_loop;

shift_zero:   a_src => zero, b_src => gp, latch_a => 1, latch_b => 1;
              alu_op => add, JUMP_TO_OP_END(fast_epilog);

origin 0x80;
sb_1: READ_RS2, latch_b => 1, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => sb;
sh_1: READ_RS2, latch_b => 1, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => sh;
sw_1: READ_RS2, latch_b => 1, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => sw;

origin 0x88;
branch_ops:
beq_1: latch_b => 1, b_src => gp, jmp_type => direct, target => beq;
                
bne_1: latch_b => 1, b_src => gp, jmp_type => direct, target => bne;

branch_lt_epilog: alu_op => add, cond_test => cmp_alu_o_zero, pc_action => inc, \
                  jmp_type => direct, target => fetch;
        jmp_type => direct, cond_test => true, target => fetch, pc_action => load_alu_o;

blt_1: latch_b => 1, b_src => gp, jmp_type => direct, target => blt;
bge_1: latch_b => 1, b_src => gp, jmp_type => direct, target => bge;
bltu_1: latch_b => 1, b_src => gp, jmp_type => direct, target => bltu;
bgeu_1: latch_b => 1, b_src => gp, jmp_type => direct, target => bgeu;

beq: a_src => imm, b_src => pc, latch_a => 1, latch_b => 1, alu_op => sub, \
        jmp_type => direct, target => branch_gte_epilog;
bne: a_src => imm, b_src => pc, latch_a => 1, latch_b => 1, alu_op => sub, \
        jmp_type => direct, target => branch_lt_epilog;
blt: a_src => imm, b_src => pc, latch_a => 1, latch_b => 1, CMP_LT, \
        jmp_type => direct, target => branch_lt_epilog;
bge: a_src => imm, b_src => pc, latch_a => 1, latch_b => 1, CMP_LT, \
        jmp_type => direct, target => branch_gte_epilog;
bltu: a_src => imm, b_src => pc, latch_a => 1, latch_b => 1, alu_op => cmp_ltu, \
        jmp_type => direct, target => branch_lt_epilog;
bgeu: a_src => imm, b_src => pc, latch_a => 1, latch_b => 1, alu_op => cmp_ltu, \
        jmp_type => direct, target => branch_gte_epilog;

branch_gte_epilog: alu_op => add, invert_test => true, cond_test => cmp_alu_o_zero, \
                     pc_action => inc, jmp_type => direct, target => fetch;
        jmp_type => direct, cond_test => true, target => fetch, pc_action => load_alu_o;

origin 0x98;
jalr: b_src => imm, latch_b => 1; 
      alu_op => add, latch_a => 1, latch_b => 1, a_src => four, b_src => pc; // TODO: latch exception.
      alu_op => add, latch_a => 1, latch_b => 1, a_src => alu_o, b_src => one; // TODO: cond_test => exception, jmp_type => direct
      WRITE_RD, alu_op => xor;  // Bit Clear = A & ~B
      jmp_type => direct, cond_test => true, target => fetch, pc_action => load_alu_o;

sb: a_src => zero, b_src => gp, latch_a => 1, latch_b => 1, alu_op => add;
    alu_op => add, latch_adr => 1;
    mem_sel => byte, latch_data => 1;
// For stores/loads, we use a wishbone block cycle (don't deassert cyc in
// between data access and insn fetch)
sb_wait:  mem_req => 1, invert_test => 1, cond_test => mem_valid, \
              mem_sel => byte, write_mem => 1, jmp_type => direct_zero, target => sb_wait;

sh: a_src => zero, b_src => gp, latch_a => 1, latch_b => 1, alu_op => add;
    alu_op => add, latch_adr => 1;
    mem_sel => hword, latch_data => 1;
// For stores/loads, we use a wishbone block cycle (don't deassert cyc in
// between data access and insn fetch)
sh_wait:  mem_req => 1, invert_test => 1, cond_test => mem_valid, \
              mem_sel => hword, write_mem => 1, jmp_type => direct_zero, target => sh_wait;

sw: a_src => zero, b_src => gp, latch_a => 1, latch_b => 1, alu_op => add;
    alu_op => add, latch_adr => 1;
    mem_sel => word, latch_data => 1;
// For stores/loads, we use a wishbone block cycle (don't deassert cyc in
// between data access and insn fetch)
sw_wait:  mem_req => 1, invert_test => 1, cond_test => mem_valid, \
              mem_sel => word, write_mem => 1, jmp_type => direct_zero, target => sw_wait;

origin 0xB0;
jal: a_src => imm, b_src => pc, latch_a => 1, latch_b => 1;
     alu_op => add; // TODO: latch exception.
     NOP; // TODO: cond_test => exception, jmp_type => direct
     pc_action => load_alu_o, latch_a => 1, latch_b => 1, a_src => four, b_src => pc;
     INSN_FETCH, alu_op => add, JUMP_TO_OP_END(fast_epilog);

fast_epilog: INSN_FETCH_EAGER_READ_RS1, WRITE_RD, SKIP_WAIT_IF_ACK;
fast_epilog_csr: INSN_FETCH_EAGER_READ_RS1, WRITE_RD_CSR, SKIP_WAIT_IF_ACK;

origin 0xc0;
add_1:        latch_b => 1, b_src => gp, pc_action => inc, jmp_type => direct, \
                    target => add;
sll_1:        latch_b => 1, b_src => gp, pc_action => inc, jmp_type => direct, \
                    target => sll;
slt_1:        latch_b => 1, b_src => gp, pc_action => inc, jmp_type => direct, \
                    target => slt;
sltu_1:       latch_b => 1, b_src => gp, pc_action => inc, jmp_type => direct, \
                    target => sltu;
xor_1:        latch_b => 1, b_src => gp, pc_action => inc, jmp_type => direct, \
                    target => xor;
srl_1:        latch_b => 1, b_src => gp, pc_action => inc, jmp_type => direct, \
                    target => srl;
or_1:         latch_b => 1, b_src => gp, pc_action => inc, jmp_type => direct, \
                    target => or;
and_1:        latch_b => 1, b_src => gp, pc_action => inc, jmp_type => direct, \
                    target => and;
sub_1:        latch_b => 1, b_src => gp, pc_action => inc, jmp_type => direct, \
                    target => sub;  // 0b1000
              NOT_IMPLEMENTED;  // 0b1001
              NOT_IMPLEMENTED;  // 0b1010
              NOT_IMPLEMENTED;  // 0b1011
              NOT_IMPLEMENTED;  // 0b1101
sra_1:        latch_b => 1, b_src => gp, pc_action => inc, jmp_type => direct, \
                    target => sra;

origin 0xd0;
lui:    a_src => zero, b_src => imm, latch_a => 1, latch_b => 1, pc_action => inc, \
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
             READ_RS1, a_src => thirty_one, latch_a => 1;
             READ_RS2, a_src => gp, latch_a => 1, alu_op => and;
             a_src => alu_o, b_src => one, latch_a => 1, latch_b => 1, alu_op => sll,
                  jmp_type => direct, CONDTEST_ALU_NONZERO, target => sll_loop;
             READ_RS1, jmp_type => direct, target => shift_zero;

srl:  
             READ_RS1, a_src => thirty_one, latch_a => 1;
             READ_RS2, a_src => gp, latch_a => 1, alu_op => and;
             a_src => alu_o, b_src => one, latch_a => 1, latch_b => 1, alu_op => srl,
                  jmp_type => direct, CONDTEST_ALU_NONZERO, target => srl_loop;
             READ_RS1, jmp_type => direct, target => shift_zero;

sra:  
             READ_RS1, a_src => thirty_one, latch_a => 1;
             READ_RS2, a_src => gp, latch_a => 1, alu_op => and;
             a_src => alu_o, b_src => one, latch_a => 1, latch_b => 1, alu_op => sra,
                  jmp_type => direct, CONDTEST_ALU_NONZERO, target => sra_loop;
             READ_RS1, jmp_type => direct, target => shift_zero;

// Interrupt handler.
origin 0xf0;
save_pc: NOT_IMPLEMENTED;
// Send PC through ALU
// save_pc: a_src => pc, b_src => target, jmp_type => nop, target => 0;

// Misc?
origin 248;
panic: jmp_type => direct, target => panic
