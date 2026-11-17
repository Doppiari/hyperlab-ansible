# A retained Create form hid the Machine selected on the map

Author: [importriri](https://github.com/importriri).

## Symptom

Opening Sfere while a Create form remained open in Machines, then selecting
a sphere, changed the selected Machine but left the Create form covering its
context pane. The navigation reported success without showing the target.

## Root cause

Machine selection belongs to ShellSurfaces; the Create subview belongs to
MachineStage. Selecting an identifier does not change the stage's creating
flag. Direct selection from the map therefore updated only half of the
navigation state.

## Fix

The map emits a Machine navigation request. WorkspaceSurface returns the
existing stage from Create before selecting the current identifier and
inventory generation. External and count requests return to the same
inventory without selecting an operational target. The separate empty-view
Create request still opens the existing form. No Machine operation is sent.

## Regression proof

`tests/sfere_view_contract.py` leaves a Create form active, navigates the map
with the keyboard, presses Enter and requires the selected context sphere
to be visible with creating false. Reintroducing creating true in the map
request handler fails Enter did not open the existing Machine pane; restoring
the handler passes.
