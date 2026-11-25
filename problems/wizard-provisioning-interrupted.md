# A provisioning cut off half way left a Machine that looked ready

Author: [importriri](https://github.com/importriri).

Status: corrected in source and covered by the provisioner, creation-plan
and operation integration contracts; software-verified. A real
provisioning on Nitro, its Looking Glass proof included, is pending.

## Symptom

The Machine `sid` (Template `workstation-dev`, VFIO, network `dev`) was
created from the shell's Create view on 2026-11-05. It showed in Machines
like any other running Machine. On 2026-11-23 Looking Glass did not show its
desktop: the client waited ("The host application seems to not be running")
and fell back to SPICE, which was black.

## What was observed

Read without privilege on 2026-11-23:

- Provisioning had stopped after `guest_desktop_hyprland` in the profile
  passes of `playbooks/guest-arch-dev-vfio.yml`; `close-access` never ran.
  `sudo -n true` in the guest still succeeded: cloud-init's passwordless rule
  was in place.
- `~/.config/hypr/xdph.conf` and `~/looking-glass-host.ini`, the per-user
  files of `guest_looking_glass_linux`, were missing. The root-owned picker,
  sender and kvmfr rules come from the sealed image, so they were there.
- Without `xdph.conf` the screen-cast portal ran its stock share picker on
  the invisible `HEADLESS-0`. The sender stopped after `portal_selectSource`
  and never logged `Capture Start`. SPICE was black because the desktop runs
  on the NVIDIA headless output.

## Cause

`privatestack-machine-provision` printed the failed step and returned its
status, and the operation record said `failed`, but nothing about the
Machine kept it. The operation's transcript lives in the runtime directory
and is gone after a reboot, no receipt or log was written, and the Machines
view and `hyperlabctl machine show` read only the Machine record and
libvirt. A Machine whose provisioning had finished and one cut off half way
(a failed step, a closed terminal, a reboot) looked the same. Nothing at the
end of a run checked that it had left what it should: passwordless sudo
gone, and a Looking Glass sender that captures.

## Correction

- The provisioner keeps a receipt and the whole output of every run below
  `$XDG_STATE_HOME/hyperlab/provisioning/`, bound to the record's digest
  and held under a lock. Only a run whose every step ended with 0 writes
  `finished`; a failure, a refusal, SIGINT, SIGTERM, SIGHUP or a closed
  terminal records the step it stopped at. A run killed without a word
  leaves `running` with no lock held, which reads as interrupted.
- `hyperlabctl machine show`, `machine inventory` and the Machines card read
  it: `Provisioning incomplete: step N of M (label)` with
  `privatestack-machine-provision NAME --from N`, or `Provisioning unknown`
  for a Machine without a readable receipt of its own.
- A workstation's last step, `hyperlabctl machine verify-provisioning`,
  fails while `sudo -n true` still runs in the guest and, for VFIO Linux
  Looking Glass, until the restarted sender has started a capture.

## Regression proof

`tests/host_machine_provision_contract.py` fails a step at each place a run
can fail, the last one included, signals the real provisioner on a PTY in
the middle of a step and of the last step (SIGKILL too), resumes runs with
`--from`, holds the lock from outside, reads damaged and foreign receipts,
runs the verification against a sender stopped at source selection and one
that reached `Capture Start`, and renders the card. The mutations are in
[`tests/MUTATIONS.md`](../tests/MUTATIONS.md).

## Not covered

`sid` itself keeps no receipt and reads `Provisioning unknown`; its
`close-access` is still pending, so the whole run in the checkout finishes
it. Whether a real sender logs `Capture Start` within the step's five
minutes once a client is open, and whether `restart-capture` succeeds right
after `close-access` restarted the guest agent, are Nitro checks.
