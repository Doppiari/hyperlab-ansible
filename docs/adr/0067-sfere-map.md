# ADR 0067 - Show the host and Machines on a static map

Status: Proposed

## Context

[ADR 0064](0064-spheres-are-machines.md) gives Machines their shared sphere
and reserves the grey product symbol for the host. The Machines inventory
already supplies membership and provenance; Networks supplies declared
forwarding and libvirt observations; GPU ownership and the boot claim are
separate shell observations. A system view can compose these facts without
another host reader or a new action path.

Network domains form an explicit graph, not a distance hierarchy. Services
is outside the GPU ladder. An external libvirt domain remains visible and
neutral without becoming a product Machine (ADR 0060).

## Decision

Make Sfere the first workspace destination and the bar glyph's primary
activation. Keep the existing command palette reachable by its existing
routes. The view uses geometry B in the HOST grey at its centre and one
MachineSphere per Machine, including neutral external observations.

Use angular sectors in the shell's existing provenance order, external last.
Sector widths follow their population; two tilted ellipses distinguish
running from other observed states. Every sector uses the same two radii.
Place spheres by arc length and reserve both tangential and radial clearance;
a small window scrolls instead of overlapping spheres. There is no orbit
drift: this follows the shell's existing rule against ambient loops. Reported
transitions retain MachineSphere's existing motion and reduced-motion rule.

A line connects a registry Machine to the host as network router only when
its observed attachment names a declared NAT network reported active by the
existing Networks source. An isolated, inactive, missing or unknown network
draws none. Lines do not represent firewall acceptance, access to host
services or measured reachability. External observations currently supply no
attachments to the shell, so they draw no lines. No Machine-to-Machine path
is inferred. The Networks opt-in remains authoritative: Sfere becomes a
second visible consumer of the same reader, flight generation, timeout and
30-second cadence. With the feature off, a stale answer or a failed answer,
the map states why it draws no links.

Use only current gpuOwnership for the GPU token; unknown or stale ownership
draws no token. The owner stays individually visible even when its sector
collapses. An empty owner in a known answer docks the token on the host.
Mark sectors above the retained boot claim as requiring a reboot, qualifying
a stale or failed claim as last seen. Services never becomes a ladder rung.

Above 24 Machines, collapse the largest sectors until at most 24 spheres
remain, with one count per collapsed sector plus its GPU owner if present.
A shared state or disposable lifecycle is drawn only when all counted
members share it. Mixed states use a neutral outline, the count and the
words mixed states. A count has a network line only if every member shares
the same declared active NAT attachment. The accessible list still names
every underlying Machine, its domain, observed state and marks in sector
order. Count and external activation open the existing Machines inventory;
only registry Machines enter the existing operational context pane.
Entry keys are namespaced by Machine, external or group kind, so a count
cannot shadow a Machine with a similar name. Object names, links and readouts
use these view keys; ownership and navigation retain the unchanged backend
identifier. No backend name is reconstructed from a presentation key. The
workspace returns from an open Create subview before either navigation.

The empty, readable inventory offers one Create a Machine entry into the
existing Create flow. An unavailable registry or raw observation cannot
claim an empty system. Hover and keyboard focus show identity and state;
arrows follow sector order, Enter and pointer activation share ShellControl.
A new hover or focus event selects its own fixed readout. When either leaves,
keyboard focus takes priority over a parked pointer, so neither input mode
can permanently mask the other.
No activation changes an observed state or dispatches a Machine operation.

## Consequences

The navigation contracts retain an exact route inventory. The bar now has
four openWorkspace calls: Sfere, Diagnostics, Control Center and emergency
Machines. WorkspaceSurface owns the two additional state-only routes for
map inventory and Create, and the map's selection handler; SfereView owns
one arrow-focus route. The former presentation-wide toggleLauncher marker
was specific to the old glyph action and is replaced by the Sfere entry
marker. Runtime contracts exercise the real glyph, tab and sphere signals,
including the existing rule that internal navigation must not raise the
compositor window. No arbitrary destination or action is allowed.

The shell adds presentation and visibility wiring only. No new bridge,
privileged path, configuration gate or network policy exists.
`tests/sfere_view_contract.py` runs the real QML with inert transports, using
the real net list formatter and trust provider/CLI over repository network
configuration. It checks four 1920x1080 fixture scenes, 24 Machines in a
small window, transitions with reduced motion, source failures, keyboard and
pointer routes, counts and the full accessible list. Its optional --renders
argument retains the four captures. Mutation checks cover invented links,
domain-dependent radii, tinting, literals, ownership, boot restrictions,
collapse, clearance and navigation. These are software checks; installed
Quickshell, compositor focus and the physical Nitro/Predator view remain
operator acceptance.
