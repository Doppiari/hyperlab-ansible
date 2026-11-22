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

## Regression

The showcase contract exercises null interfaces, absent facts, stale reads,
a disabled reader, a multi-homed Machine and an external allocation.
[Machine showcase contract](../tests/machine_showcase_contract.py)
