space block_ram: width 48, size 256;

space block_ram;
origin 0;

// Microcode fields in this space correspond to classes defined in
// ucodefields.py. The ordering of microcode fields is taken from this file.
// Width and enum field names are validated against the Amaranth source after
// assembly.
//
// Comments are included for convenience, and efforts are made to ensure
// they don't contradict comments in ucodefields.py. In case of conflict,
// ucodefields.py comments take priority.
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
  a_src: enum { gp = 0; imm; alu_o; zero; four; thirty_one; }, default gp;
  b_src: enum { gp = 0; pc; imm; one; dat_r; csr_imm; csr; mcause_latch }, default gp;
  // Latch the A/B inputs into the ALU. Contents vaid next cycle.

  alu_op: enum { add = 0; sub; and; or; xor; sll; srl; sra; cmp_ltu; }, default add;
  // Modify inputs and outputs to ALU.
  alu_i_mod: enum { none = 0; inv_msb_a_b; }, default none;
  alu_o_mod: enum { none = 0; inv_lsb_o; clear_lsb_o }, default none;

  // Either read or write a register in the register file. _Which_ register
  // to read/write comes from the decoded insn.
  // Read contents will be on the data bus the next cycle. When insn_rs1 is
  // paired with insn_fetch, the address sent to the reg file comes directly
  // from bits 15 to 20 on the WB DAT_R bus. Otheriwse, the address sent to the 
  // reg file is retrieved from a holding register for bits 15 to 20 of the
  // previously-decoded instruction word.
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

  except_ctl: enum { none; latch_decoder; latch_jal; latch_store_adr; \
                     latch_load_adr; enter_int; leave_int; }, default none;
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
#define CMP_GEU alu_op => cmp_ltu, alu_o_mod => inv_lsb_o
#define CMP_GE  alu_op => cmp_ltu, alu_i_mod => inv_msb_a_b, alu_o_mod => inv_lsb_o
// The LT[U]/GE[U] tests will either return zero or one; this makes it fine
// to reuse the conditional meant for shift ops.
#define CONDTEST_ALU_ZERO cond_test => cmp_alu_o_zero
// HINT: alu_o_mod -> inv_lsb_o can be used to
// implement a check for ALU output being exactly one. Can
// this be utilized anywhere?
// Also, inv_lsb_o does the same as XOR 1. So ((A XOR 1)) XOR 1 is a no-op,
// if a bit convoluted.
#define CONDTEST_ALU_NONZERO invert_test => 1, cond_test => cmp_alu_o_zero
#define JUMP_TO_ZERO cond_test => true, invert_test=> true, jmp_type => direct_zero
#define STOP_MEMREQ_THEN_JUMP_TO_ZERO mem_req=>0, JUMP_TO_ZERO

// CSR Register addresses in private RAM
#define MSTATUS 0
#define MIE 0x4
#define MTVEC 0x5
#define MSCRATCH 0x8
#define MEPC 0x9
#define MCAUSE 0xA
#define MIP 0xC

fetch:
wait_for_ack: INSN_FETCH_EAGER_READ_RS1, invert_test => 1, cond_test => mem_valid, \
                  jmp_type => direct, target => wait_for_ack;
              // Illegal insn or insn misaligned exception possible
check_int:    jmp_type => map, a_src => gp, latch_a => 1, READ_RS2, \
                  except_ctl => latch_decoder, cond_test => exception, \
                  target => save_pc;
origin 2;
       // Make sure x0 is initialized with 0. PC might not be valid, depending
       // on which microcycle a reset or clock enable (if applicable) was
       // asserted/deasserted. So reset PC to zero also.
       // Additionally, MCAUSE CSR is nominally a copy of a latch, but it also
       // should be 0 (for our implementation) after reset.
       //
       // Stale microcode exists on microcode ROM read port for one cycle after
       // non-power-on-resets, since read port lags by one cycle except for
       // after POR. The effects of stale microcode appear on the second cycle
       // after reset. This has the following consequences which we exploit:
       // * Spec mandates MSTATUS.MIE is zero after reset. The ALU output is
       // initialized to 0 upon reset, so stale microcode on read port will
       // never write a non-zero value to registers.
       // * One full cycle after reset was deasserted, we make can no assumptions
       // about ALU contents. So we must explicitly reinitialize the ALU to 0.
