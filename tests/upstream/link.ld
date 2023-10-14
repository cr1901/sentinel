OUTPUT_ARCH( "riscv" )
ENTRY(_start)

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
  .bss : { *(.bss) }
  _end = .;
}

