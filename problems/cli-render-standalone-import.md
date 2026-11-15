# A palette dependency broke standalone status rendering

Found during software verification on 2026-11-15.

## What was wrong

The desktop cockpit contract loads `tools/hyperlabctl/hyperlabctl/render.py`
directly with `importlib.util.spec_from_file_location`. Its existing status
renderers have no package dependency. Adding a module-level relative import of
`ContractError` for terminal palette validation made that supported loading path
fail with `ImportError: attempted relative import with no known parent package`.
Ordinary CLI imports and the component suite's package imports still worked,
so those checks alone missed the break.

## Fix

Import the palette exception only inside the palette reader. The existing
status renderers remain independently loadable, and decorated CLI output still
uses the package's ordinary error boundary. Plain output does not load the new
palette dependency.

## Test

`test_status_renderers_still_support_loading_by_filename` in the render
component suite loads the actual file without a package and renders a plain
status document. It first failed with the same import error, then passed after
the import moved. Reintroducing a top-level relative import turns it red.
`tests/host_quickshell_desktop_cockpit_contract.py` also passes its original
direct-loading path without changing the contract.
