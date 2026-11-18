# QML wiring rejected the inherited Item state

## Observation

The first Machines surface using `MachineSphere` loaded successfully under
Qt, while the structural wiring contract reported that the sphere declared
no `state` property. All five new sphere bindings were rejected.

## Cause and fix

The structural checker collects required local properties into a shared
vocabulary. `StateChip` requires `state`, which makes every assignment to
that name subject to its local declaration check. The resolver followed the
local component hierarchy but stopped before recognising `Item.state`,
which the sphere intentionally uses without redeclaring it.

[ADR 0065](../docs/adr/0065-qml-inherited-item-state.md) proposes recognising
that property only for Item-based roots already used by the components.
QtObject-based components still have no such property. Required injections,
unknown assignments and root wiring keep their checks.

## Regression proof and remaining gate

The showcase contract checks both sides of the inheritance boundary using
the real component catalogue: `MachineSphere` has `state`, the QtObject-based `Icons` does not.
It failed before the resolver correction. Removing the correction fails
again, while restoring it passes. Executed Qt checks independently confirm
the sphere receives the inventory state, rather than merely accepting its
property name. This is software verification; physical acceptance of the
Machines showcase remains open.
