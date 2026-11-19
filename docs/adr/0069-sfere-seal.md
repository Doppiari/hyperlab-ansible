# ADR 0069 - Draw Sfere as the seal of networks around the host

Status: Proposed

## Context

[ADR 0067](0067-sfere-map.md) made Sfere a static map: the host's symbol at
the centre and every Machine as a sphere in an angular sector of its domain.
On 2026-11-17 the operator chose another picture for the view that gives the
product its name, the seal: the host raised above an engraved floor, each
network a glass sphere ([ADR 0068](0068-compiled-shell-shaders.md)) on its
own place, and every network joined to the host by its own spoke, because
Machines talk only through the host. The map's sources, tab, glyph route and
contract still fit; its picture does not.

The facts the seal needs are already read: the network inventory
(`hyperlabctl --json net list`, now with each network's gateway and DHCP
range from its live libvirt definition), the Machine inventory, external
domains, GPU ownership and the GPU ladder. The frozen flow matrix
(`docs/network-flows.md`) gives the outbound rule of each forwarding mode.

## Decision

**The host.** At the centre stands the host keystone: `IsolationGlyph`
itself draws geometry B ([ADR 0056](0056-product-symbol-geometry-b.md)), so
the blades, the cut and the containment ring keep their named proportions,
and a `NetworkSphere` of character 0 (glass, silver core) fills the glyph's
core at the core's radius. The ring carries **one port per network the
network inventory lists**, at the angle of that network's spoke, and no
other. Each blade is engraved with one line of words true of every host.

**The networks.** Every listed network, in the source's order, is a
`NetworkSphere` in its `dom_<name>` palette colour and its character (clean
calm, dev swirling, services banded, dirty flickering, lab lattice). The
character table sits next to the palette lookup, keyed by network name, with
the same keys; a network outside them is neutral (`textSecondary`) and calm.
A core is **lit** when at least one managed Machine attached to the network
runs and the Machine inventory is current; otherwise it is dark. Its words
say "N machines · M running" (with "lit:" when lit), "empty" or
"isolated · sealed", and "last observed" while the inventory is stale.

**Spokes and isolation.** Each network has one spoke from its own port to
its sphere. A network whose `forward` is `isolated` has a **sealed port** (a
circle with a slash) and a **broken spoke** (two dashed ends and a seal in
the gap), and only such a network has them. A spoke is not a proof of
reachability, firewall acceptance or access to host services.

**Machines.** Each managed Machine is an electron, still, on a tilted ring
around its network's sphere: bright while running and the Machine inventory
is current, hollow otherwise, on a dashed ring when it is disposable. Past eight Machines in a network the last
ring stands for the rest as "+N". A Machine attached to no listed network
and every unmanaged domain are listed outside the seal, bottom left, with a
dashed mark, never on a ring.

**The panel.** A click or Enter selects a network; the panel under the stage
shows its name, subnet, gateway, DHCP range, mode, GPU level and the
outbound rule in words, and its Machines as the Machines view's cards
without their spheres; with the Machine inventory unreadable it says the
Machines are unknown, never that the network is empty. A second activation, `+` or "Enter <network>" enters
it: the camera centres the network at 2.1 times, at once with reduced
motion. Esc or "← The whole seal" returns. A card opens the existing Machine
pane. Selecting and entering are the only actions; no Machine operation is
reachable from the seal.

**The heartbeat.** The host's core beats once for every successful refresh
of the network inventory, the Machine inventory or GPU ownership, using
their existing observation times. When any of them is stale (older than
twice the 30-second slow poll, failed or off) the core stops and dims, and
the host's words say so: "data from 14:02 · Machine inventory not
answering"; otherwise "data current". With reduced motion it never beats;
the words still say whether the data is current.

**Atmosphere.** The seal's rings and ticks turn slowly (one turn in four
minutes), dust drifts and the host's light rays turn (one turn in three and
a half minutes), all at low contrast. This supersedes ADR 0067's rule of no
drift, and only for this atmosphere: it never carries state. Its component
takes only the seal's geometry and one clock, so no network or Machine can
make it faster, brighter or denser anywhere. It stops with reduced motion,
when the view is not shown, and when the **Ambient motion** setting is off.
The setting is `~/.config/hyperlab/ambient-motion`, read like reduced
motion: absent means on, `0` or `false` off, `1` or `true` on, anything else
or unreadable off; the System panel's row writes it.

**Frame budget.** One 33 ms timer (at most 30 frames a second) drives every
clock of the view: lit cores, the heartbeat, the atmosphere and the camera.
It runs only while the view is shown and something needs it, so with reduced
motion, the setting off and no lit core it stops. Sphere effects use
`textureScale` 0.5 while the GPU is lent to a Machine (the host then draws on
the integrated GPU) or after 30 frames in a row miss a 50 ms budget, until
the view is hidden.

**Colour and words.** No colour literal or constructor appears in the view
or its helpers: every colour is a palette entry or a theme token. Every
state is also written in words, in the labels, the cards and the accessible
names, and a hidden accessible list repeats the host's freshness line, every
network, every Machine and everything outside the seal.

ADR 0067's sectors, state orbits, 24-sphere collapse, GPU token and boot
marks leave the view. Its tab, glyph and IPC routes, shared network reader,
absence wording, Create entry and Machine navigation stay.

## Consequences

The view is `SfereView.qml` with helpers `SealFloor.qml`, `SealAmbient.qml`,
`HostKeystone.qml`, `SealSpoke.qml`, `SealNetwork.qml` and `SealPanel.qml`,
installed with the shell. `tests/sfere_view_contract.py` runs the real QML
over the real net list formatter and the role's own libvirt network template,
and checks the port set, sealing iff isolation, geometry B, palette and
character keys, lit cores, freshness words, the panel against net list,
keyboard and pointer routes, and what moves and when. It keeps five
1920x1080 captures with `--renders DIR`.

Two facts the seal would show have no source in the shell yet: the host's
name, which the mockup engraves on a blade
([`../../problems/sfere-seal-host-name-has-no-source.md`](../../problems/sfere-seal-host-name-has-no-source.md)),
and a locked session, which should stop the clock
([`../../problems/sfere-seal-clock-under-session-lock.md`](../../problems/sfere-seal-clock-under-session-lock.md)).
Electrons in motion, traffic, the GPU beam and focus come with the live
layer. The seal on the Nitro, with the GPU at home and lent, is operator
acceptance.
