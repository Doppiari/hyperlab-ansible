# ADR 0072 - Navigation-only IPC routes for documentation captures

Status: Proposed

## Context

The capture session of 2026-11-02 on the Nitro could not reach most of the
shell. The workspace IPC target opened the six destinations, but no IPC
target opened a Control Center or Diagnostics section, the Create form or a
selected Machine. No input simulation tool is installed, and none should be
needed. Captures of a running Machine needed the lifecycle playbook. The lock
screen cannot be captured while it is shown.

## Decision

Add one IPC target, `navigate`, to `ShellIpc.qml`. A fixed table gives one
route id to each section of the navigation model: every destination and
page of `ShellSurfaces` (the opt-in Networks and Nitro pages too), the
Create form, every launcher mode, the system panel and the idle desktop.
`open` takes only an id from that table. `machine` selects a Machine of the
current inventory by its exact name. `routes` lists the ids. `current`
reports the open route, transient, selection and rail, so a caller can
restore them.

The target is navigation only. It calls the coordinator's open, close and
select functions and reads its state. It holds no action object and asks the
compositor for no raise or slot. Nothing it reaches arms a confirmation,
sends the clipboard or reports an action. The Create form is shown or hidden
through the coordinator. Hiding it is refused while a creation is in
flight.

`tools/docs/capture-shell` walks these routes on a live session and takes
one `grim` capture per surface on an empty compositor slot. It puts back the
view, the selection, the rail and the slot. With `--demo`, the surfaces are
rendered from a fixture state file through the existing offscreen QML
harness. This needs no session and no bridges, and no Machine runs.

## Consequences

Any process of the operator's session could already open every destination
through IPC. Now it can also open a section, select a Machine by name or
close the workspace. That changes what is displayed, never what runs, and
the existing confirmations still guard every action. Adding a section
without a route fails `documentation_capture_contract.py`. A route that
reaches an action function fails it too.

GPU ownership has no separate page. Captures use Diagnostics "Isolation and
GPU" and the Sfere view. The shell has no do-not-disturb mode, and the
script does not change the notification daemon. The lock screen is drawn by
hyprlock or swaylock, so it has no demo render and is still photographed by
hand.
