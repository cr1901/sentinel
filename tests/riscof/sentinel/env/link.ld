OUTPUT_ARCH( "riscv" )
ENTRY(rvtest_entry_point)

SECTIONS
{
  . = 0x00000000;
  .text.init : { *(.text.init) }
  . = ALIGN(0x10);
  .tohost : { *(.tohost) }
  . = ALIGN(0x10);
  .text : { *(.text) }
  /* Unfortunately, . = ALIGN(0x10) doesn't get us much; there's an .align 12
     in arch_test.h for paged systems that essentially forces us to use at
     least 8Kb of simulated memory. */
  . = ALIGN(0x10);
  .data : { *(.data) }
  .data.string : { *(.data.string)}
  .bss : { *(.bss) }
  _end = .;
}
