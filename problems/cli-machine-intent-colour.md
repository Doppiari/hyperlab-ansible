# Machine intent acquired a confirmed domain colour

Found during software verification on 2026-11-15.

## What was wrong

`machine list` drew its terminal dot from a registry record's `network_profile`.
That field describes requested intent, while the shell and `vm list` draw
confirmed product provenance. An uncreated Machine or one whose observed
runtime no longer matched its record therefore received a filled domain dot
in the terminal and a neutral outline in the shell. Its columns were accurate,
but its dot implied an identity the host had not confirmed.

## Fix

Use `build_product_inventory` provenance for the Machine dot too, keyed by the
record ID. Missing runtime, drift and failed additional classification reads
produce neutral outlines. The initial registry read still must succeed before
its records can be printed. Plain text and JSON retain their existing bytes
and avoid this additional inventory read.

## Test

`tests/cli_domain_spheres_contract.py` first failed on the drifting `sample-5`
row's filled DEV dot. It now requires a neutral outline there, for missing or
unreadable runtime, and when the extra membership read fails after the initial
record listing. Restoring network-profile colouring turns the contract red.

Failing call sentinels also forbid additional inventory reads on pipes,
suppressed terminals and JSON. Calling inventory unconditionally fails even
when its result would leave the output bytes unchanged. A CLI component test
requires the dispatch colour flag to be false for JSON on a TTY with `always`.
