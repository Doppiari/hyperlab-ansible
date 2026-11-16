# The bar clock overlapped narrow readouts

Author: [importriri](https://github.com/importriri).

Status: corrected, software-verified.

## Symptom

At 800 logical pixels the always-visible focus item could overlap the
clock. With stale sources, the expanded GPU warning and workspace
unavailability label could also push the clock into the workspace text.

## Cause

The fallback clock centre reserved an approximate 40 pixels from the left
and derived its right bound from the right group's width. It did not account
for the clock's actual half-width or the right group's margin. The existing
focus contract rendered only at 1440 pixels, leaving the collision unseen.

## Correction

The context exposes the clock row's measured width. The bar uses the right
group's actual position and that width to place the clock between the side
groups. Below 820 pixels, right controls retain their own padding but release
their extra inter-control gaps, and the left group uses the smallest spacing.
Domain/state words and unavailable-data indications remain visible.

## Regression proof

`tests/bar_core_focus_contract.py` renders every focus fixture at both 1440
and 800 pixels under both compositors. It reads the real bounds of identity,
workspaces, clock, focus, GPU, system and settings controls and requires
containment and no pairwise overlaps. The stale case ages the other sources
too, retaining the longer unavailable readouts. Restoring the approximate
clock centre or the old narrow spacing makes the geometry contract fail;
restoring the corrected layout passes. See `tests/MUTATIONS.md`.
