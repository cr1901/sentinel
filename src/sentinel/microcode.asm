space block_ram: width 32, size 256;

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
  // map: Use address supplied by opcode.
  // direct: Conditionally use address supplied by target field.
  // vec: Conditionally jump to vector (hardcoded).
  // direct_req: Unconditionally jump to address supplied by target field
  //             plus an offset based on the current minor opcode.
  //             See "requested_op" signal.
  jmp_type: enum { cont = 0; nop = 0; map; direct; vec; direct_req; }, default cont;

  // Various tests (valid current cycle) for conditional jumps:
  // false: Unconditionally fail
  // int: Is interrupt line high?
  // exception: Illegal insn, EBRAK, ECALL, misaligned insn, misaligned ld/st?
  // mem_valid: Is current dat_r valid? Did write finish?
  // alu_ready: Is alu_ready (mainly for shifts)?
  // true: Unconditionally succeed
  cond_test: enum { false = 0; intr; exception; cmp_okay; mem_valid; alu_ready; true}, default true;

  // Invert the results of the test above. Valid current cycle.
  invert_test: bool, default 0;

  // Modify the PC for the next cycle.
  pc_action: enum { hold = 0; inc; load_abs; load_rel; }, default hold;

  // Latch the A input into the ALU. A input contents vaid next cycle.
  a_src: enum { gp = 0; pc; }, default gp;

  // Latch the B input into the ALU. B input contents vaid next cycle.
  // Target is for shifts.
  b_src: enum { gp = 0; imm; target; }, default gp;

  // Enum layout needs to match ALU.OpType
  alu_op: enum { add = 0; sub; and; or; xor; sll; srl; sra; cmp_eq; cmp_ne; cmp_lt; cmp_lut; cmp_ge; cmp_geu; nop }, default nop;

  // Either read or write a register in the register file. _Which_ register
  // to read/write comes from the decoded insn. Read contents will be on the
  // data bus the next cycle. Written contents will be valid on the next cycle.
  // Reads are NOT transparent.
  reg_op: enum { none = 0; read_a; read_b_latch_a; latch_b; write_dst; }, default none;

  // Start or continue a memory request. For convenience, an ack will
  // automatically stop a memory request for the cycle after ack, even if
  // mem_req is enabled. Valid one cycle later.
  mem_req: bool, default 0;

  // Current mem request is insn fetch. Valid one cycle later.
  insn_fetch: bool, default 0;
};

check_int: jmp_type => vec, cond_test => intr, target => save_pc;
fetch:
wait_for_ack: insn_fetch => 1, mem_req => 1, invert_test => 1, cond_test => mem_valid, \
                  jmp_type => direct, target => wait_for_ack;
              // Illegal insn or insn misaligned exception possible
              jmp_type => vec, cond_test => exception, target => save_pc;
              reg_op => read_a, jmp_type => map;

origin 8;
imm_ops:
imm_ops_begin:
              reg_op => read_b_latch_a;
              // BUG: Assembles, but label doesn't exist! reg_op => read_b_src, b_src => imm, jmp_type => direct_req, target => addi_alu;
              reg_op => latch_b, b_src => imm, jmp_type => direct_req, target => imm_ops_alu;
imm_ops_end:
              reg_op => write_dst, pc_action => inc, cond_test => true, \
                  jmp_type => direct, target => check_int;
imm_ops_alu:
addi:
              alu_op => add, jmp_type => direct, target => imm_ops_end;
// Trampolines for multicycle ops are almost zero-cost except for microcode space.
slli_trampoline:
              alu_op => sll, jmp_type => direct, target => slli;
slli:
              // Need 3-way jump! alu_op => sll, jmp_type => direct, cond_test => alu_ready, target => imm_ops_end;
              alu_op => sll, jmp_type => direct, cond_test => alu_ready, invert_test => true, target => slli;
              alu_op => sll, jmp_type => direct, target => imm_ops_end; // Hold ALU's results by keeping alu_op the same.




// Interrupt handler.
origin 224;
// Send PC through ALU
save_pc: a_src => pc, b_src => target, jmp_type => nop, target => 0;