reset: latch_a => 1, latch_b => 1, b_src => one, a_src => zero;
       alu_op => and;
       alu_op => and, reg_write => 1, reg_w_sel => zero;
       jmp_type => direct_zero, pc_action => load_alu_o, csr_op => write_csr, \
            csr_sel => trg_csr, invert_test => 1, cond_test => true, \
            target => MCAUSE;

origin 8;
lb_1: latch_b => 1, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => lb;
lh_1: latch_b => 1, b_src => imm, jmp_type => direct, target => lh;
lw_1: latch_b => 1, b_src => imm, jmp_type => direct, target => lw;
               NOT_IMPLEMENTED;
lbu_1: latch_b => 1, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => lbu;
lhu_1: latch_b => 1, b_src => imm, jmp_type => direct, target => lhu;

lb: alu_op => add;
    latch_adr => 1;
lb_wait:  a_src => zero, b_src => dat_r, latch_a => 1, latch_b => 1, mem_req => 1, invert_test => 1, \
              cond_test => mem_valid, mem_sel => byte, mem_extend => sign, jmp_type => direct, \
              target => lb_wait;
          alu_op => add, JUMP_TO_OP_END(fast_epilog);

lh: alu_op => add;
    latch_adr => 1, except_ctl => latch_load_adr, mem_sel => hword, \
            jmp_type => direct, cond_test => exception, target => save_pc;
lh_wait:  a_src => zero, b_src => dat_r, latch_a => 1, latch_b => 1, mem_req => 1, invert_test => 1, \
              cond_test => mem_valid, mem_sel => hword, mem_extend => sign, jmp_type => direct, \
              target => lh_wait;
          alu_op => add, pc_action => inc, JUMP_TO_OP_END(fast_epilog);

lw: alu_op => add;
    latch_adr => 1, except_ctl => latch_load_adr, mem_sel => word, \
            jmp_type => direct, cond_test => exception, target => save_pc;
lw_wait:  a_src => zero, b_src => dat_r, latch_a => 1, latch_b => 1, mem_req => 1, invert_test => 1, \
              cond_test => mem_valid, mem_sel => word, jmp_type => direct, \
              target => lw_wait;
          alu_op => add, pc_action => inc, JUMP_TO_OP_END(fast_epilog);

lbu: alu_op => add;
     latch_adr => 1;
lbu_wait:  a_src => zero, b_src => dat_r, latch_a => 1, latch_b => 1, mem_req => 1, invert_test => 1, \
              cond_test => mem_valid, mem_sel => byte, jmp_type => direct, \
              target => lbu_wait;
           alu_op => add, JUMP_TO_OP_END(fast_epilog);

lhu: alu_op => add;
     latch_adr => 1, except_ctl => latch_load_adr, mem_sel => hword, \
            jmp_type => direct, cond_test => exception, target => save_pc;
lhu_wait:  a_src => zero, b_src => dat_r, latch_a => 1, latch_b => 1, mem_req => 1, invert_test => 1, \
              cond_test => mem_valid, mem_sel => hword, jmp_type => direct, \
              target => lhu_wait;
           alu_op => add, pc_action => inc, JUMP_TO_OP_END(fast_epilog);

origin 0x24;
// CSR ops take two cycles to decode. This is effectively a no-op in case
// there's an illegal CSR access or something.
csr_trampoline: READ_RS1, jmp_type => map, except_ctl => latch_decoder, \
                     cond_test => exception, target => save_pc;
csrro0_1: a_src => zero, b_src => one, latch_a => 1, latch_b => 1, pc_action => inc, \
            jmp_type => direct, target => csrro0;
csrw_1: a_src => zero, b_src => gp, latch_a => 1, latch_b => 1, pc_action => inc, \
            jmp_type => direct, target => csrwi;
