# The Sfere seal cannot engrave the host's name

Author: [importriri](https://github.com/importriri).

Status: deferred; the blades carry words true of every host
([ADR 0069](../docs/adr/0069-sfere-seal.md)).

## Symptom

The seal's design engraves the host's name on one of the keystone's blades
and repeats it under the word "Host". The shell has no source for that
name, so the seal cannot show it.

## Root cause

`ShellState.qml` reads the product identity, the status bridge, the Machine
and network inventories, GPU ownership and the trust claim. None of them
carries the host's name: `hyperlabctl` knows it (`host_hostname`, or the
system's own name) but no read the shell already runs returns it. The seal
may draw only facts from sources the shell trusts, and a name typed into the
view, or one read from a new file, would be neither.

## What the seal does instead

The left blade reads "EVERY PATH PASSES" and the right one "HOST"; the label
above the keystone says "Host" and "every path passes here". Both are true
of every host, so nothing pretends to know a name it was not given.

## To close it

Add the host's name to a read the shell already makes (the status bridge's
document is the natural place), validate it there like every other field,
and pass it to `HostKeystone.engravings` and the host's label. The Sfere
contract should then compare the engraving with the fixture's name.
