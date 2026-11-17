# A parked pointer hid the keyboard-focused Machine's identity

Author: [importriri](https://github.com/importriri).

## Symptom

After hovering a sphere, keyboard focus moved to another sphere but the
Sfere readout continued showing the hovered Machine. Moving the pointer away
made the focused Machine appear. Keyboard navigation therefore depended on
where the pointer happened to be parked.

## Root cause

Both hover and focus changes recomputed the readout with unconditional hover
priority. A valid keyboard focus could not override a still-valid hover.
Reversing that unconditional priority would instead stop a new hover from
showing another Machine while a sphere retained keyboard focus.

## Fix

A new hover or focus event selects its own sphere immediately. When either
leaves, the readout falls back to the focused sphere, then the hovered one.
The fixed readout retains the same name, domain, state and observation words.
No focus change or pointer event dispatches a Machine operation.

## Regression proof

`tests/sfere_view_contract.py` hovers dev-desk, focuses clean-desk while the
pointer stays parked, then leaves and hovers dev-desk again. Each new input
must select its own readout. Restoring unconditional hover priority fails
keyboard focus retained another sphere's hover readout; restoring the event
handling passes.
