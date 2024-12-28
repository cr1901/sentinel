# Development Guidelines

I've developed this coding guidelines for me over the past year (2024). It
took a long time for me to be happy with code style, and the codebase doesn't
consistently follow them yet. What's more, my guidelines are *potentially*
still in flux; I *have* changed my mind about style things like `Component`
variable annotations (forbid => allow) as I write more Amaranth. Bringing
Sentinel up to date with guidelines and/or further refining the below list is a
long term effort.

With that in mind, I've found the following coding style guidelines useful for
keeping Sentinel managable:

## Privacy

_Technically, all `Component`s except `Top` should be treated as "not likely
to change but still private"._ However, I don't think the majority of objects
in the package beginning with underscores looks nice. The compromise I've been
using is that "non-nested `Component`s should not begin with underscores".
Private top-level objects that _are not_ `Component`s are fine.

_Actual_ private classes, objects, functions, etc (begin with an underscore)
should have at least a single-line docstring, and more if Ruff complains
(e.g. a "Yields" section).

### Public API

The `Top` and `FormalTop` `Signatures`s are part of the public interface.
However, `Top`'s `rvfi` `Signature` member is private.

## Signatures

```{todo}

This section of guidelines is still in flux. The source code does not
necessarily reflect this section's guidelines.
```

`Signature` objects are not publicly exposed, except _maybe_ the top-level
signature in `Top`. Bindings for `Signature` objects are allowed, but
should be private/local to a `Component`. Despite being private, local
`Signature` objects should *not* begin with an underscore if they're shared 
between Python modules (to avoid proliferation of a bunch of attributes
beginning with underscores in public interfaces).

(sig-pov)=
`Signature` objects are _always_ from the point-of-view of transfer
initiator, _even `Signature` objects without bindings_. If a responder
signature is required, generate one using `Signature.flip`.

## Variable Annotations

### Components And Data Structures

`Component` class variable annotations _for `Signature`s_ should be used when
possible. There is no way to express "always from initiator point-of-view" in
variable annotations. However, variable annotations for `Signature`s have the
benefit of more compact class `__init__` and documentation. I use the following
rules to limit confusion over directions, and it seems to work fine:

* In contrast to the {ref}`previous paragraph <sig-pov>`, top-level
  `In` and `Out` {class}`~amaranth:amaranth.lib.wiring.Flow`s for `Component`
  variable annotations are from the point-of-view of the `Component`, even if
  `Component` is a responder (`In`) on some of its constituent interfaces.
* _However_, if a `Component` contains {ref}`nested interface members <wiring-intro2>`,
  their annotations should have `Signatures` from the transfer initiator
  point-of-view, _even `Signature` objects without bindings_. If a responder
  `Member` for a nested `Signature` is required, generate one using `In`.

Note that Parametric `Component`s can't use class variable annotations; use
an "Attributes" section in the `__init__` docstring for these `Components`.

Likewise, for prefer `Struct`, `Union`, etc over `StructLayout`, `UnionLayout`,
etc. Their variable annotations make them more compact than `Layout`s, and they
can still be used anywhere a `Layout` can.

### Class Variables

All class variable annotations (`enum`s, `Component`s, `Struct`s, etc) should
use [doc comments](https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html#doc-comments-and-docstrings)
(`#:`). Try to limit class variables to where they have readily-apparent
benefits (e.g. `enum`s, `Component` `Signatures`, `Struct`s, etc). 

When useful for cross-referencing  (_on a best-effort basis_), doc comments 
for class variables should start with a type (e.g. (`#: type: Docs go here`)).
This is especially useful for `Components`, because Sphinx tends to fail to
generate useful links from `In(MyType)`/`Out(MyType)` annotations by themselves. 

## Class Nesting

Mild `class` nesting is allowed at your own discretion. These can either be
private or public member class variables. If I think functionality will be
useful to others, nested classes/vars are public (e.g. `MCause.Cause`).
If I think it's purely an implementation detail that a user shouldn't access,
the nested class is private (e.g. `Insn._CSR` was _previously_ private).

## Type Annotations

Type annotations are very much a work-in-progress (and likely out-of-date).
