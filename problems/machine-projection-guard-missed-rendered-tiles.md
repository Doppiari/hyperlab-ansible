# The Machine projection guard checked an unused component

## Observation

The Machines view rendered `MachineTile`, but the presentation contract still
checked `MachineModule` for guest images, screen copies and lifecycle calls.
Adding an image or screen copy to the rendered tile escaped that guard.
The unused former component also remained in the deployment inventory.

## Cause and fix

The guard followed a component filename rather than the view's current
presentation. It now checks the tile's host-projection fields and parses QML
object blocks and call tokens in both the tile and dense row. Image,
AnimatedImage, ScreencopyView, shutdown and destroy remain forbidden there;
the all-QML backend restrictions still apply. The unused component is removed
from the source and both installation inventories.

## Regression proof

The cockpit contract first refused the still-deployed unused component.
Separate tile mutations adding Image, AnimatedImage and ScreencopyView blocks
or shutdown and destroy calls each fail with `machine module gained backend
behavior`. An Image in the dense row fails too. Each saved source passes after
restoration. Reintroducing the retired deployment entry fails the shared-shell
inventory contract. The mutation catalogue records these results.
