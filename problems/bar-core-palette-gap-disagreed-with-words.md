# The hollow bar core disagreed with the focus words

Author: [importriri](https://github.com/importriri).

Status: corrected, software-verified.

## Symptom

With one `dom_*` key missing from the palette, the bar drew a hollow core
while its focus item still named a Machine (`dev-01 · dev`) or the host
(`Host`). The shape said Unknown but the words said the identity was known.

## Cause

`HyperLabBar.qml` required a complete domain palette before filling the
core. `ProvenanceBadge.qml` received the unmodified host-resolved answer
from `ShellState.focusedMachine`, so its words did not share that condition.
The sphere already refused incomplete palettes, leaving three signals with
different answers. The focus contract used a complete palette throughout.

## Correction

The bar derives one presentation answer from the host-resolved answer and
the palette's availability. Both the core and the focus item consume it.
If any domain colour is missing, both say Unknown, including under host
focus. Restoring the palette restores the current answer without needing a
new focus event. The resolver and its Diagnostics answer are unchanged.

The shell documentation also distinguishes the colour fade from
re-validation: every focus snapshot clears the answer while the resolver
works, including the unchanged-window heartbeat. Restoring the same colour
does not restart the fade, but the pending interval still reads Unknown.
Whether that interval is visibly distracting remains a hardware check;
retaining an old identity during it would change the fresh-answer rule.

## Regression proof

`tests/bar_core_focus_contract.py` removes each `dom_*` key under host and
Machine focus, checks both presentation signals and the accessible words
before and after a resolver answer, then restores the palette and checks
live recovery. Removing the bar's palette guard or passing the raw shell
answer to the focus item turns the contract red; see `tests/MUTATIONS.md`.
