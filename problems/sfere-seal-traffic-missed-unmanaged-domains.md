# The seal's traffic counted only product Machines

Author: [importriri](https://github.com/importriri).

## Symptom

A domain made by hand and attached to the `dev` network could move bytes
while the seal's panel said the network's traffic was "none", or gave a
lower rate. A network whose product Machines were all shut off read as a
known zero, while a network with none attached read as unknown, for the
same thing observed: no interface.

## Root cause

`hyperlabctl machine inventory --json` asked `virsh domstats` only for the
running product Machines and summed their interfaces per network, starting
every network a product Machine was attached to at zero. Other domains on
the same bridge were never read.

## Fix

The counters read `virsh domstats --raw --cpu-total --interface
--list-active` once, for every active domain, and place each interface
through its domain's definition: its source network, or the libvirt network
that owns its bridge. A network appears only with an observed interface; an
interface that cannot be placed leaves out the networks it may be on, and
every network when the domain is not a product Machine. ShellState also
treats an empty interface set as no reading. Load stays per product
Machine. The breaks are catalogued in `tools/hyperlabctl/MUTATIONS.md`
("Raw runtime counters") and `tests/MUTATIONS.md` (`empty-interfaces-quiet`).

## Lesson

A total over a shared medium has to read everything on it, or say it did
not.
