# The bar core is hidden while a guest is fullscreen

Author: [importriri](https://github.com/importriri).

Status: open, recorded only. No change addresses it yet; Nitro and Predator
acceptance of the bar core stays open.

## Symptom

The host bar's core and its focus item answer "where am I typing?" (ADR
0064): the core takes the domain colour of the Machine that owns the focused
window, grey for the host, hollow with the word **Unknown** when focus cannot
be placed. Both live on the host bar. A fullscreen window covers the bar, so
exactly while a guest viewer is fullscreen, the moment a guest could imitate
the host, the bar's answer is not on screen.

## What still holds

The fullscreen frame of
[ADR 0039](../docs/adr/0039-host-frame-around-fullscreen-guests.md) is drawn
on the overlay layer above every window. It uses the same focused-surface
provenance (`ShellState.fullscreenFrame` reads
`ShellState.focusedProvenance`), so a fullscreen guest still gets a host-drawn
ring in its domain colour, or the warning colour while the surface is
resolving, unresolved or unavailable. A fullscreen window nobody registered,
a plain host terminal included, gets the warning ring too.

## The gap

The ring is not the bar's answer:

- it carries colour only, without the Machine's name or domain as words, and
  without the sphere's shape, so under a fullscreen guest colour stands
  alone, which the bar core avoids on purpose;
- Unknown has no hollow drawing there: the ring uses the warning colour for
  every unplaced surface, a different signal from the bar's neutral hollow
  core;
- the bar's own rule that Unknown is never grey and never a domain colour is
  therefore not visible while the bar is covered.

## Not done here

The change that built the bar core (`tests/bar_core_focus_contract.py`) left
fullscreen out of scope by design. Closing the gap needs a decision on what
the overlay may draw over a fullscreen guest (words, a sphere, a hollow
state) without taking input or reserving space, which belongs with ADR 0039.
