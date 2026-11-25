# ADR 0039 - The host frame around a fullscreen guest window

Status: accepted (2026-10-05, option A) and built in the host shell
(`FullscreenFrame.qml`); its acceptance on Nitro is open.

## Context

Roadmap milestone 11 asks that every focused surface be named by the host,
fullscreen guests included, and that the host frame stay visible around a
Looking Glass window at all times. The resolver already names a surface the
same way whether it is fullscreen or not: it answers for the focused PID and
window. What disappears is the presentation: the host shows provenance as
the focused window's border colour and in the top rail, and a fullscreen
window covers the rail and has no border. A guest that is fullscreen can
therefore draw anything, including a fake host desktop, with nothing
host-drawn on screen to contradict it.

## Options

**A. A host-drawn ring on the overlay layer (recommended).** While the
focused surface is a guest and is fullscreen, the host shell draws a thin
ring in that guest's provenance colour around the output, on the
compositor's overlay layer, above every window, with an empty input region
so it takes no clicks. It is drawn by the host from the resolver's answer,
never by the guest, and it disappears with the fullscreen state or the
focus. It covers a few pixels of the guest's edge.

**B. No true fullscreen for guest windows.** The host fullscreen key
maximizes a guest window instead, keeping its border and the rail. Simpler,
and the frame is the usual one, but games and video lose true fullscreen
and the rail's height.

**C. Leave it.** Rejected: the roadmap asks for the frame at all times.

## Recommendation

A, with the ring's width a design token, so the frame holds in fullscreen
without changing how fullscreen behaves. The ring must be checked on Nitro
over a fullscreen Looking Glass window and over a fullscreen SPICE console.

## Implementation

The compositor adapter adds `fullscreen` to its focus snapshot: Hyprland's
`activewindow` mode 2 (`FSMODE_FULLSCREEN`; 1 is maximized, which keeps the
border and the rail) or a Sway `fullscreen_mode` of 1 or 2, and a
`fullscreen>>` event refreshes it. `ShellState.fullscreenFrame` makes the
ring visible whenever the focused window is fullscreen and the host has not
resolved it as its own: in the resolved guest's provenance colour, and in
the warning colour while it is resolving, unresolved or unavailable (fail
closed). `FullscreenFrame.qml` draws it on the overlay layer of the focused
window's output, ignoring other surfaces' exclusive zones, with no input
region; its width is the design token `fullscreenRing` (4 px).
`tests/host_quickshell_runtime_contract.py` (scenario `fullscreen-frame`)
and `tests/host_hyprland_adapter_contract.py` cover it.

## Acceptance

`tools/acceptance/12-fullscreen-ring.sh` on Nitro, with the shell that
carries `FullscreenFrame.qml` installed: the ring in dev-01's colour around
a fullscreen Looking Glass window, clicks at its edges reaching the guest,
the warning ring around a fullscreen plain terminal (see the amendment
below; until 2026-11-25 this step asked for no ring), and the ring around
dev-01's fullscreen SPICE console. `tests/acceptance_scripts_contract.py` holds the
script to those steps in that order.

## Amendment: an unregistered window is not the host (2026-11-25)

The implementation above let the resolver name any unregistered process
`HOST` (`unregistered-host-process`), and the ring skipped every window the
host had resolved as its own. A host process does not establish what its
window shows: a plain terminal can hold an ssh session to any Machine, and
virt-manager, spicy or an application nobody anticipated can show any guest.
No list of application ids can decide it. Such a window, fullscreen, drew no
ring at all.

The resolver now answers `unverified-window` (reason `unregistered-window`,
or `window-without-pid` when the compositor gives no PID) for every actual
window without a verified registration: no identity, no wallpaper or RGB.
In the `focus-trust` keyboard mode such a window, and a managed-looking
window whose PID nobody registered, gives the keyboard back the operator's
saved colours, the restore `off` uses, instead of holding the previous
window's trust colour.
Only the empty snapshot, with no PID, app id or window id, is the host
desktop. `ShellState.fullscreenFrame` draws the ring around every fullscreen
window: in the guest's colour only for a resolved guest from
`host-owned-vm-spec`, and in the warning colour for anything else, a plain
terminal included. There is no host exception left, since nothing that
can be fullscreen is the empty desktop. The shell also refuses a `HOST`
answer for a snapshot that names a process or a window.

Software-verified by the `provenance` and `fullscreen-frame` scenarios of
`tests/host_quickshell_runtime_contract.py`, fed with real resolver answers,
by `tests/surface_provenance_contract.py`, and for the keyboard by
`tests/focus_provenance_accent_contract.py`. The Nitro observation of a
fullscreen host terminal without a ring accepted the old rule and does not
accept this one: group 12 now asks for the warning ring around a fullscreen
plain terminal, and must be run again on Nitro and replayed on Predator.
