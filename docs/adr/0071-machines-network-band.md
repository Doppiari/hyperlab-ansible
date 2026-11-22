# ADR 0071 - Group Machines by observed network attachment

Status: Proposed

## Context

The November 2026 Machines design moves the spheres on Machine tiles to a
band of networks above the inventory. The Machines view previously grouped
tiles by provenance. A Machine can have a reviewed profile on one network
and an interface on another, or interfaces on several networks. The seal
already associates Machines with observed interfaces. [ADR 0069](0069-sfere-seal.md)

## Decision

Use the existing opt-in network reader for Machines as well. Each row of
the validated network list gets one card. Known names follow palette order.
Other names retain source order and use the neutral tone. The displayed GPU
level describes the network's configured handoff level. GPU ownership on a
Machine card comes from its separate inventory fact.

Join the registry Machines to a network by membership in their observed
`networks` arrays. A Machine with two attachments appears once in each
corresponding group. The view's defined total still counts it once.
An empty attachment array gives a **No network** group. An unreadable
attachment gives a **Network unknown** group and makes network counts
lower bounds. Only a current observation can light a network. Only a
complete inventory can establish that it is empty.

Use a still network sphere for a confirmed running or occupied network
and an outline for a confirmed empty one. Show uncertainty in words.
Replace the Machine spheres specified by ADR 0064 for this view with a
small provenance mark, a state word and labelled facts. Keep the separate
read-only group for observed domains outside the registry.

## Consequences

Activating a network filters the inventory in place. A second activation
or Escape clears that filter. Losing the source also clears it, so an
invisible selection cannot hide Machines. Existing Machine actions and
the reviewed source of identity stay with their current owners.
