# The Machine projection guard checked an unused component

## Observation

The Machines view rendered `MachineTile`, but the presentation contract still
checked `MachineModule` for guest images, screen copies and lifecycle calls.
Adding an image or screen copy to the rendered tile escaped that guard.
The unused former component also remained in the deployment inventory.
After retargeting the guard, matching only exact Image and AnimatedImage
object names left BorderImage and IconImage blocks unguarded. The former
substring check had refused these names too.

## Cause and fix

The guard followed a component filename rather than the view's current
presentation. It now checks the tile's host-projection fields and parses QML
object types and call tokens in both the tile and dense row. Every type ending
in Image is refused, including qualified names. ScreencopyView, shutdown and
destroy remain forbidden there; the all-QML backend restrictions still apply.
The unused component is removed
from the source and both installation inventories.

## Regression proof

The cockpit contract first refused the still-deployed unused component.
Separate tile mutations adding Image, AnimatedImage and ScreencopyView blocks
or shutdown and destroy calls each fail with `machine module gained backend
behavior`. An Image in the dense row fails too. Each saved source passes after
restoration. Reintroducing the retired deployment entry fails the shared-shell
inventory contract. The mutation catalogue records these results.

BorderImage in the tile and IconImage in the dense row first passed the
exact-type guard. Both now fail with the same backend-behavior diagnostic,
as do qualified Image and IconImage blocks and a custom GuestPreviewImage
type. The direct virsh refusal is also replayed. Each contract passes after
byte-identical restoration of the saved source.
