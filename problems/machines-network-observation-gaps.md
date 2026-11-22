# Missing observations in the Machines network band

Author: [importriri](https://github.com/importriri).

## What can be missing

An unreadable libvirt definition gives unknown gateway and DHCP values.
A readable definition can explicitly have no gateway or no DHCP range.
A null forwarding mode leaves both mode and outbound policy unknown.
The network inventory can be off, loading, stale or unavailable.

A Machine with unreadable interfaces could belong to any network. Its
absence from the confirmed set cannot establish an empty network. Raw
domains can also lack memory, vCPU or attachment information. Their source
contains no reviewed image-manifest OS. The native shell previously
discarded even the allocations that the raw source did provide.

## Display

Keep absent facts unknown. Pass through positive integer allocations for
external domains. The read-only group keeps its neutral identity even when
an observed interface belongs to a product network. The earlier provenance
filter hid every external domain. With an attachment filter, that would
hide domains on the selected network. Match the raw attachment while
retaining the separate group and managed-only band counts.

An incomplete inventory shows confirmed counts as lower bounds. The band
withholds an empty outline or a dark core when occupancy or running state is
undetermined. Stale inventory withholds the core and labels the counts
unknown. The host name has a separate [source gap](sfere-seal-host-name-has-no-source.md).

## Bridge-backed interfaces

A libvirt interface can name a bridge directly. Comparing that string
with a network name hid external attachments and misplaced registered
Machines. The domain reader keeps the source type. The same network XML
map used for traffic counters supplies bridge ownership for display. An
unreadable definition or duplicate owner leaves the mapping unknown.
A matching set of product metadata can establish the observed attachment
while the existing runtime check still reports configuration drift.

## When the observed facts disagree

The disposable footer previously used the registry lifecycle even on a
configuration-drift row. A permanent runtime could therefore promise to
discard writes. Both layouts now require the inventory to confirm a
present, matching runtime before showing that promise.

Malformed shell attachment arrays also remain unknown. A valid empty
array still establishes the absence of attachments.

An unplaced stopped Machine had made the running count unknown everywhere.
The band now evaluates uncertainty about running separately from uncertainty
about the total. It also compares the reported mode with the reviewed
outbound policy. A NAT mode alone had advertised internet access on networks
with no matching policy.

The compact external layout hid the observed allocation, attachment and
read-only footer once a large inventory selected it automatically. Its two
lines now show those facts. Network polls had also replaced the focused
delegate. The band keeps a delegate for each retained network name while
its displayed facts change.

## Regression

The showcase contract exercises null interfaces, absent facts, stale reads,
a disabled reader, a multi-homed Machine and an external allocation.
[Machine showcase contract](../tests/machine_showcase_contract.py)
