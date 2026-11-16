# The focus item omitted an unsupported Machine state

Author: [importriri](https://github.com/importriri).

Status: corrected, software-verified.

## Symptom

A registered dev viewer whose Machine inventory reported `crashed` drew a
neutral sphere beside `dev-01 · dev`. The state appeared only in the
accessible name, so the visible outline had no explanation and could read
as an external or unclassified Machine.

## Cause

`ShellState.focusedMachine` keeps identity and inventory state separate.
`ProvenanceBadge.qml` passed the inventory state to `MachineSphere`, which
refuses states outside its drawing vocabulary, but displayed only the
Machine name and domain. ADR 0064 requires adopting surfaces to write the
unsupported state beside the outline. The focus fixtures exercised only
running Machines.

## Correction

The focus item uses its sphere's `knownState` to append the inventory state
when the sphere cannot draw it: `dev-01 · dev · crashed`, for example.
An unconfirmed inventory state adds `state not confirmed`. The sphere stays
neutral, and the core retains the domain proven by the host resolver.
An unresolved surface still shows `Unknown` with a hollow core. Returning
to a supported state removes the suffix, including on an inventory update
without a new focus event or provenance answer.

## Regression proof

`tests/bar_core_focus_contract.py` runs `crashed` and `unknown` inventory
fixtures through the registered viewer under Sway and Hyprland. It reads
the domain core and empty neutral sphere pixels, the unchanged sphere
state, visible state words and accessibility. It also exercises inventory
updates, recovery to running and an unconfirmed state. Removing the state
suffix or normalizing `crashed` to `running` at the badge input turns the
contract red; see `tests/MUTATIONS.md`.
