# The bar geometry was measured in fallback fonts

Author: [importriri](https://github.com/importriri).

Status: corrected, software-verified.

## Symptom

CI failed at `4d141a2` on the bar core focus contract:
`sway-800/stale: rail-clock overlaps rail-workspaces on the 800-pixel rail`.
The same contract passed on a workstation with the host's fonts.

## Cause

`Tokens.qml` names Adwaita Sans for rail text and JetBrainsMono Nerd Font
for mono text and icons. The Ubuntu runner had neither, so Qt drew the rail
in DejaVu Sans and DejaVu Sans Mono. The stale 800-pixel rail holds the
longest readouts: "Workspaces unavailable", the stale GPU reading with its
last-seen boot claim, and "Unknown". In DejaVu the workspace label was about
7 pixels wider, the clock about 6 and the right group about 8. That is 21
pixels where the host's fonts leave about 2, so the clock no longer fitted
between the two groups.

The verdict followed whatever fallback the machine had. With both shell
fonts hidden from fontconfig, the contract failed with the CI diagnostic. It
passed when only Adwaita Sans remained, and also when only Noto remained.
A pass or a failure therefore said nothing about the rail the host draws.

## Correction

The contract now refuses to measure unless Qt's font database holds both
families named by `Tokens.fontSans` and `Tokens.fontMono`. A missing family
is a missing input, not a default. The CI toolchain installs Ubuntu's
`fonts-adwaita-sans` and the Nerd Fonts v3.5.1 `JetBrainsMono.tar.xz`
archive, the release Arch packages as `ttf-jetbrains-mono-nerd` 3.5.1. The
archive is checked against the SHA-256 published with the release. The step
requires `fc-match` to resolve both family names before any contract runs.
The rail layout itself is unchanged.

## Regression proof

These fontconfig files were local and are not tracked. One rejected
Adwaita Sans and JetBrainsMono Nerd Font and loaded Ubuntu's
`fonts-adwaita-sans` 49.0 and the pinned Nerd Fonts archive. Under it all
forty captures had the same item bounds as with the host's Adwaita Sans
51.0, and the contract passed. With the shell fonts hidden (DejaVu, Noto or
a mix), the contract now stops with the font refusal instead of measuring.
Naming an uninstalled family in `Tokens.qml` gives the same refusal; see
`tests/MUTATIONS.md`.

Not proved here: a hosted CI run of the new toolchain step.

The 800-pixel stale rail fits with about 2 pixels to spare in these fonts.
A wider font release would bring the overlap back, and the contract would
report it.
