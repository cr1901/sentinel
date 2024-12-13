# Development Guidelines

```{todo}
This whole section needs to be written/refined. As of 12/12/2024, even I don't
consistently follow my own guidelines. The general gist is:

* `Signature` objects are not publicly exposed (except _maybe_ the top-level
  signature in `Top`). Bindings for `Signature` objects are allowed, but
  should be private/local to a `Component`.
* `Signature` objects are _always_ from the point-of-view of transfer
  initiator. If a responder signature is required, generate one using
  `Signature.flip`.
  * This is not possible to enforce with `Component` variable annotations, and
    as such `Component`s with variable annotations are not allowed.
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
* Variable annotations for classes derived from `View`s in `amaranth.lib.data`
  (e.g. `Struct`, `Union`) are okay, and are not subject to direction ambiguity
  of `Component` variable annotations.
  * Prefer `Struct`, `Union`, etc over `StructLayout`, `UnionLayout`, etc.
    They are more compact than `Layout`s, can be used anywhere a `Layout` can.
* Type annotations are very much a work-in-progress (and likely out-of-date).
```