csrrw_1: csr_op => read_csr, csr_sel => insn_csr, a_src => zero, latch_a => 1, \
            b_src => gp, latch_b => 1, pc_action => inc, jmp_type => direct, \
            target => csrrwi;  
csrr_1: csr_op => read_csr, csr_sel => insn_csr, a_src => zero, latch_a => 1, \
            pc_action => inc, jmp_type => direct, target => csrr;   
csrrs_1: csr_op => read_csr, csr_sel => insn_csr, a_src => zero, latch_a => 1, \
            pc_action => inc, jmp_type => direct, target => csrrs;
csrrc_1: csr_op => read_csr, csr_sel => insn_csr, a_src => zero, latch_a => 1, \
            latch_b => 1, b_src => one, pc_action => inc, jmp_type => direct, \
            target => csrrc;
csrwi_1: a_src => zero, b_src => csr_imm, latch_a => 1, latch_b => 1, pc_action => inc, \
            jmp_type => direct, target => csrwi;
csrrwi_1: csr_op => read_csr, csr_sel => insn_csr, a_src => zero, b_src => csr_imm, \
            latch_a => 1, latch_b => 1, pc_action => inc, jmp_type => direct, \
            target => csrrwi;
csrrsi_1: csr_op => read_csr, csr_sel => insn_csr, a_src => zero, latch_a => 1, \
            pc_action => inc, jmp_type => direct, target => csrrsi;
csrrci_1: csr_op => read_csr, csr_sel => insn_csr, a_src => zero, latch_a => 1, \
            latch_b => 1, b_src => one, pc_action => inc, jmp_type => direct, \
            target => csrrci;

origin 0x30;
misc_mem: pc_action => inc, jmp_type => direct, target => fetch;

csrro0: alu_op => and, JUMP_TO_OP_END(fast_epilog);
csrr:  latch_b => 1, b_src => csr;
       alu_op => add, JUMP_TO_OP_END(fast_epilog);
csrwi: alu_op => add, JUMP_TO_OP_END(fast_epilog_csr);
csrrwi: alu_op => add, latch_b => 1, b_src => csr; // Latch old CSR value, pass thru new.
        WRITE_RD_CSR, alu_op => add, JUMP_TO_OP_END(fast_epilog);

csrrsi: latch_b => 1, b_src => csr;
        alu_op => add, b_src => csr_imm, latch_b => 1;
csrrs_2: WRITE_RD, a_src => alu_o, latch_a => 1; // Feed back old CSR value.
         alu_op => or, JUMP_TO_OP_END(fast_epilog_csr);

csrrci: latch_b => 1, b_src => csr, alu_op => sub;  // Synthesize -1 on ALU_O
        // TODO: Unlike GP reads, csr_ops are not sticky. Maybe they should be?
        csr_op => read_csr, csr_sel => insn_csr, alu_op => add, a_src => alu_o, \
            b_src => csr_imm, latch_a => 1, latch_b => 1;
csrrc_2: WRITE_RD, b_src => csr, latch_b => 1, alu_op => xor; // Bit Clear = A & ~B
         a_src => alu_o, latch_a => 1;
         alu_op => and, JUMP_TO_OP_END(fast_epilog_csr);

origin 0x40;
addi_1: latch_b => 1, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => addi;
slli_1:
        // All the Shift-Immediates pass through to the Shift-Register logic;
        // the AND with 31 is harmless for SLL and SRL, and required for SRA
        // because of a hardcoded 1 in the imm12.
        READ_RS1, a_src => thirty_one, latch_a => 1, b_src => imm, \
                latch_b => 1, pc_action => inc, jmp_type => direct, \
                target => sll;
slti_1: latch_b => 1, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => slti;
sltiu_1: latch_b => 1, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => sltiu;
xori_1: latch_b => 1, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => xori;
srli_1: READ_RS1, a_src => thirty_one, latch_a => 1, b_src => imm, \
                latch_b => 1, pc_action => inc, jmp_type => direct, \
                target => srl;
ori_1: latch_b => 1, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => ori;
andi_1: latch_b => 1, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => andi;
              NOT_IMPLEMENTED;  // 0b1000  subi?
