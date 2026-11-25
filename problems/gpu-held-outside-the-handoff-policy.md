# A GPU attached to a running domain never reaches the ladder

Author: [importriri](https://github.com/importriri).

Status: open, reported. `hyperlabctl doctor` and the shell now say when a
domain outside the GPU policy holds a passthrough device; nothing prevents
the attach, and nothing remembers it after the holder stops.

## Symptom

The qemu hook keeps the GPU's contamination ladder (clean, dev, dirty, lab)
and refuses an unmapped domain that asks for PCI passthrough. It decides at
`prepare` and exits at once for every other phase. libvirt's qemu hook has no
phase for a hot-plug, so a device given to a running domain with
`virsh attach-device` never reaches it. A domain absent from both policy
surfaces (the static `gpu_domain_profiles` and the root-owned
`/etc/gpu-handoff/domains.d`) can start without passthrough, pass the
preflight, and then receive the GPU. `/run/gpu-handoff/trust` keeps the rung
it had, which is cleaner than the GPU's real history in this boot.

## Cause

The ladder is a record of the prepares the hook saw, not an observation of
the device. Attaching a device needs the libvirt group, which is already
root-equivalent host authority ([threat model](../docs/threat-model.md)), so
the hook could never refuse it. Before this change nothing compared the
record with the domains that hold devices now: the shell showed the rung as
if it still described the GPU.

## Fix

The hook is unchanged. `observe_pci_holders` in
`tools/hyperlabctl/hyperlabctl/providers/domains.py` reads every domain's
live XML (`virsh dumpxml` without `--inactive`, so attached devices are
present; a document for another identity is unreadable) and finds each
domain that is not shut off and holds a PCI hostdev or a hostdev interface.
It compares them with the installed policy the hook reads, the static
`/etc/gpu-handoff/domains` and `domains.d`, both validated as the hook
validates them; the checkout's `gpu_domain_profiles` can differ until the
next apply. A holder in neither makes the trust section's `ladder_state`
`outside-policy`, whether or not the rung itself is readable. An unreadable
domain, domain list or surface, a domain named by both surfaces, or an
unmapped running domain with a QEMU command-line extension (whose devices the
XML cannot show) makes it `unverified`. Only `recorded` lets a renderer
believe the rung:

- `hyperlabctl doctor` reports `trust.gpu_outside_policy` (an error naming
  the domain) or `trust.gpu_holders_unverified`, and exits 2;
- `trust_claim` drops the rung; the shell's Boot claim row and rail badge
  read **Unknown, reboot to reset**, and `hyperlabctl trust` lists no
  reachable level.

## Defects in the first version

The first version of the report could still call a holder clean:

- it took the static policy from the checkout's `gpu_domain_profiles`, so
  between a checkout update and a host apply a name present only in the
  checkout cleared a holder the hook would refuse;
- a static match skipped `domains.d`, so a domain named by both surfaces (a
  collision the hook refuses) read as recorded;
- an unreadable or nonnumeric rung raised before the holders were observed,
  so the named error and the reboot instruction disappeared while the
  device was still held;
- the live XML's identity was not checked, so a reply for another domain, or
  a document that was not a domain, could clear one domain with another's
  devices;
- every QEMU-namespace element counted as a held device, so an environment
  setting earned a reboot instruction;
- `domains.unguarded_vfio` ignored `domains.d` for a non-product domain and
  advised adding the static entry that would create the collision.

Each is fixed as described above, with its own fixture and mutation.

## What is still open

The report is a reading of the moment. Once the holder stops, nothing on the
host records that it held the device, and the recorded rung reads normally
again although only a host reboot resets the GPU. A durable record needs a
root-side writer (the hook or a helper), outside the scope of this change.
A host-session actor can also detach the device before a reading.

## Regression proof

`python3 tools/hyperlabctl/tests/run.py`, module `test_gpu_holders.py`:
mapped holders (static and managed), an unmapped holder (running and
paused), a stopped unmapped definition, no holder, unreadable and malformed
live XML, a reply for another identity, an unreadable domain list, an
installed policy that differs from the checkout in both directions, unusable
or colliding installed surfaces, an unreadable or nonnumeric rung beside an
outside holder, an extension without a device, a managed-only domain in
doctor, each device shape, and the live read. `tests/host_quickshell_runtime_contract.py`
feeds the real backend payload for an unmapped holder to the shell. The
mutations are in `tools/hyperlabctl/MUTATIONS.md`, "GPU held outside the
handoff policy".
