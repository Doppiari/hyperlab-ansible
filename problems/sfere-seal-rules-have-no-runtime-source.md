# The Sfere seal reads rules between networks from no runtime source

Author: [importriri](https://github.com/importriri).

Status: deferred; the flow matrix allows no flow between networks, so the
seal draws no rule pulse ([ADR 0070](../docs/adr/0070-sfere-seal-live-layer.md)).

## Symptom

The seal's design draws a pulse from one network through the host to
another for each rule that allows traffic between them. The shell reads no
such rule at run time: `ShellState.networkRules` is an empty list written in
the source.

## Root cause

The only source of those rules is the frozen flow matrix
([`../docs/network-flows.md`](../docs/network-flows.md)), which
`roles/lab_isolation` renders into its nftables ruleset. The ruleset is
rendered from the list of guest networks alone: it drops every ordered pair
of different networks, so no data anywhere declares an allowed flow, and
nothing the shell reads (the status bridge, `net list`, the Machine
inventory) carries one. Reading the live ruleset would need privilege the
shell does not have.

## What the seal does instead

`ShellState.networkRules` is empty, and `tests/sfere_live_layer_contract.py`
renders the isolation ruleset and holds that list equal to the flows it
accepts between two guest bridges: none. The day an allowed flow is added,
the contract fails before the seal can disagree with the host. A fixture
alone declares a rule, to show what its pulse looks like.

## To close it

When a flow between networks is allowed, declare it as data the ruleset is
rendered from (one list of `from`, `to` and a name in `group_vars`), render
its accept rule from that list, publish the same list in `hyperlabctl
--json net list`, and let ShellState read it there with the network
inventory. The contract should then derive the expected list from that data
and from the rendered ruleset, and require both to agree.