csrrs: READ_RS1, latch_b => 1, b_src => csr;
        alu_op => add, b_src => gp, latch_b => 1, jmp_type => direct, \
            target => csrrs_2;
csrrc:  READ_RS1, latch_b => 1, b_src => csr, alu_op => sub;  // Synthesize -1 on ALU_O
        csr_op => read_csr, csr_sel => insn_csr, alu_op => add, a_src => alu_o, \
            b_src => gp, latch_a => 1, latch_b => 1, jmp_type => direct, target => csrrc_2;
srai_1: READ_RS1, a_src => thirty_one, latch_a => 1, b_src => imm, \
                latch_b => 1, pc_action => inc, jmp_type => direct, \
                target => sra;

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

srl_loop:
              alu_op => sub, a_src => alu_o, latch_a => 1, WRITE_RD;
              alu_op => srl, a_src => alu_o, b_src => one, latch_a => 1, latch_b => 1, \
                  jmp_type => direct_zero, CONDTEST_ALU_NONZERO, target => srl_loop;

sra_loop:
              alu_op => sub, a_src => alu_o, latch_a => 1, WRITE_RD;
              // Then, do the shift, and bail if the shift cnt reached zero.
              alu_op => sra, a_src => alu_o, b_src => one, latch_a => 1, latch_b => 1, \
                  jmp_type => direct_zero, CONDTEST_ALU_NONZERO, target => sra_loop;

origin 0x80;
sb_1: READ_RS2, latch_b => 1, b_src => imm, pc_action => inc, jmp_type => direct, \
                target => sb;
sh_1: READ_RS2, latch_b => 1, b_src => imm, jmp_type => direct, target => sh;
sw_1: READ_RS2, latch_b => 1, b_src => imm, jmp_type => direct, target => sw;

predict_not_taken_neq:
     // Old PC still available in ALU latches. Preemptively assume branch not
     // taken and load new PC. Construct the jump target in case this was a bad
     // assumption, and pass the old PC through.
     pc_action => inc, a_src => zero, latch_a => 1, alu_op => add, \
        CONDTEST_ALU_NONZERO, jmp_type => direct_zero, \
        target => mispredict_branch_was_taken;

predict_not_taken_eq:
     // Old PC still available in ALU latches. Preemptively assume branch not
     // taken and load new PC. Construct the jump target in case this was a bad
     // assumption, and pass the old PC through.
     pc_action => inc, a_src => zero, latch_a => 1, alu_op => add, \
        CONDTEST_ALU_ZERO, jmp_type => direct_zero, \
        target => mispredict_branch_was_taken;

mispredict_branch_was_taken:
     // If branch required, preemptively assume the address is good, and load
     // the branch target into the PC. If this fails, the old PC will be
     // available to rollback and go to exception handler.
     alu_op => add, pc_action => load_alu_o, except_ctl => latch_jal, \
        jmp_type => direct_zero, cond_test => exception, \
        target => branch_exception_detected;

branch_exception_detected:
     // Old PC is available on ALU output. We have an exception. Rollback PC
     // and begin exception handler.
     pc_action => load_alu_o, cond_test => true, jmp_type => direct, \
        target => save_pc;

origin 0x88;
branch_ops:
beq_1: latch_b => 1, b_src => gp, jmp_type => direct, target => beq;
                
bne_1: latch_b => 1, b_src => gp, jmp_type => direct, target => bne;
                NOT_IMPLEMENTED;
                NOT_IMPLEMENTED;
blt_1: latch_b => 1, b_src => gp, jmp_type => direct, target => blt;
bge_1: latch_b => 1, b_src => gp, jmp_type => direct, target => bge;
bltu_1: latch_b => 1, b_src => gp, jmp_type => direct, target => bltu;
bgeu_1: latch_b => 1, b_src => gp, jmp_type => direct, target => bgeu;

beq: a_src => imm, b_src => pc, latch_a => 1, latch_b => 1, alu_op => sub, \
        jmp_type => direct, target => predict_not_taken_eq;
bne: a_src => imm, b_src => pc, latch_a => 1, latch_b => 1, alu_op => sub, \
        jmp_type => direct, target => predict_not_taken_neq;
