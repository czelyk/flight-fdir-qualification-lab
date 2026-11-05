/* Emulator memory map, not a board startup/linker file. */
ENTRY(arm_smoke)
MEMORY {
  CODE (rx) : ORIGIN = 0x00010000, LENGTH = 256K
  RAM (rwx) : ORIGIN = 0x20000000, LENGTH = 128K
}
SECTIONS {
  .text : { *(.text*) *(.rodata*) } > CODE
  .ARM.exidx : { *(.ARM.exidx*) } > CODE
  .data : { *(.data*) } > RAM AT > CODE
  .bss (NOLOAD) : { *(.bss*) *(COMMON) } > RAM
}
