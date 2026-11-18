# ADR 0065 - Recognise the inherited Item state in QML wiring

Status: Proposed

## Context

The wiring contract builds its property vocabulary from required properties
of local components. `StateChip` requires `state`, so bindings to that name
are checked on every local component. `MachineSphere` deliberately uses
`Item.state` without redeclaring it (ADR 0064). Its first use in a surface
therefore produced a false wiring defect, although the real Qt engine
instantiated the sphere and applied its state correctly.

The structural contract follows local inheritance but stops at Qt types.
Treating every name in the required vocabulary as locally declared loses
this inherited Qt property. Dropping `state` from the vocabulary altogether
would also lose useful checks on components that are not Items.

## Decision

Recognise `state` as declared when the local inheritance chain ends at
`Item`, `Rectangle`, `Text` or `Canvas`. These are Item-based roots in the
existing component vocabulary. Do not recognise it on `QtObject` roots.
Keep every required-property check and every other stray-binding check.

The showcase contract resolves the real `MachineSphere` and `Icons`
inheritance chains: the former must include `state`, and the latter must
not. The executable Qt showcase independently checks the sphere's state
against the inventory, so the structural correction cannot replace runtime
verification.

## Consequences

Machine tiles, dense rows, the empty host and the selected Machine header
can bind the existing sphere state directly. No component redeclares a Qt
property to satisfy a structural checker, and no runtime API changes.
`tests/machine_showcase_contract.py` and
`tests/host_quickshell_qml_wiring_contract.py` cover the corrected boundary;
removing the inherited-property recognition must fail again.