blt: a_src => imm, b_src => pc, latch_a => 1, latch_b => 1, CMP_LT, \
        jmp_type => direct, target => predict_not_taken_neq;
bge: a_src => imm, b_src => pc, latch_a => 1, latch_b => 1, CMP_GE, \
        jmp_type => direct, target => predict_not_taken_neq;
bltu: a_src => imm, b_src => pc, latch_a => 1, latch_b => 1, alu_op => cmp_ltu, \
        jmp_type => direct, target => predict_not_taken_neq;
bgeu: a_src => imm, b_src => pc, latch_a => 1, latch_b => 1, CMP_GEU, \
        jmp_type => direct, target => predict_not_taken_neq;

origin 0x98;
jalr: b_src => imm, latch_b => 1;
jalr_shared:
      // Bring in PC and prepare to construct PC + 4. Calculate jmp target.
      latch_a => 1, latch_b => 1, a_src => four, b_src => pc, alu_op => add, \
        alu_o_mod => clear_lsb_o;
      // PC + 4 will be avail on next cycle, which fast_epilog will save into
      // RD. If we had an exception, then we have to wait until the old PC
      // is available, which is still latched in ALU B input.
      // Preemptively load PC with jmp target.
      a_src => zero, latch_a => 1, pc_action => load_alu_o, alu_op => add, \
        except_ctl => latch_jal, jmp_type => direct, cond_test => exception, \
        invert_test => 1, target => fast_epilog;
      // Exception detected. Pass the old PC through, and then reload.
      alu_op => add, jmp_type => direct, cond_test => true, \
        target => branch_exception_detected;

sb: a_src => zero, b_src => gp, latch_a => 1, latch_b => 1, alu_op => add;
    alu_op => add, latch_adr => 1;
    mem_sel => byte, latch_data => 1;
sb_wait:  mem_req => 1, invert_test => 1, cond_test => mem_valid, \
              mem_sel => byte, write_mem => 1, jmp_type => direct, target => sb_wait;
          STOP_MEMREQ_THEN_JUMP_TO_ZERO;

sh: a_src => zero, b_src => gp, latch_a => 1, latch_b => 1, alu_op => add;
    alu_op => add, latch_adr => 1, except_ctl => latch_store_adr, mem_sel => hword, \
        jmp_type => direct, cond_test => exception, target => save_pc;
    mem_sel => hword, latch_data => 1, pc_action => inc;
sh_wait:  mem_req => 1, invert_test => 1, cond_test => mem_valid, \
              mem_sel => hword, write_mem => 1, jmp_type => direct, target => sh_wait;
          STOP_MEMREQ_THEN_JUMP_TO_ZERO;

sw: a_src => zero, b_src => gp, latch_a => 1, latch_b => 1, alu_op => add;
    alu_op => add, latch_adr => 1, except_ctl => latch_store_adr, mem_sel => word, \
        jmp_type => direct, cond_test => exception, target => save_pc;
    mem_sel => word, latch_data => 1, pc_action => inc;
sw_wait:  mem_req => 1, invert_test => 1, cond_test => mem_valid, \
              mem_sel => word, write_mem => 1, jmp_type => direct, target => sw_wait;
          STOP_MEMREQ_THEN_JUMP_TO_ZERO;

origin 0xB0;
jal: a_src => imm, b_src => pc, latch_a => 1, latch_b => 1, \
        jmp_type => direct, target => jalr_shared;

fast_epilog: INSN_FETCH_EAGER_READ_RS1, WRITE_RD, SKIP_WAIT_IF_ACK;
fast_epilog_csr: INSN_FETCH_EAGER_READ_RS1, WRITE_RD_CSR, SKIP_WAIT_IF_ACK;

origin 0xc0;
add_1:        latch_b => 1, b_src => gp, pc_action => inc, jmp_type => direct, \
                    target => add;
              // Re: READ_RS1... the reg values read out of the GP file are
              // sticky, but as part of pipelining, we read out RS2's value
              // during dispatch/check_int.
              // We'll need RS1 again, so get it back.
