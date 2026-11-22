# GPU handoff policy

The discrete GPU is passed to at most one guest at a time. Once a guest has
used it, the device may carry state that guest wrote. The GPU handoff policy is
the host-owned rule that decides which guest may take the device next in the
same host boot.

This document records the decision and the vocabulary around it. The
implementation lives in `roles/gpu_handoff/files/qemu` (the libvirt hook),
`roles/gpu_handoff/files/xml-preflight.py` (the prepare XML check),
`tools/gpu_handoff_policy.py` (the root-owned managed policy tool) and the
guest planners.

## The ladder

```text
clean  3
dev    2
dirty  1
lab    0
```

Each GPU-capable domain maps to one handoff profile. On the libvirt `prepare`
phase the hook compares the domain's level with the level recorded in
`/run/gpu-handoff/trust` for the current boot:

- equal or lower: the domain may take the GPU and the recorded level drops to
  its level;
- higher: refused. Only a host reboot clears the record and raises the ceiling
  again.

`/run` is a tmpfs, so the record never survives a reboot. A missing, redirected,
corrupt or duplicated policy input is a refusal, never a default.

## The state transaction

Reading the recorded level, comparing the request and committing the new level
are one transaction. libvirt may run `prepare` hooks for different domains at
the same time (a manual `virsh start`, autostart), so without serialization a
cleaner request could read a stale level and overwrite a dirtier one committed
in between.

```text
/run/gpu-handoff/            real directory, never a symlink
/run/gpu-handoff/lock        hook-owned flock(2) lock, mode 0600
/run/gpu-handoff/trust       the committed level, mode 0644
/run/gpu-handoff/trust.*     a commit in progress, never read
```

For a mapped domain the hook:

1. creates the state directory if needed and refuses one that is a symlink;
2. creates the lock privately if needed, refuses a lock that is a symlink or
   not a regular file, and waits at most 10 s for an exclusive `flock`; any
   failure to create, open or acquire it refuses the start;
3. under the lock, refuses a `trust` that is a symlink, not a regular file,
   unreadable or not a number, and refuses a request above the recorded level;
4. writes the new level to a `mktemp` file in the same directory, makes it
   `0644` (the desktop reads the level without privilege) and renames it over
   `trust`.

Any failure in step 4 exits nonzero and removes the temporary file, and the
previous `trust` stays byte-identical: a failed write can never leave a missing
or truncated level that would authorize a cleaner domain later. HUP, INT and
TERM refuse the start with status 1 at any step. Between the creation of the
temporary file and the moment the hook records it as its own, such a signal is
held and acted on right after, so the file is removed in that window too. The
kernel releases the lock when the hook exits, whether it succeeded, refused,
was interrupted or was killed. A hook killed with `SIGKILL` may leave a
`trust.*` file behind; it is never read, and the next reboot clears it.

The lock is the hook's own. The managed start's GPU and capacity locks are
directories under the guest lock root, taken by the playbook around
`virsh start`; the hook never takes them and the playbook never takes this one,
so a managed start whose hook runs inside them cannot wait on itself. The
managed locks order managed starts; this lock orders every `prepare`, managed
or not.

The ladder is monotonic per boot by design. It does not try to prove that a GPU
reset removed guest state; it assumes it did not. That is why the decision is a
ladder and not a per-guest allowlist: what matters is the worst code that has
run on the device since boot.

`services` is a network identity, not a rung. A services Machine that needs the
GPU (a local inference service, for example) requests a reviewed handoff profile
explicitly, and its Template must allow that profile.

## Where a domain's profile comes from

```text
/etc/gpu-handoff/domains          static map for checked-in fixtures
/etc/gpu-handoff/domains.d/*.conf one root-owned file per C10 Machine
```

The static map is rendered from `gpu_domain_profiles` in
`group_vars/all/networks.yml`. The managed directory is written only by
`tools/gpu_handoff_policy.py` during a privileged guest lifecycle operation.
The hook merges both surfaces and refuses duplicate domain names, symlinks,
files whose name does not match the domain they describe, and unknown profiles.

The hook never reads the user-owned Machine registry or a VM-spec. Product
intent reaches it only after the privileged tool has written the root-owned
file.

## Prepare XML and reviewed QEMU arguments

Every `prepare` passes the XML that libvirt supplies on stdin through
`/usr/bin/python3 -I /etc/gpu-handoff/xml-preflight.py`, before the hook creates
its state directory or lock or reads the rung. Missing, malformed or oversized
XML, a document type, and a missing, duplicated or mismatched domain name
refuse. This is a structural policy preflight, not a replacement for libvirt's
complete domain schema validation. Other hook phases retain their immediate
success without reading XML or policy.

A domain absent from both mapping surfaces passes without touching state only
when its XML has no PCI `<hostdev type='pci'>`, hostdev
`<interface type='hostdev'>`, or QEMU namespace extension. Elements and
attributes are parsed, independent of XML quote style, whitespace and attribute
order. The QEMU namespace is identified by its URI,
`http://libvirt.org/schemas/domain/qemu/1.0`, rather than the spelling of a
prefix. An unmapped `-device vfio-pci` extension therefore refuses even when
its namespace prefix is renamed. The domains provider still reports unmapped
PCI hostdev domains as `domains.unguarded_vfio` before a start.

A mapped domain may have no QEMU extension, or exactly the existing Looking
Glass extension in `roles/guest/templates/domain.xml.j2`: one top-level
command-line block with four arguments in this order:

1. `-device`;
2. the template's `ivshmem-plain` object, with id `shmem0` and memdev
   `looking-glass`;
