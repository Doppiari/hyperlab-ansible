# The guest fullscreen fixture read a half-written state file

Author: [importriri](https://github.com/importriri).

Status: corrected in the test fixture; software-verified. The transaction
code was right and is unchanged.

## Symptom

Seen in CI on `main` at 61d448f, 2026-11-22, and not on the next commits:
the hyperlabctl component suite failed in
`test_synchronous_completion_orders_opposite_request` with
`concurrent_first_rc`, `concurrent_second_rc` and `terminal_rc` all
"expected 0, got 75", and then
`Unavailable: guest fullscreen receipt returned unexpected fields`.

The last message was misleading. The second transaction had not written a
bad receipt. It had correctly answered UNKNOWN
(`PREVIOUS_OPERATION_RECOVERY_REQUIRED`, blocked by the first operation),
and the test parsed that envelope as a receipt.

## Cause

The test starts the first transaction, whose fake `hyprctl dispatch` writes
`dispatch-ready` and then waits for a release. As soon as `dispatch-ready`
appears, the test sets the fake compositor's `state` to 2, so that a second,
opposite request sees a converged screen while the first call is still
outstanding.

The fake compositor reads `state` just after writing `dispatch-ready`, before
it waits. The test wrote `state` with `Path.write_text`, which truncates the
file and then writes it. When the read fell between the two, the fixture read
an empty string, `int("")` raised `ValueError`, and the fake `hyprctl` ended
with status 1. The first transaction saw an unacknowledged dispatch and, as
designed, left its operation as an UNKNOWN barrier (rc 75). The second
transaction found that barrier and refused with UNKNOWN too (rc 75).

Running the scenario in 14 parallel loops on an 8-core machine reproduced it
3 times in 336 cases, each with the CI signature. A probe at the fixture's
read recorded `ValueError("invalid literal for int() with base 10: ''")`
while the file, read again a moment later, held `2`.

## Correction

Every fixture file that another process may read while it changes is now
replaced, never rewritten in place: the test's `Guest.write`, the fake
compositor's `write` and the delayed-apply worker write a temporary file in
the same directory and `os.replace` it over the name. A reader opens either
the old file or the new one, each complete.

`_terminal` now reports the transaction's output when the exit status is
wrong, so a refusal like this one names its reason instead of failing later
in the receipt parser.

## Regression proof

`test_fixture_state_writes_replace_whole_files` opens `state` before a write
and reads that descriptor afterwards. An in-place rewrite keeps the inode, so
the old descriptor shows the new value; a replacement leaves it the complete
old one. The test makes the write three ways: through `Guest.write`, through
the real fixture argv `hyprctl dispatch ...`, and through the delayed-apply
worker. Before the correction all three failed; this check does not depend
on timing. The mutations are in `tools/hyperlabctl/MUTATIONS.md`.

After the correction, the same load (14 loops of the opposite-request case
and 4 of the same-operation case in parallel) ran 248 cases with no failure.

## Remaining timing

The second transaction keeps the production lock wait of 3 seconds. Under 16
parallel loops on the same machine, the first transaction finished no
later than 0.39 s after its release, so that bound has a wide margin; on a
much slower runner it would fail as an empty-output rc 75, not as this
symptom.
