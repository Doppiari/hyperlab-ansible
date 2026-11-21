# A reserved tick name prevented the host bar from loading

Author: [importriri](https://github.com/importriri).

## Symptom

The Sway fixture in `tests/bar_core_focus_contract.py` exited before it
could capture the bar. Qt reported that `WorkspaceSurface`, `SfereView`
and `SealAmbient` were unavailable. The last diagnostic pointed to the
`const long` declaration in the seal's tick drawing.

## Cause and fix

The QML parser in Ubuntu 26.04's Qt 6.10.2 reserves `long`. Arch's
Qt 6.11.2 accepts it as a variable name, so the local bar test passed
with the same source. The flag is now named `majorTick`. Every fifteenth
tick still extends inward by 3.5% of the seal radius and the others by 1.5%.

## Verification

On Qt 6.10.2, restoring the old name reproduced the parser error. With
`majorTick`, the bar-focus contract reached its pixel, label and geometry
checks for Sway and Hyprland at both widths.