3. `-object`;
4. the template's `memory-backend-file` object, with id `looking-glass`, the
   approved kvmfr path and byte size, and `share:true`.

Argument **values must match the template's literal syntax**; the helper does
not evaluate or execute their contents. Extra or duplicate blocks, arguments,
properties or environment elements, an added device, mismatched ids, path
changes and size drift refuse. A future change to that syntax requires review
and a corresponding preflight change. Rejecting every command-line block
would also reject the reference workstation's Looking Glass device.

`gpu_handoff` installs the helper and `/etc/gpu-handoff/looking-glass.json`
as root:root `0644` below root:root `0755` `/etc/gpu-handoff`, before publishing
the hook as root:root `0755`. The JSON policy derives `device` and `size_bytes`
from the shared `hyperlab_looking_glass_device` and
`hyperlab_looking_glass_shm_mb` configuration in
`group_vars/all/looking-glass.yml`; it never derives limits from incoming XML.
A missing or failed helper, or a missing, redirected, unreadable, writable by
others, wrongly owned, malformed or duplicated transport policy refuses every
prepare. Python runs isolated (`-I`), so neither `PYTHONPATH` nor the
helper's directory can supply a module. There is no runtime import from a
writable checkout and no new third-party Python dependency.

After the normal reviewed host apply, read back the installed artifacts:

```bash
cmp roles/gpu_handoff/files/qemu /etc/libvirt/hooks/qemu
cmp roles/gpu_handoff/files/xml-preflight.py /etc/gpu-handoff/xml-preflight.py
stat -c '%U:%G %a %n' /etc/gpu-handoff /etc/libvirt/hooks/qemu /etc/gpu-handoff/xml-preflight.py /etc/gpu-handoff/looking-glass.json
python -m json.tool /etc/gpu-handoff/looking-glass.json
```

Both comparisons must exit 0. The modes and owners must match those above;
the current shared 1920×1080 configuration renders `device` `/dev/kvmfr0`
and `size_bytes` `67108864`. Check configured values again after any transport
configuration change. These are installation checks, not evidence of a live
Looking Glass start or physical input isolation. The software fixtures in
`tests/arch_dev_vfio_hardware_gate_contract.py` render the real reference
domain and send it through the actual copied hook/helper; `tests/hook.bats`
and `tests/gpu_handoff_xml_contract.py` prove the refusal paths and unchanged
state bytes in temporary directories.

## Authority and limits

Membership in the host's `libvirt` group grants unrestricted system libvirt
access and **root-equivalent host authority**. The host session and this
authority are already trusted. A become password prompt records an explicit
privileged operation; it does not confine what another process in that session
can do through libvirt. This hook guards managed policy and accidental or
unreviewed starts. It does not sandbox a hostile host owner, replace libvirt
authorization, establish a GPU lease or prove GPU reset sanitization.

The prepare preflight reads only the domain XML libvirt passes on stdin. Three
routes to a PCI device stay outside it, and each needs the same libvirt
authority: the `<emulator>` binary a domain names is not inspected, so a
wrapper could add its own arguments; an `<interface type='network'>` is not
resolved to its network's forward mode, so a network that forwards in
`hostdev` mode is not seen as passthrough; and a device attached to a running
domain (`virsh attach-device`) never reaches the hook, because libvirt's qemu
hook has no phase for a hot-plug.

## The ceiling rule

A handoff profile may lower, never raise, the class that a ranked network
identity already implies:

| network_profile | allowed gpu_handoff_profile |
|-----------------|-----------------------------|
| clean           | clean, dev, dirty, lab      |
| dev             | dev, dirty, lab             |
| dirty           | dirty, lab                  |
| lab             | lab                         |
| services        | any profile its Template allows |

The Machine factory, `tools/guest_plan.py` and the root-owned policy tool each
enforce this rule. The root tool enforces it even for a plan that did not come
from the factory, because the `managed-machine` tag on a plan is a provenance
claim, not a boundary. Removing a policy skips the rule so a stale entry can
always be cleaned up. See
[`problems/managed-machine-provenance-claim.md`](../problems/managed-machine-provenance-claim.md).

## Vocabulary

| Field | Where | Meaning |
|-------|-------|---------|
| `network_profile` | Template defaults, Machine, VM-spec | network identity and host-owned provenance |
| `gpu_handoff_profile` | Template allowlist, Machine, VM-spec, libvirt metadata | requested contamination class for GPU handoff |
| `gpu_trust_profile` | provider output | handoff class observed on the root-owned policy surface |
| `gpu_policy_state` | provider output | for a product Machine: `verified`, `missing`, `mismatch`, `metadata-missing`, `unexpected`, `not-required`, or the policy-surface failure `unavailable`, `unsafe`, `collision`; for any other domain: `legacy-static` or `not-configured` |
| `device_capabilities` | Template | the device capabilities a Template offers (plural map) |
| `device_capability` | Machine | the one capability a Machine was created with |
| `device_profile` | VM-spec, guest plan, VFIO planner, root policy payload | the derived compatibility field; the Machine projection sets it from `device_capability` |

`device_profile` is kept in the derived layers on purpose. Renaming it there
would break the existing guest lifecycle without changing what it means.

## Known open work

- The managed policy surface and the unmapped-passthrough refusal have
  contract coverage. On Nitro, `dev-01`, created from `workstation-dev`, has
  its `domains.d` entry and runs with the GPU; the physical acceptance of
  that entry being matched at start, and of an unmapped passthrough domain
  being refused, is still open.
- A boot-scoped GPU lease (a GPU-capable Machine that may also start without
  the GPU) is decided in [ADR 0019](adr/0019-gpu-lease.md) and not yet
  implemented.
