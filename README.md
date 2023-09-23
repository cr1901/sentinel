# `sentinel`

Sentinel is a small RV32I CPU designed to fit into 1000 4-input LUTs or less
on an FPGA. It is a good candidate for control tasks where a programmable
state machine or custom size-tailored core would otherwise be used.

Unlike most RISC-V implementations, Sentinel is [microcoded](https://en.wikipedia.org/wiki/Microcode),
not pipelined. Instructions require multiple clock cycles to execute. Sentinel
is therefore not necessarily a good fit for applications where high throughput/
CPI is required.
