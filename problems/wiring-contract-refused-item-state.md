# The wiring contract refused a sphere's Item.state

Author: [importriri](https://github.com/importriri).

Status: corrected in the contract, software-verified.

## Symptom

The bar's focus item is the first surface that draws a `MachineSphere`. It
passes the Machine's state as `state: ...`, the input ADR 0064 chose for the
component. `tests/host_quickshell_qml_wiring_contract.py` refused it:

```text
ProvenanceBadge.qml assigns ['state'] to MachineSphere, which declares no such property
```

The real shell and `tests/bar_core_focus_contract.py`, which instantiate the
component under Qt, accepted the same binding.

## Cause

The contract builds its vocabulary from the properties HyperLab components
require. `StateChip.qml` requires a property called `state`, so the word
entered the vocabulary, and any assignment of `state` to a component that
did not declare it with `property` became a wiring defect. `MachineSphere`
does not declare it: it binds Qt's own `Item.state` on its root object
(`state: ""`), as ADR 0064 decided, so that no QML `States` can change it.
The contract's own description says it says nothing about Qt's properties;
a shared word turned one of them into a HyperLab name.

## Correction

The contract lists only `MachineSphere.state` as a Qt input, following
ADR 0064, and counts it as declared only while the component binds it on
its own root. No other root binding authorizes an injected property. The
initial correction counted every root binding as declared; that was broader
than the documented input and could hide a wiring error. The explicit,
component-specific exception preserves the check that caught the C9 defect.

## Regression proof

`tests/MUTATIONS.md` ("The wiring contract and a component's root
bindings"): injecting `icons` into the sphere, deleting the sphere's root
`state: ""` and assigning `state` to `GpuBadge` each turn the contract red.
Binding `state` on `GpuBadge`'s root while injecting it from the bar also
stays red: a root binding alone grants no exception.
