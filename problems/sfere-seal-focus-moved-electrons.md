# A change of focus moved electrons on the seal

Author: [importriri](https://github.com/importriri).

## Symptom

On the seal, motion means a Machine is running and nothing else. Moving
focus from one Machine to another in the same network, or handing the GPU
from one to another, made both electrons jump to other rings and other
places, with nothing started or stopped.

## Root cause

The rings of a network were sorted with the GPU holder and the focused
Machine first, so that neither would be hidden behind "+N" in a crowded
network. That order was applied to every network, crowded or not. A ring's
place and tilt follow its index (`angleOf` and `tiltOf` in
`SealNetwork.qml`), so a new holder or a new focus changed indices, and the
electrons moved with them.

The contract did not see it: in its fixtures the focused Machine and the
GPU holder were the same Machine, already first by name.

## Fix

The rings keep the still seal's order, running first and then by name. The
"holder and focus first" ranking is used only to choose which Machines get
a ring when a network has more Machines than rings, and the chosen ones are
then put back in the usual order.
`tests/sfere_live_layer_contract.py` moves focus and the GPU between two
Machines of one network at a fixed time and requires every electron's
angle, tilt and drawn position to stay the same (`rings-reordered` in
`tests/MUTATIONS.md`).

## Lesson

Where an index sets a position, sorting by anything but a stable key turns a
change of that key into motion.
