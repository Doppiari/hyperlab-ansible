# A Machine tile handled Enter twice

## Observation

Removing a Machine tile's local Enter handler unexpectedly left the keyboard
selection test green. The shared card already handled Enter, so checking
only the final selected identifier could not distinguish one activation
from two.

## Cause and fix

The tile inherits `ShellCard`. Both its additional `Keys.onPressed` handler
and the inherited handler received Enter and emitted the activation signal.
The tile now handles only arrows, leaving Enter and Space to the shared
card. The existing selection route and all Machine actions are unchanged.

## Regression proof

The showcase contract connects to the real tile activation signal and sends
a real Qt Return event. It requires exactly one activation as well as the
correct selected Machine. This failed with the duplicate handler and passed
when it was removed. Reintroducing the tile handler fails the exact-once
check; removing the shared card activation fails it too. The original green
mutation is recorded in the mutation catalogue with its cause.
