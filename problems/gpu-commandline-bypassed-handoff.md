# QEMU arguments bypassed the unmapped GPU handoff check

Found by an architecture review of the qemu hook. This was reproduced with
temporary software fixtures; no adversarial domain was defined or started on
a host.

## What was wrong

Only unmapped domains had their XML read, and a grep looked for one spelling
of `<hostdev type='pci'>` or `<interface type='hostdev'>`. XML allows spacing
around `=`, either quote style and reordered attributes. More seriously, a
QEMU namespace command-line extension could supply `-device vfio-pci` without
any hostdev element. An unmapped domain then passed without lowering the GPU
ladder. Mapped domains never had their XML inspected by the hook.

Rejecting every QEMU extension would break the reference workstation:
`roles/guest/templates/domain.xml.j2` uses four QEMU arguments to attach
Looking Glass's IVSHMEM device and its memory backend.

## Fix

Every prepare now passes its actual stdin XML to the installed
`/etc/gpu-handoff/xml-preflight.py` before the ladder transaction. The stdlib
XML parser recognizes elements by namespace URI and attributes structurally.
Unmapped PCI hostdev, hostdev interfaces and QEMU extensions refuse. Mapped
domains allow no extension or exactly the template's four Looking Glass
argument values, including fixed device/backend ids and properties. Path and
size come from a separately installed root-owned JSON policy rendered from
the shared Looking Glass configuration. No incoming argument is evaluated or
executed. Missing or failed helper/policy input refuses; the existing atomic
state transaction is preserved.

The authority wording was also wrong by implication: a become prompt cannot
confine a session whose libvirt group membership already grants
root-equivalent host authority. The hook guards managed policy and accidental
or unreviewed starts; it does not sandbox a hostile host owner. See the
[policy](../docs/gpu-handoff-policy.md) and
[threat model](../docs/threat-model.md).

## Regression proof

`bats tests/hook.bats` includes a renamed-namespace vfio-pci bypass,
reordered/spaced PCI attributes and mapped missing/malformed XML. Every mapped
fixture now supplies representative XML, including state-failure and race
cases. Refusals preserve existing trust bytes or create no state directory.

`python tests/gpu_handoff_xml_contract.py` evaluates the actual install tasks,
renders the host policy, exercises both valid shapes and checks extra devices,
arguments, properties, blocks and environment nodes, mismatched ids and
transport drift. `python tests/arch_dev_vfio_hardware_gate_contract.py` renders
the actual reference template through the existing fixture planners and sends
it to the real copied hook/helper, including a mapped VFIO case without Looking
Glass. A blanket command-line rejection fails this positive control.

The deliberate breaks and observed red/restored-green commands are recorded
in `tests/MUTATIONS.md`, under "GPU prepare XML and reviewed QEMU arguments".
These are software checks. Installed readback, the reviewed managed Looking
Glass start and PRIMARY/input observations remain physical gates; software
attack fixtures are never live GPU starts. The GPU lease remains separate.
