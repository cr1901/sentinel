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
  . = ALIGN(0x10);
  .data : { *(.data) }
  .data.string : { *(.data.string)}
  .bss : { *(.bss) }
  _end = .;
}
