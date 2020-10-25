space block_ram: width 32, size 256;

space block_ram;
origin 0;

fields block_ram: {
  target: width 8, origin 0, default 0;

  // cont: Increment upc by 1.
  // nop: Same as cont, but indicate we are using the target field for
  //      something else.
  // map: Use address supplied by opcode.
  // direct: Conditionally use address supplied by target field.
  // vec: Conditionally jump to vector (hardcoded).
  jmp_type: enum { cont = 0; nop = 0; map; direct; vec; }, default cont;

  // false: Unconditionally fail
  // int: Is interrupt line high?
  // exception: Illegal insn, EBRAK, ECALL, misaligned insn, misaligned ld/st?
  // mem_valid: Is current dat_r valid? Did write finish?
  // alu_ready: Is alu_ready (mainly for shifts)?
  // true: Unconditionally succeed
  cond_test: enum { false = 0; intr; exception; cmp_okay; mem_valid; alu_ready; true}, default true;

  pc_action: enum { hold = 0; inc; load_abs; load_rel; }, default hold;
  a_src: enum { gp = 0; pc; }, default gp;
  // target is for shifts.
  b_src: enum { gp = 0; imm; target; }, default gp;

  // Enum layout needs to match ALU.OpType
  alu_op: enum { add = 0; sub; and; or; xor; sll; srl; sra; cmp_eq; cmp_ne; cmp_lt; cmp_lut; cmp_ge; cmp_geu; nop }, default nop;

  reg_op: enum { none = 0; read_a_src; read_b_src; write_dst; }, default none;
  mem_req: bool, default 0;
  do_decode: bool, default 0;
};

check_int: jmp_type => vec, cond_test => intr;


// Interrupt handler.
origin 224;
// Send PC through ALU
save_pc: a_src => pc, b_src => target, jmp_type => nop, target => 0;
