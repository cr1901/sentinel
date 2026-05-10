<p align="center">
  <img src="doc/White Background Ver.png" 
  alt="Sentinel Logo. A lighthouse is shining its light on a PCB and computer
  chip. The silicon die of the computer chip is visible. The text &quot;Sentinel&quot;
  in a black and gray gradient stretches in parallel with the lighthouse's beam.
  The text covers the base of the lighthouse and is below the chip.">
</p>

<p align="center">
  <strong>Logo by <a href="https://tokinokei.carrd.co/">Tokino Kei</a>.</strong>
</p>

# `sentinel`

Sentinel is a small RISC-V CPU (`RV32I_Zicsr`) written in [Amaranth](https://amaranth-lang.org/).
It implements the Machine Mode privileged spec, and is designed to fit into
~1000 4-input LUTs or less on an FPGA. It is a good candidate for control tasks
where a programmable state machine or custom size-tailored core would otherwise
be used.

Unlike most RISC-V implementations, Sentinel is [microcoded](https://en.wikipedia.org/wiki/Microcode),
not pipelined. Instructions require multiple clock cycles to execute. Sentinel
is therefore not necessarily a good fit for applications where high throughput/
IPC is required. Short version: minimum of 4 CPI for basic arithmetic,
maximum of 69 for a 31-bit shift (_yes, shift instructions need work_).

As of 5-9-2026, development has [moved](https://codeberg.org/cr1901/sentinel) to Codeberg.
Please update your remotes. _This repository is not currently mirrored._
