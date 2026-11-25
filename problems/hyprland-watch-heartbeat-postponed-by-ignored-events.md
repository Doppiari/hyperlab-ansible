# Ignored Hyprland events postponed the watch heartbeat

Author: [importriri](https://github.com/importriri).

Status: corrected in source and covered by the compositor adapter behaviour
contract; software-verified. Nitro observation of the installed fix is
pending.

## Symptom

On Nitro, with Hyprland running and the shell healthy, the bar read
"Workspaces unavailable" instead of the workspace strip while the operator
worked in the windows. The strip came back by itself about 30 seconds after
mouse and keyboard went still. Hyprland answered on its sockets, the shell
had the right `HYPRLAND_INSTANCE_SIGNATURE`, `workspace-watch` was alive,
connected to `.socket2.sock` and drained by the shell, and
`workspaces-json` returned a valid snapshot in 0.05 s.

## Cause

`privatestack-compositor-adapter` re-publishes a watcher's snapshot on a
heartbeat (30 s) so a quiet stream never ages past the shell's 90-second
stale bound (`staleSeconds` in `ShellState.qml`). The Hyprland workspace
and focus loops took that heartbeat only when `read -t 30` timed out.

Both loops read every line of Hyprland's event socket and act on a short
list of event names. Any other event, such as `windowtitle`,
`activewindow` in the workspace loop, or `windowtitlev2`, published nothing
but still ended the read, and the next read started a fresh 30-second
timeout. A terminal that animates its title, a browser tab whose title
changes, or focus moving between two windows on one workspace sends such
events less than 30 seconds apart. With none of the listed events among
them, no snapshot was published at all; after 90 seconds the workspace
source was stale and the strip said it was unavailable.

The Sway loops were not affected: they publish on every event they
subscribe to. The existing contract proved the heartbeat only on a quiet
stream, never on a busy stream of ignored events.

## Correction

The Hyprland loops measure the heartbeat from the last published snapshot.
Each publication (the first one, a heartbeat, or a listed event) arms a
deadline one heartbeat away; every read waits only for the time left until
it, and when it is due the loop publishes without reading. An ignored event
neither publishes nor moves the deadline, so it costs no `hyprctl` call
and the loop never polls faster than one heartbeat. Listed events still
publish at once. The deadline uses `EPOCHREALTIME`; if the wall clock moves
back, a deadline further than one heartbeat away is pulled in to one
heartbeat, so the bound never grows. The end of the stream and the refusal
of a missing event socket are unchanged.

## Regression proof

`tests/host_compositor_adapter_behaviour_contract.py` serves a fake
`.socket2.sock` and a fake `hyprctl`. With a 3-second heartbeat and one
`windowtitle` event per second for 11 seconds, each watcher published one
snapshot before the change and four after it (at about 0, 3, 6 and 9 s).
The contract also requires every gap to stay within one heartbeat of the
next, refuses a snapshot sooner than the heartbeat when only ignored events
arrive, and keeps the quiet-stream heartbeat, the immediate publication of
a listed event, the end of the stream and the missing-socket refusal. The
mutations are in `tests/MUTATIONS.md`.

Not proved here: the installed adapter on Nitro with a title-animating
window.