sll_1:        READ_RS1, a_src => thirty_one, latch_a => 1, b_src => gp, \
                    latch_b => 1, pc_action => inc, jmp_type => direct, \
                    target => sll;
slt_1:        latch_b => 1, b_src => gp, pc_action => inc, jmp_type => direct, \
                    target => slt;
sltu_1:       latch_b => 1, b_src => gp, pc_action => inc, jmp_type => direct, \
                    target => sltu;
xor_1:        latch_b => 1, b_src => gp, pc_action => inc, jmp_type => direct, \
                    target => xor;
srl_1:        READ_RS1, a_src => thirty_one, latch_a => 1, b_src => gp, \
                    latch_b => 1, pc_action => inc, jmp_type => direct, \
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
sra_1:        READ_RS1, a_src => thirty_one, latch_a => 1, b_src => gp, \
                    latch_b => 1, pc_action => inc, jmp_type => direct, \
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

sll:
             // Get first input to shift it. Restrict second input
             // (shift count) from 0-31. Set up b_src for shift loop.
             a_src => gp, latch_a => 1, b_src => one, latch_b => 1, alu_op => and;
             // Do a shift, but also check if shift count was zero/
             // If so, bail. Otherwise, we're all set for the main shift loop.
             a_src => alu_o, latch_a => 1, alu_op => sll, \
                  jmp_type => direct, CONDTEST_ALU_NONZERO, target => sll_loop;
             // Whoops, was a zero shift. Pass through original RS1 and write
             // to dest!
             a_src => zero, b_src => gp, latch_a => 1, latch_b => 1;
             alu_op => add, INSN_FETCH, JUMP_TO_OP_END(fast_epilog);

srl:
             // Same comments as sll apply here.
             a_src => gp, latch_a => 1, b_src => one, latch_b => 1, alu_op => and;
             a_src => alu_o, latch_a => 1, alu_op => srl, \
                  jmp_type => direct, CONDTEST_ALU_NONZERO, target => srl_loop;
             a_src => zero, b_src => gp, latch_a => 1, latch_b => 1;
             alu_op => add, INSN_FETCH, JUMP_TO_OP_END(fast_epilog);

sra:  
             // Same comments as sll apply here.
             a_src => gp, latch_a => 1, b_src => one, latch_b => 1, alu_op => and;
             a_src => alu_o, latch_a => 1, alu_op => sra, \
                  jmp_type => direct, CONDTEST_ALU_NONZERO, target => sra_loop;
             a_src => zero, b_src => gp, latch_a => 1, latch_b => 1;
             alu_op => add, INSN_FETCH, JUMP_TO_OP_END(fast_epilog);

// Interrupt handler.
origin 0xf0;
save_pc: except_ctl => enter_int, csr_op => read_csr, csr_sel => trg_csr, \
            a_src => zero, b_src => pc, latch_a => 1, latch_b => 1, target => MTVEC;
         // Latch MTVEC, pass thru PC.
         alu_op => add, b_src => csr, latch_b => 1;
         // Read mcause_latch, write MEPC, pass thru MTVEC.
         alu_op => add, b_src => mcause_latch, latch_b => 1, csr_op => write_csr, \
            csr_sel => trg_csr, target => MEPC;
         // Write PC, pass thru mcause_latch
         alu_op => add, pc_action => load_alu_o;
         // Write MCAUSE, and start exception handler.
         INSN_FETCH, jmp_type => direct_zero, invert_test => 1, cond_test => true, \
            csr_op => write_csr, csr_sel => trg_csr, target => MCAUSE;


origin 248;
mret:    csr_op => read_csr, csr_sel => trg_csr, a_src => zero, latch_a => 1, target => MEPC;
         // Latch MEPC
         b_src => csr, latch_b => 1;
         // Pass thru MEPC
         alu_op => add;
         // Write PC
         pc_action => load_alu_o;
         except_ctl => leave_int, INSN_FETCH, jmp_type => direct, target => fetch;


origin 254;
halt: jmp_type => direct, target => halt;
origin 255;
panic: jmp_type => direct, target => panic;
