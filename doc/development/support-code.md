# Support Code

`sentinel-rt` is an _currently-empty_ Rust support crate. If necessary, it will
contain support routines optimized for the Sentinel RISC-V _implementation_
that LLVM or Rust wouldn't generally know about. I have three potential use
cases:

1. Wrappers over custom opcodes[^1] and the slow shift operators :),
2. Related to 1., [`compiler-builtins`](https://github.com/rust-lang/compiler-builtins)
   specialization if possible[^2].
3. Runtime/Machine Mode code that is incompatible with the existing
   [`riscv-rt`](https://github.com/rust-embedded/riscv/tree/master/riscv-rt),
   _but_ compatible with the RISC-V spec[^3].

However, at present, I don't need any special support code, so `sentinel-rt`
is just a reserved crate with example code for demo bitstreams.

```{note}
If I expand demos such that multiple linker scripts are required, the examples
_directory_ will become an examples crate. Do not depend on
`sentinel-rt/examples` being stable; the source root is _already_
a [workspace](https://doc.rust-lang.org/book/ch14-03-cargo-workspaces.html)!
```

## Footnotes

[^1]: A `memcpy` instruction is a good candidate for custom microcoded instruction
   with speedups.
[^2]: Not clear to me that this _is_ possible! Just something I thought of.
[^3]: The big one here is that RISC-V permits hardcoding `MTVEC`, but last I
      checked, this was not supported. This would likely be a size win, but
      I don't want to create a fork of `riscv-rt` just for this one edge case,
      so I deal.
