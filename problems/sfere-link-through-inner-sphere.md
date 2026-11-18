# Sfere links seemed to join two Machines

Author: [importriri](https://github.com/importriri).

## Symptom

In the twelve and thirty Machine captures, a shut-off Machine's line to the
host ran under a running Machine of the same domain: clean-05, then clean-00,
then the host. The picture read as a path from one Machine to another, which
the repository never declares. The same lines struck through the inner
Machines' names.

## Root cause

Each orbit spread its own spheres evenly over the sector's angles. When a
sector had as many running Machines as shut-off ones, both orbits computed
the same fractions, so every outer sphere sat on the ray from an inner sphere
to the host. A link is a straight segment from its sphere to the emblem, so
it passed under the inner sphere and its name. Nothing in the layout looked
at the other orbit.

## Fix

A sector now has one angle per sphere, not per orbit. The running Machines
are spread evenly among those angles and the others take the rest, so no two
spheres share a ray. A link also starts outside its own Machine's name and
ends outside the host word and the host GPU token, and the emblem leaves room
under it for the host word.

## Regression proof

`tests/sfere_view_contract.py` measures every drawn link segment against
every other sphere and every visible name and requires the sphere's half
width plus a small margin. Restoring per-orbit angles fails a link passes
through another sphere in the twelve-external fixture; the current layout
passes in all fixtures, including thirty Machines and 24 in 800x600.
