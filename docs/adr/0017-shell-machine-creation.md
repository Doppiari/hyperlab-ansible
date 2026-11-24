# ADR 0017 - The shell creates a Machine through the reviewed bridge and one durable operation

Status: accepted (2026-11-05, operator's decision).

The decision is recorded in the operator's private notes
(operator-observed, unpublished), in the 2026-11-05 task entry and Nitro
session step 11 at 19:24. The operator accepted the design read at `main` commit
`1e42308a863180590fc9b2a209b41227978b8a4f`. This records design acceptance
without adding hardware evidence; the implementation and its unobserved
hardware checks remain listed under "Implementation status" below.

## Context

[`../first-machine.md`](../first-machine.md) creates a Machine by hand:
`hyperlabctl machine create` and `project` without privilege, then
`vm-create.yml` and `vm-guest-inventory.yml` with `-K`, and for a
workstation the profile playbook twice, the first time with a password hash
read from a file that lives in memory and is deleted after the run.

Roadmap milestone 5 asks for the same steps from the shell's Machines
destination. The shell is presentation: it never calls a hypervisor,
`sudo` or a shell, and it names reviewed actions that something else
performs ([`../hyperlab-shell.md`](../hyperlab-shell.md)). Three things in
the manual path must not move into the shell: the privilege prompt, the
workstation password and the choice of the guest SSH key.

## Decision

Creation is split along the existing boundary.

- **Plan.** `privatestack-machine-actions create-plan` returns
  `hyperlabctl machine create-plan`: the ready Templates with what each one
  allows (lifecycle, networks, resource profiles), the resources every
  profile resolves to, the custom limits (disk at least the sealed image,
  memory at least the image floor, vCPUs at most the host's), whether the
  Template needs a password, and the guest key's fingerprint. Every value
  comes from the same factory code that creates the record; the shell only
  shows them.
- **Intent.** `privatestack-machine-actions create TEMPLATE NAME LIFECYCLE
  NETWORK PROFILE [MEMORY VCPUS DISK]` takes positional, validated values
  only. It
  runs one staged `hyperlabctl machine create --project`
  ([ADR 0053](0053-withdraw-machine-intent.md), accepted 2026-11-05), which
  refuses anything the Template forbids, writes the projected spec first and
  publishes the Machine record last under the registry lock. It answers
  with structured JSON, and the bridge launches nothing unless that answer
  names the Machine, its `vm-specs/.generated/NAME.yml` spec and the
  record's SHA-256 digest. A refusal leaves no record behind.
- **Provision.** It then launches the durable operation `machine.provision`
  through `privatestack-operation`, the runner that already owns managed
  start and shutdown. The command is never taken from the caller: the
  runner resolves it through the action registry and accepts exactly
  `["/usr/local/bin/privatestack-machine-provision", NAME]`, for a NAME
  whose spec is its own generated projection
  (`vm-specs/.generated/NAME.yml`), never a checked-in spec. It pins the
  digest of that spec's bytes in the operation record at launch and
  checks it again before it runs anything: a spec changed in between is
  a durable failure with no child started. The provisioner takes NAME
  alone and asks `hyperlabctl machine provision-steps NAME` for the
  documented steps, derived from the Machine record, its projected spec
  and its Template. `provision-steps` reads the generated spec as stored
  and refuses it unless it is exactly what the record projects to now,
  scalar types included (`true` is not `1`, `2048.0` is not `2048`): a
  missing spec, a link, an unreadable or malformed file and a spec edited
  by hand are refused alike. Before the steps, the provisioner reads the
  Machine record itself with `hyperlabctl machine show NAME`; the record's
  Template and workspace, not the plan, decide whether the steps are a
  server's or a workstation's and which profile playbook both profile
  passes run. A missing or malformed record is a refusal. The provisioner
  then holds the whole plan to the reviewed one before the first step runs
  or anything is asked: each step has its exact reviewed command (the host
  playbooks with `-K`, the profile playbook the record's Template maps to,
  `guest-close-access.yml` last), and every playbook is an existing
  regular file directly in the real `playbooks/` directory of the reviewed
  checkout, with no link anywhere on the way. Then it runs the steps in
  order inside the operation's private terminal.
- **Privilege.** Each `-K` playbook asks for the become password in that
  terminal, exactly as by hand. Nothing caches it. This prompt is an
  explicit operation step, not a boundary around host-session authority:
  membership in the host's `libvirt` group already grants unrestricted
  system libvirt access and root-equivalent host authority.
- **Password.** For a Template whose profile needs one, the provisioner asks
  for it twice without echo in the same terminal, turns it into a SHA-512
  crypt hash with `openssl passwd -6 -stdin`, writes the hash to a 0600 file
  below `$XDG_RUNTIME_DIR/hyperlab/provision/` (0700), passes the file to
  the first profile pass only and deletes it in every outcome: success, a
  failed step, Ctrl-C (SIGINT), a stopped operation unit (SIGTERM) and a
  terminal that hangs up (SIGHUP). On those signals the running playbook is
  stopped first (SIGTERM, then SIGKILL after ten seconds) and reaped; the
  file is created and removed with them held back, and only the first of
  them ends the run, so the ones that follow (a stopped runner's hangup, its
  SIGTERM, systemd's signal to the unit) cannot cut the cleanup short. A
  signal that arrives while a playbook is being started is noted and raised
  only once the provisioner holds the started process, so that playbook is
  stopped and reaped too; it is not blocked in the kernel there, so the
  playbook inherits no blocked signal. A stopped
  operation gives its command three seconds before the runner kills it,
  except `machine.provision`, which gets thirty, longer than the
  provisioner's own ten-second escalation and inside the user manager's
  default 90 s stop timeout. The password never reaches QML, an argument
  vector, a child's environment, the operation record or the transcript.
- **Key.** The guest key is the host's one HyperLab guest key,
  `~/.ssh/hyperlab_ed25519.pub`: one public ed25519 line, validated before
  use. The shell shows its fingerprint and offers no choice; the private key
  is never read.

## Consequences

- The shell gains a Create view without any new authority: everything it
  submits is re-validated by the factory, and everything privileged runs in
  the operation terminal under the operator's own become prompt. The host
  session and its libvirt authority remain trusted; the prompt does not
  confine another process in that session. The GPU hook guards managed
  policy and accidental or unreviewed starts, including QEMU argument
  extensions; it does not sandbox a hostile host owner
  ([GPU handoff policy](../gpu-handoff-policy.md)).
- A creation asks for the become password once per privileged playbook:
  twice, for `vm-create.yml` and `vm-guest-inventory.yml`. The profile
  passes of a workstation reach the guest over SSH and need no become
  password on the host.
- A failed step leaves the Machine record, the projected spec and possibly
  the domain in place, exactly as the manual path would; the operation
  record ends `failed` with the step's exit status, the operation window
  shows the step and its output, and the next step is the same documented
  command. Failed provisioning is not refused intent: the creation had
  already succeeded, so nothing is withdrawn
  ([ADR 0053](0053-withdraw-machine-intent.md) covers only refused
  creations).
- Closing the operation window is not a signal: the window only observes,
  the operation keeps running and the window can be reopened.
- Limits. The checks hold when the plan is validated and when the runner
  starts: the spec and the playbooks are read again by `ansible-playbook`
  later, and a writer of the checkout between those moments is not
  detected. The Machine record holds no digest of its projection; the
  comparison recomputes the projection every time. The table of reviewed
  profile playbooks by Template is held both in `hyperlabctl` and in the
  provisioner, which cannot import it; a contract keeps the two equal. The
  thirty seconds are a bound, not a handshake: a provisioner stuck past
  them for another reason is killed. SIGKILL (or a lost
  power) cannot be handled: the hash file then stays in the runtime
  directory, which is memory, until logout or the next provisioning of the
  same Machine replaces it. The signal handling is proven with handled
  signals against inert fixture playbooks under the real runner, with
  systemd replaced; a real unit stop and a real `ansible-playbook` are
  hardware checks.
- Template profile playbooks are a reviewed table in `hyperlabctl`. A
  workstation Template without an entry is not offered for creation.
- Disposable Machines and the GPU lease (roadmap 5 and 5b) reuse this flow
  when their Templates allow them.

## Implementation status

- Built and software-verified: the plan, the staged intent, the Create
  view in the shell (`CreateMachineView.qml`) and the provisioning runner
  with its whole-plan check and its hash-file cleanup
  (`tests/c10_machine_create_plan_contract.py`,
  `tests/host_quickshell_create_view_contract.py`,
  `tests/host_machine_provision_contract.py`). These contracts run on
  fixtures, with the limits listed above.
- Activation: on request — `host_desktop_common` in `playbooks/lab.yml`
  installs the bridge, runner, provisioner and shell files.
  `playbooks/v1-host.yml` stages the managed Hyprland and Quickshell sessions
  beside Sway without selecting a Ly default. Nothing is created until the
  operator submits a creation.
- Not proven on hardware: no Machine has been created from the shell on
  Nitro, and a real unit stop and a real `ansible-playbook` under the
  runner have not been observed.
- Of the flows that reuse this one, a disposable Machine is offered by the
  server Templates, but what it needs after its first stop is open
  ([ADR 0018](0018-disposable-discards-on-stop.md)); the GPU lease is a
  design accepted on 2026-11-05 and is not built
  ([ADR 0019](0019-gpu-lease.md)).

## Amendment (2026-11-25): a receipt for every provisioning

Status of this amendment: proposed.

A provisioning of `sid` stopped in its profile passes and the Machine still
looked ready: nothing kept the failure once the operation window was gone
([the problem](../../problems/wizard-provisioning-interrupted.md)).

- **Receipt.** Once the whole plan is validated, the provisioner takes
  `$XDG_STATE_HOME/hyperlab/provisioning/NAME.lock` (exclusive; a second run
  of the same Machine is refused) and keeps, beside it, `NAME.json` and
  `NAME.log` (0600 in a 0700 directory). The receipt names the Machine, the
  SHA-256 of its record as `machine show` read it, when the run started and
  ended, and every step's result and exit status. It is replaced atomically
  after every change. Only a run whose every step ended with 0 writes
  `finished`, in the same write as the last step's result. A failed step,
  a refusal, SIGINT, SIGTERM, SIGHUP and a closed terminal record the step
  where the run stopped; SIGKILL and a lost power leave `running`, which no
  lock then holds. The log keeps everything the steps printed (their output
  goes through a pipe; their input stays the terminal, so the become prompt
  and the password prompts never reach it) and the previous run's log.
- **Reading.** `hyperlabctl machine show` and `machine inventory` add
  `provisioning` to the Machine: `finished` only for a receipt of this
  record's digest, with its Template's steps, every one ok. A failed,
  interrupted or dead run reads "Provisioning incomplete: step N of M
  (label)" with the command that resumes it; a missing, unreadable,
  linked or foreign receipt reads "Provisioning unknown". The Machines card
  shows the same text and command for a product Machine and treats a row
  without a reading as unknown.
- **Resume.** `privatestack-machine-provision NAME --from N`, run by hand
  in the checkout, continues a failed or interrupted receipt of the same
  steps at or before its first step that did not end with 0. The runner
  still accepts only `[provisioner, NAME]`; nothing the shell submits can
  resume or skip a step.
- **Proof.** A workstation gets a last step, `hyperlabctl machine
  verify-provisioning NAME`: `sudo -n true` over the pinned SSH channel
  must be refused for a password, and for a VFIO Machine with Linux Looking
  Glass `restart-capture` then `health` must show the sender started a
  capture (stream `starting` or `streaming`) within five minutes. A server
  keeps passwordless sudo by design and gets no such step.

Consequences: a Machine provisioned before receipts existed reads
"Provisioning unknown" until a whole run finishes; commands run by hand
from [`../first-machine.md`](../first-machine.md) write no receipt. The
receipt layout is held in both programs, like the profile table, and a
contract keeps them equal. The Looking Glass proof needs an open client,
since a sender without one stops its capture; that, and the timing on real
hardware, are unobserved.

