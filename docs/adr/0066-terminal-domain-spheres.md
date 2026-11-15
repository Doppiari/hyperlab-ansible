# ADR 0066 - Show domain spheres in the terminal

Status: Proposed.

## Context

[ADR 0064](0064-spheres-are-machines.md) gives Machines a palette-owned sphere
and keeps their domain word visible. The terminal needs that same identity in
`vm list`, `machine list`, `net list` and `trust`, while scripts depend on the
existing bytes and columns. A text dot cannot carry the graphical component's
state drawing; the existing state words remain authoritative.

## Decision

Prefix each terminal row with a coloured `●` for a confirmed domain and a plain
`○` for external or unclassified identity, followed by one space. Never use
HOST grey for a guest. Keep every existing row body and heading unchanged.

Use the product inventory's existing runtime classification for `vm list`.
Unreadable membership, external domains and runtime drift stay neutral; a raw
GPU profile or network attachment never grants colour. `machine list` lists
intent, so its dot follows the record's declared network profile without
asserting runtime provenance. Networks and ladder rungs use their own names.
This changes no policy, membership or lifecycle decision.

`--color=auto` requires a TTY, absence of `NO_COLOR`, and `TERM` other than
`dumb`. `always` overrides environment suppression only on a TTY. `never` and
the existing `--no-color` suppress dots and colour. The last option wins.
All modes keep pipes and JSON byte-identical to the previous output. The
absolute pipe requirement takes precedence over the usual interpretation of
`always` as permission to decorate a pipe.

Read the semantic domain table directly from the selected checkout's
`tools/palette/palette.yml`, only for decorated text. Refuse missing,
unreadable, redirected, duplicate, aliased, malformed or incomplete input;
never substitute an appearance colour or a copied domain palette.
`COLORTERM=truecolor` or `24bit` advertises RGB. Otherwise choose the nearest
fixed xterm-256 cube/grey entry by squared RGB distance, breaking ties by the
lowest index. Avoid slots 0–15, which a terminal theme can redefine. Reset
immediately after the dot so the domain colour cannot spill into the row.

## Consequences

The core still depends only on the standard library and PyYAML. The shared
renderer owns palette validation and conversion; commands retain their row
formats. Plain VM text and all JSON avoid the added membership/palette reads.

`tests/cli_domain_spheres_contract.py` exercises real command dispatch with
isolated provider and registry fixtures. Frozen byte digests pin the previous
pipe output and terminal row bodies. The check covers each domain, neutral
rows, option precedence, suppression, palette changes, RGB and indexed ANSI,
unsafe inputs and typed colour rejection. Component tests also pin parsing,
disabled rendering and nearest-index conversion. This is software evidence;
terminal legibility and pipe behaviour on Nitro remain operator checks.
