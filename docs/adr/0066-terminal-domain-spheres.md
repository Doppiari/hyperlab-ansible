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
Rules out: guest dots in HOST grey, colouring the whole row with its domain,
and using a dot instead of the existing words.

Use the product inventory's existing runtime classification for both `vm list`
and `machine list`. Failed membership or runtime reads, external domains,
uncreated Machines and runtime drift stay neutral; a declared network profile,
raw GPU profile or network attachment never grants colour. `machine list` still
prints recorded intent in its existing columns, and still requires a readable
initial registry to list its records. Networks and ladder rungs use their own
names. This changes no policy, membership or lifecycle decision.
Rules out: a filled trust-coloured dot for unconfirmed Machine intent or an
identity invented by a renderer instead of the shared product inventory.

`--color=auto` requires a TTY, absence of `NO_COLOR`, and `TERM` other than
`dumb`. `always` overrides environment suppression only on a TTY. `never` and
the existing `--no-color` suppress dots and colour. The last option wins.
All modes keep pipes and JSON byte-identical to the previous output. The
absolute pipe requirement takes precedence over the usual interpretation of
`always` as permission to decorate a pipe.
Rules out: escapes or dots in a pipe even after an explicit `always`, JSON
decoration, and separate colour precedence for the legacy alias.

Read the semantic domain table directly from the selected checkout's
`tools/palette/palette.yml`, only for decorated text. Refuse missing,
unreadable, redirected, duplicate, aliased, malformed or incomplete input;
never substitute an appearance colour or a copied domain palette.
Rules out: accepting ambiguous palette input or silently falling back to an
invented identity colour when the shared palette cannot be validated.

`COLORTERM=truecolor` or `24bit` advertises RGB. Otherwise choose the nearest
fixed xterm-256 cube/grey entry by squared RGB distance, breaking ties by the
lowest index. Avoid slots 0–15, which a terminal theme can redefine.
Rules out: theme-controlled ANSI identity colours, assuming RGB without its
advertisement, and conversion choices that vary between commands.

Reset immediately after the dot so the domain colour cannot spill into the row.
Rules out: a domain tint on the existing state words or columns.

## Consequences

The core still depends only on the standard library and PyYAML. The shared
renderer owns palette validation and conversion; commands retain their row
formats. Plain list text and all JSON avoid the additional product-inventory
and palette reads; `machine list` still reads the records it prints. The global
colour policy also controls existing status tones in every command.

`tests/cli_domain_spheres_contract.py` exercises real command dispatch with
isolated provider and registry fixtures. Frozen byte digests pin the previous
pipe output and terminal row bodies. The check covers each domain, neutral
rows, option precedence, suppression, palette changes, RGB and indexed ANSI,
unsafe inputs and typed colour rejection. Component tests also pin parsing,
disabled rendering, JSON dispatch without colour and nearest-index conversion.
Failing read sentinels ensure plain list output never builds the additional
product inventory and JSON never reads the domain palette. This is software evidence;
terminal legibility and pipe behaviour on Nitro remain operator checks.
