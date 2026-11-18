# The wiring contract refused a sphere's Item.state

Author: [importriri](https://github.com/importriri).

Status: corrected in the contract, software-verified.

## Symptom

When the bar's focus item first drew a `MachineSphere`, it passed the
Machine's state as `state: ...`, the input ADR 0064 chose for the
component. `tests/host_quickshell_qml_wiring_contract.py` refused it:

```text
ProvenanceBadge.qml assigns ['state'] to MachineSphere, which declares no such property
```

The real shell and `tests/bar_core_focus_contract.py`, which instantiated
the component under Qt, accepted the same binding.

## Cause

The contract built its vocabulary from the properties HyperLab components
required. `StateChip.qml` required a property called `state`, so the word
entered the vocabulary, and any assignment of `state` to a component that
did not declare it with `property` became a wiring defect. `MachineSphere`
does not declare it: it binds Qt's own `Item.state` on its root object
(`state: ""`), as ADR 0064 decided, and declares no QML `States`.
The original contract description excluded Qt's properties; a shared word
turned one of them into a HyperLab name.

## Correction

The first correction listed only `MachineSphere.state` as a Qt input and
counted it while the sphere bound it on its root. That component-specific
rule superseded an overly broad rule counting every root binding as a
declaration. These are historical steps, not the current inheritance rule.

[ADR 0065](../docs/adr/0065-qml-inherited-item-state.md) now recognises `state`
when the local inheritance chain ends at `Item`, `Rectangle`, `Text` or
`Canvas`. A root binding is not required, and another Item-based component
may receive the same property. QtObject-based components still cannot.
The retained `MachineSphere.state` root-input entry does not restrict or
replace this inherited-property recognition. Required injections and stray
assignments of other vocabulary names keep their existing checks.

## Regression proof

`tests/MUTATIONS.md` ("The wiring contract and inherited Item.state") keeps
the earlier red results labelled historical. A current replay accepts all
three valid Item changes: deleting the sphere's root `state: ""`, assigning
`state` to `GpuBadge`, and also binding it on `GpuBadge`'s root. Each exits 0
with `OK (56 components)`, as ADR 0065 intends.

Injecting `icons` into the sphere still exits 1 with a stray-property defect.
Assigning `state` to the QtObject-based `Icons` in `shell.qml` also exits 1.
Every saved source is restored byte-identically and the contract then passes.
The showcase contract separately checks the actual sphere and Icons
inheritance chains; runtime contracts check the state values passed to spheres.
