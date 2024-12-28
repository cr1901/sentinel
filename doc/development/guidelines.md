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

* `Signature` objects are not publicly exposed (except _maybe_ the top-level
  signature in `Top`). Bindings for `Signature` objects are allowed, but
  should be private/local to a `Component`.
* `Signature` objects are _always_ from the point-of-view of transfer
  initiator, _even `Signature` objects without bindings_. If a responder 
  signature is required, generate one using `Signature.flip`.
  * `Component` variable annotations for `Signature`s can use `In` and `Out`
    freely. If a `Component` contains {ref}`nested interface members <wiring-intro2>`,
    their annotations should have `Signatures` from the transfer initiator
    point-of-view, _even `Signature` objects without bindings_. If a responder
    `Member` for a nested `Signature` is required, generate one using `In`.
* All class variable annotations (`enum`s, `Component`s, `Struct`s, etc) should
  use [doc comments](https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html#doc-comments-and-docstrings)
  (`#:`). When useful for cross-referencing (_on a best-effort basis_), doc
  comments for class variables should start with a type (e.g. (`#: type: Docs go here`)).
  This is especially useful for `Components`, because Sphinx tends to fail to
  generate useful links from `In(MyType)`/`Out(MyType)` annotations by themselves.
  * Parametric `Component`s can't use class variable annotations.
  * Try to limit class variables to where they have readily-apparent benefits
    (e.g. `enum`s, `Component`s, `Struct`s, etc).
* Mild `class` nesting is allowed at your own discretion. These can either be
  private or public member class variables.
  * If I think functionality will be useful to others, nested classes are
    public (e.g. `MCause.Cause`). If I think it's purely an implementation
    detail that a user shouldn't access, the nested class is private (e.g. `Insn._CSR`).
* _Technically, all `Component`s except `Top` should be treated as "not likely
  to change but still private"._ However, I don't think the majority of objects
  in the package beginning with underscores looks nice.
  * The compromise I've been using is that "non-nested `Component`s should not
    begin with underscores".
  * I've not yet needed any private objects that _are not_ `Component` at
    top-level. But when I do, private top-level objects that _are not_
    `Component`s are probably fine.
  * The `Top` and `FormalTop` `Signatures`s are part of the public interface.
    However, `Top`'s `rvfi` `Signature` member is private.
* Prefer `Struct`, `Union`, etc over `StructLayout`, `UnionLayout`, etc.
  They are more compact than `Layout`s, can be used anywhere a `Layout` can.
* Type annotations are very much a work-in-progress (and likely out-of-date).
