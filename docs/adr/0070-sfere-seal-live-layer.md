# ADR 0070 - Show what runs, loads, holds the GPU and has focus on the seal

Status: Proposed

## Context

[ADR 0069](0069-sfere-seal.md) drew the Sfere seal still: networks, ports,
spokes and Machines as electrons that never move. The operator's design adds
a live layer on 2026-11-17: electrons travelling their rings, a trail for
load, traffic on the spokes, a beam to the GPU's holder, a wave where focus
is and a pulse for a rule between two networks. Its demonstration data moves
electrons faster under load and shows a rule between dev and services.

Two of those facts had no source in the shell. The Machine inventory carried
each Machine's state but no CPU time, and nothing carried traffic. libvirt
exposes both read-only (`virsh domstats --cpu-total --interface`: `cpu.time`
in nanoseconds, and `net.N.name`, `net.N.rx.bytes`, `net.N.tx.bytes` per
interface). The rules between networks have one source, the frozen flow
matrix ([`../network-flows.md`](../network-flows.md)) rendered into
`roles/lab_isolation`'s ruleset, and it allows no flow between two networks.

## Decision

**Motion means running, and only that.** A running Machine's electron
travels its ring at one angular speed shared by every Machine (0.9 radians a
second); its load never changes the speed. A Machine that is not running, or
whose inventory is not current, stands still. The live layer moves only on
the seal's one 33 ms clock, while the view is shown, not with reduced motion,
and only while something live is on the seal.

**Load and traffic are rates the shell computes.** `hyperlabctl machine
inventory --json` adds a `counters` object beside its rows: each running
product Machine's `cpu_time_ns` and vCPU count, and per network the summed
`rx_bytes` and `tx_bytes` of every active domain's interfaces on it, managed
or not, with the list of those interfaces, all from one `domstats --raw
--list-active` read on the existing `qemu:///system` connection, with the
read's monotonic time. A network's traffic is all of it, so a domain made
by hand on a network counts too. Each interface is placed through its
domain's definition: its source network, or the libvirt network that owns
its bridge (`net-dumpxml`); an interface on neither carries no listed
network's bytes. An interface that cannot be placed leaves out the networks
it may be on (a product Machine's declared networks, or every network for
any other domain), and a network with no active interface is left out too,
since nothing was observed there. hyperlabctl keeps no state. ShellState keeps
the previous sample and divides: load is CPU time over elapsed time and vCPU
count (0 to 1), traffic is bytes received and sent per second. The first
sample, a counter that fell, a changed vCPU count or interface set, an
empty interface set, a gap
longer than the 90-second stale threshold, a failed read or an invalid object
give no reading, never 0. Counters sit beside the rows, so the inventory's
signature, and the confirmations that depend on it, move only with a fact.

**A trail for load, particles for traffic.** Behind a running electron with
a load reading, a tapering trail 0.4 + 1.8 x load radians long; without a
reading there is no trail, and its tooltip, card and spoken line say "load
unavailable". On a whole spoke, particles travel both ways, one more each way
for every tenfold of bytes per second (1 under 10 kB/s, up to 4 from 1 MB/s);
none at rest, none without a reading and never on a broken spoke. The panel
gives the selected network's traffic in words: a rate, "none" or "unknown".

**The GPU beam follows GPU ownership.** A dotted beam labelled "GPU" runs
from the host's core to the electron of the Machine that GPU ownership names,
with a white token beside the electron; the holder is always drawn on a ring,
never hidden behind "+N". The rings themselves stay in the order of the
still seal (running first, then by name), because a ring's place and tilt
follow its index: a change of GPU holder or of focus moves no electron. Only
in a network with more Machines than rings do the holder and the focused
Machine come first when choosing who gets one. When ownership says the host holds it, the token
sits on the host and there is no beam. When ownership is unknown, or names a
domain outside the seal, there is no beam; the words under the keystone say
"GPU holder unknown" or name the holder "outside the seal", and so does the
outside list.

**Focus follows the provenance answer.** Two widening rings surround the
network of the Machine the focused-surface provenance names (the bar's
`focusedMachine`), with a white ring round its electron; round the host when
the host has focus; none when focus is unrecognised. A window title never
places focus.

**Rules come from the ruleset's data.** ShellState declares the flows
allowed between two different networks, and the seal draws one pulse for
each whose two networks are listed: network, its port, the host, the other
port, the other network, with a caption naming the rule. The flow matrix
allows none, so the list is empty and no pulse is drawn on a real host.
`tests/sfere_live_layer_contract.py` renders the isolation ruleset, takes
for every ordered pair of guest bridges the verdict of the first forward rule
that matches it (or the chain's policy), refuses a rule it cannot read, and
holds the list equal to the pairs accepted; a fixture alone declares a rule
to show the pulse.

**Words.** Each Machine's spoken line, tooltip and card say its state, its
load or "load unavailable" while it runs, "holds the GPU" and "has focus"
where true; the host's line says who holds the GPU and whether it has focus.
No state is shown by colour or motion alone. A Machine's address has no
source in the shell, and its tooltip says "address unknown".

## Alternatives considered

- **The mockup's speed under load.** Its demonstration data moves a loaded
  electron faster. Rejected: motion would then mean two things, and a still
  electron and a slow one would be hard to tell apart. Load has its own
  mark, the trail.
- **Rates in hyperlabctl.** A stateful hyperlabctl would keep the previous
  sample between invocations in a file. Rejected: the bridge runs it as a
  one-shot command, and a state file is one more thing to trust, lock and
  clean up. The shell already keeps every observation it shows.
- **Counters inside each Machine row.** Rejected: the shell compares the
  rows to decide whether the inventory changed, and an open exact-name
  confirmation is dropped when it does. Counters move on every poll.
- **A zero for what was not read.** Rejected: a quiet network and an unread
  one would look the same. Unknown draws nothing and says "unknown".
- **Only product Machines' traffic.** Cheaper (no definitions of other
  domains), but a domain made by hand on a network would move bytes the seal
  calls "none". Rejected for the network's traffic; load stays per product
  Machine, since only those have electrons.
- **Reading the live nftables ruleset in the shell.** It would show a rule
  added by hand, but needs privilege the shell does not have. Rejected; the
  contract reads the rendered ruleset instead, and a runtime source is
  recorded as a problem.

## Consequences

The seal's helpers draw the live layer with no new file, timer or animation
type: `SealNetwork.qml` the orbits, trails, tokens, focus rings and wave,
`SealSpoke.qml` the particles, `SfereView.qml` the beam, the host's token and
wave and the pulses. `tests/sfere_live_layer_contract.py` runs the real QML
over two inventory samples per fixture and checks the shared speed, still
shut-off electrons, trails only with a load, particles only with bytes and
never on a broken spoke, pulses only for declared rules, the beam's end on
the holder's electron, the wave against the provenance answer, the rates'
refusals and the words; it keeps five 1920x1080 captures with `--renders`.

A Machine that restarts between two polls and has already used more CPU time
than before gives one low reading instead of none; the next poll is right.
Rules between networks are read from the repository's ruleset by the
contract, not by the shell at run time: a future allowed flow needs a source
the shell reads ([`../../problems/sfere-seal-rules-have-no-runtime-source.md`](../../problems/sfere-seal-rules-have-no-runtime-source.md)),
and the contract fails until it has one. Machine addresses are recorded in
[`../../problems/sfere-seal-machine-address-has-no-source.md`](../../problems/sfere-seal-machine-address-has-no-source.md).
The live layer on the Nitro, with load, a GPU handoff and focus changes, is
operator acceptance.
