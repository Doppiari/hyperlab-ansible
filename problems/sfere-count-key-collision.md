# A sector count shadowed a Machine named group-clean

Author: [importriri](https://github.com/importriri).

## Symptom

In a crowded Sfere map, a CLEAN sector count and an individual DEV Machine
named group-clean shared the same view identifier. Object lookup and the
readout could resolve the count when the operator focused the Machine.

## Root cause

The count used group- plus the sector as its identifier, while individual
Machines used their backend names. Both occupied one unqualified namespace.
A presentation-generated name could therefore collide with an actual Machine.

## Fix

Each entry keeps its unchanged backend identifier and a separate view key.
Machine, external and group keys have disjoint prefixes. Object names, links
and the readout use the view key. GPU ownership and Machine navigation keep
using the backend identifier; keys are never parsed to reconstruct it.

## Regression proof

The key-collision scenario in tests/sfere_view_contract.py gives the GPU to
an individual Machine named group-clean while CLEAN collapses into a count.
It checks unique control identities and the focused readout of every sphere,
as well as all the ordinary network, GPU, population and geometry checks.
Sharing the Machine namespace with the count fails count sphere key collided
with a Machine name; restoring disjoint keys passes.
