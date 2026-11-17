# Machines on adjacent orbits overlapped in a small window

Author: [importriri](https://github.com/importriri).

## Symptom

The Sfere contract's 24-Machine, 800x600 fixture reported spheres overlap.
Each ellipse had enough arc length for its own spheres, but a running and a
shut-off Machine at the same angle could intersect between the two orbits.

## Root cause

Arc-length spacing constrains neighbours along one ellipse. It says nothing
about the distance between concentric ellipses. Tilting both orbits compresses
their vertical separation by the tilt ratio, while the sphere's screen-space
diameter stays unchanged. The closest radial gap occurs at the top and bottom.

## Fix

The minimum outer radius also reserves the minimum sphere envelope divided by
`tilt * (1 - innerRatio)`. The drawn sphere size is capped by that radial gap
minus control padding, as well as by the available arc length. Small windows
scroll the larger scene; domain never participates in choosing a radius.

## Regression proof

`tests/sfere_view_contract.py` checks every pair of drawn control envelopes
for intersection and every sphere's bounds, at full size and with 24 Machines
in 800x600. Removing the radial-clearance term reproduces the failure. The
restored layout passes. Physical scale and display legibility still require
operator review.

A second small-window check scrolls to the far edge before focusing each
sphere. Keeping the readout inside the scroll content hid the Machine name,
domain and state; the detail column now stays on the viewport, with its own
reserved space. The contract checks its bounds throughout focus navigation.

The scene's fit calculation uses that remaining scroll viewport height, not
the full view height. Otherwise reserving the fixed readout clipped the lower
sector labels even at 1920x1080. All four full-size fixtures now require their
whole scene to fit without scrolling; the small fixture still exercises both
scrolling and the fixed readout.
