# The Sfere seal cannot show a Machine's address

Author: [importriri](https://github.com/importriri).

Status: deferred; the tooltip says "address unknown"
([ADR 0070](../docs/adr/0070-sfere-seal-live-layer.md)).

## Symptom

The seal's design gives each Machine's address in its tooltip, beside its
name, network, state, load and GPU. The shell has no source for it, so the
seal cannot show it.

## Root cause

The Machine inventory (`hyperlabctl machine inventory --json`) carries each
Machine's state, networks, memory and vCPUs, and now its raw CPU and
interface counters, but no address. libvirt knows a running guest's leases
(`virsh domifaddr` reads them from the network's DHCP), but no read the
shell already runs returns them, and an address typed into the view or
guessed from a subnet would be neither observed nor trusted.

## What the seal does instead

The tooltip says "address unknown" in the address's place, so nothing
pretends to know an address it was not given. Every other word in the
tooltip comes from a source the shell reads.

## To close it

Add each running Machine's leased address to the inventory's read in
`hyperlabctl` (read-only, from the network's lease source on the existing
connection, null when there is none), validate it in ShellState like every
other field, and give it to the seal's Machine words. The live layer contract
should then compare the tooltip's address with the fixture's.
