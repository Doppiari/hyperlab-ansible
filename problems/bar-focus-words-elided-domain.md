# The focus item elided its domain word

Author: [importriri](https://github.com/importriri).

Status: corrected, software-verified.

## Symptom

A registered viewer could keep a domain-coloured bar core while its focus
item hid the domain word. A long Machine name and `state not confirmed`
placed the domain in the middle of the label, exactly where middle elision
removed it.

## Cause

The focus item bounded one combined name, domain and state label at 184
logical pixels. The contract checked its full `text`, which Qt retains even
when the painted run is truncated. The short fixture names did not expose
the missing visible word.

## Correction

A bounded name label elides only at its right edge. A separate label keeps
the domain and state suffix unelided; it reserves its full natural width
before the name receives any remaining space. The full Machine name remains
accessible. Inventory uncertainty still leaves the host-proven domain core
filled and explains the neutral sphere with `state not confirmed`.

## Regression proof

`tests/bar_core_focus_contract.py` adds a registered services Machine with a
31-character name. Under Sway and Hyprland it renders crashed, unlisted and
stale inventory at 1440 and 800 pixels. It checks the real domain label's
`truncated` flag, painted width and containment inside the badge, alongside
the existing core/sphere pixel and state-word assertions. Recombining the
labels with bounded middle elision turns the contract red; restoring the
split labels turns it green. See `tests/MUTATIONS.md`.
