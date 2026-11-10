# ADR 0062 - Plan the Sfere namespace and Doppiari release transition

Status: Proposed.

## Context

The public product is Sfere by Doppiari. Its shared display value does not
rename the interfaces used by installed hosts. ADR 0059 inventories the
unfinished visible surfaces; ADR 0061 binds resident presentation to deployed
code. Changing a shell directory without its IPC callers, unit graph and
refresh observer identities would break an existing session.

The three repositories still declare MIT at their roots. The operator chose
GPL-3.0-or-later for future versions on 2026-11-09. Five author identities,
listed in the decision packet, are confirmed by the operator; the other two
repositories use subsets of those five. Confirmation of commit identities
does not resolve third-party origins. The source audit still records four
GPL-2.0-or-later patches without a complete GPL copy and 105 images without
provenance. The evidence repository has its own unresolved derivations.

Doppiari already exists as the operator's GitHub organisation. Repository
transfer, final internal spellings, compatibility lifetime and the licence
switch date require the operator's decisions. No implementation or transfer
is authorized by this record's Proposed status.

## Candidate names

These are candidates for approval, not installed interfaces.

| Surface today | Candidate | Compatibility proposal |
| --- | --- | --- |
| `hyperlabctl` | `sfere` | Retain `hyperlabctl` as a forwarding executable; proposed minimum: one release, with duration still open. |
| `tools/hyperlabctl/`, Python `hyperlabctl` | Keep initially | Command spelling can change without moving the checkout-bound implementation. |
| Quickshell `hyperlab`, `hyperlab-workspace` | `sfere`, `sfere-workspace` | Change config roots, `qs -c` argv and IPC callers together; never run two shells as aliases. |
| `hyperlab-*.service`, session targets and desktop entries | Corresponding `sfere-*` names | One coherent unit graph and Ly catalogue; preserve Sway recovery and logout semantics. |
| `/etc/hyperlabctl/checkout` | Keep initially; `/etc/sfere/checkout` is a later candidate | One authoritative regular pointer; never choose silently between two pointers. |
| Presentation helpers `privatestack-*`, `hyperlab-*` | Corresponding `sfere-*` names | Exact forwarding executables where needed; security-sensitive helpers need separate units and checks. |
| `importriri/hyperlab-ansible` | `Doppiari/sfere` | Transfer the existing repository with its history; update callers explicitly. |
| `importriri/arch-bootstrap` | `Doppiari/sfere-bootstrap` | Same; preserve the stage-1 storage interface. |
| `importriri/arch-hypervisor-lab` | `Doppiari/sfere-lab` | Same; preserve old evidence and commit identities. |
| Palette filenames and pool IDs such as `hyperlab-trust-v2` | New `sfere-*` spellings only for approved, cleared assets | Keep historical IDs and digest-bound records; a name change supplies no rights. |

## Proposed migration policy

### Preserve durable state and storage authority

Retain `/var/lib/libvirt/images/hyperlab`, its backing chains, disks,
cloud-init media, NVRAM, TPM, receipts and state. Retain the user Machine
registry at `$XDG_STATE_HOME/hyperlab/machines` (normally
`~/.local/state/hyperlab/machines`), its records and locking namespace. Do not
move, copy, recreate or adopt Machines as part of a product rename.

Also retain existing policy, secrets and durable settings below
`/etc/privatestack`, `/var/lib/privatestack`, `/etc/hyperlab`, the user's
`~/.config/hyperlab*` directories and other existing state roots. Boot assets,
UKI signing keys, vault configuration, hardware profiles, GPU trust state,
network and domain metadata are not cosmetic names. Keep their identifiers
until a separately reviewed migration proves ownership, rollback and every
consumer. No recursive ownership/mode change, remount, disk conversion,
firmware enrollment or credential rewrite belongs to this transition.

ADR 0013 remains the cross-repository boundary: stage 1 writes
`/etc/privatestack/bootstrap-storage.yml`, schema 1, after observing the
mounted topology; stage 2 validates that declaration before image-store
writes. Keep that exact path and schema on fresh and existing installs.
Repository or CLI renaming does not justify a second contract, a fallback
path, or weaker checks of mapper, mountpoint, filesystem root and NOCOW.
A later path/schema change requires producer/consumer overlap fixtures and
a separate decision. Immutable evidence continues to name its original
repositories and frozen commits.

### Migrate presentation as one checked deployment

The CLI remains attached to one reviewed checkout, with its roles,
`group_vars`, specs and tests. Both command spellings must dispatch to that
same implementation, preserve argv and exit status, and use the same locks.
An alias must neither create an alternative configuration authority nor load
cosmetic identity before emergency command dispatch (ADR 0059).

Preflight every destination and consumer before changing installed names.
Refuse foreign, ambiguous or redirected destinations and conflicting old/new
installations. The first namespace cutover requires no active managed
graphical session or operation: if busy, refuse before namespace writes.
Running workloads remain untouched. Stage the complete config and helper
set, then publish matching unit definitions, target wants links, polkit
drop-in and Ly catalogue. Switch discovery only after validation. Do not
restart a compositor, start a display manager or select a new default.

Update the resident refresh contract's unit, cgroup, application and exact
observer argv identities with the files it observes. Preserve its busy-child
refusal, generation checks, literal checkout-path handling, check-mode
silence and unchanged second-apply behavior. IPC target/function semantics
stay fixed; only the approved config selector changes. The installed
Hyprland and Sway recovery sessions must remain selectable without duplicate
catalogue entries. Package units keep their upstream names.

One successful maintenance apply must leave a complete new graph. A failed
cutover restores the previous managed presentation files and discovery
settings from the preflight snapshot, with failure reported. Reapplying
changes nothing. Reversal restores that snapshot without moving workload
state; merely applying an older checkout is insufficient because it may
leave new units, wants links and catalogue entries behind. Active-session
cutover is deferred until it has its own proof.

### Compatibility is specific, not a symlink exception

Prefer small regular forwarding executables for public commands. Do not add
symlink aliases beneath the image store, Machine registry, policy inputs,
checkout pointer, product identity or theme manifests. Their existing
readers refuse redirected inputs. Retained state paths are canonical paths,
not aliases with a removal deadline.

Systemd wants links are the existing, explicit exception: each link must
point to its reviewed unit in the same staged graph. They do not authorize
arbitrary filesystem redirects. No whole-directory symlink and no second
Quickshell config alias is proposed. Retiring a command alias requires the
approved lifetime, consumer scan and a separately checked removal.

## Licence execution

The GPL-3.0-or-later decision is settled; the switch date is open. Dedicated
units after approval carry it out in one repository each. Recheck every
shortlog identity against the confirmed list immediately before each
unit; only a newly encountered identity adds an authorship-confirmation
dependency. Existing MIT releases and history retain their terms.

Replace root licence declarations only for material whose rights permit the
switch. Carry the full GPLv3 text, an explicit version-3-or-later grant and
accurate README/author notices. Preserve third-party copyright and licence
headers, the complete GPLv2 text for the existing GPL-2.0-or-later patches,
MIT palette notices and the separately licensed Arch installer profile.
Inspect actual SPDX declarations; do not invent package metadata for the
checkout-only CLI. Refresh the per-file origin records without rewriting
their historical audit snapshots.

Treat each unresolved image and borrowed example as unknown, not as
operator-owned merely because a confirmed identity committed it. Mark
exceptions explicitly; the root switch cannot clear their rights or admit
them to a release. Replace, remove from the distributable tree, or obtain
documented rights in separate units before claiming publication clearance.
Keep those units independent of the date-controlled first-party licence
switch. Fonts and external programs retain their own terms; fetching them
later does not bundle them into this source repository. Source publication,
installation and ISO redistribution have separate obligations. ISO and
hardware gates stay open.

## Repository transfer and final guard

The operator transfers the existing three repositories to the existing
Doppiari organisation and applies the chosen names. Preserve commit objects
and history; do not recreate repositories by copying current files. Verify
permissions and target-name availability first. Complete the transfers and
chosen repository renames before landing repository-reference updates in
CI, ISO fetch inputs or guides. Earlier implementation units retain the
current resolvable repository references. Check settings, redirects and
existing CI callers after each transfer; stop on failure. Once all targets
exist, update references in one repository at a time and require its checks
before proceeding. Do not rely on redirects for action references or hosted
project sites. Do not reuse the old repository locations.

Update the real cross-repository checkout paths and required comparisons,
including `.github/workflows/ci.yml`, the bootstrap workflow and its storage
comparison, `tests/cross_repo_contract.py`, release inputs and newcomer
guides. Private integration references and local remotes need their own
inventory at execution time; no uninspected external path is assumed.

The last implementation unit adds a tracked-path and text guard for old
product names and all three former repository names across the repositories.
Give each permitted occurrence an
exact path, context, reason and retention rule: durable compatibility,
public alias, immutable history, or an exact guard pattern/negative fixture.
Validate exception-manifest names as typed metadata, not arbitrary prose;
do not exempt the manifest or guard source wholesale. Never exempt an entire
docs, tests or ADR tree. Parse structured inputs and argv to distinguish
preserved policy identifiers from obsolete callers. Refuse missing, duplicate, redirected,
stale or overly broad exception records. Planned mutations inject old
command/config/unit/CI references, new old-named paths, unexpected history
text, missing and duplicate exceptions and a forbidden state symlink;
all must fail their relevant checks, while approved history and preserved
state remain positive controls. These are planned checks, not built code.

## Rejected alternatives

- Global text/path replacement: breaks state authority, backing references,
  evidence and third-party notices.
- Rename durable roots through compatibility symlinks: conflicts with
  existing refusal rules and creates ambiguous policy inputs.
- Two CLI implementations or two running shell configs: splits locks,
  checkout policy, IPC and resident observers.
- Active-session cutover without a migration protocol: can strand logout,
  recovery and in-progress operations between two unit graphs.
- Recreate repositories under new names: loses platform continuity and
  obscures immutable evidence.
- Treat the root GPL switch as asset or ISO clearance: commit identity and
  a root licence do not supply third-party rights.
- Exempt whole historical directories from the guard: would hide new
  runtime references added to documentation, contracts or old decisions.

## Open questions and acceptance gate

The operator chooses the final CLI, config, helper, unit, path and repository
names; the duration and release boundary of public aliases; and the licence
switch date. Candidate spellings remain subject to the operator's name
clearance. Approve this ADR before any implementation unit is queued.
Authorship is already confirmed for the five inventoried identities; only
an additional identity would need another answer. Asset-origin exceptions
remain separate publication blockers, not a reopening of the licence choice.

Acceptance requires a tested maintenance upgrade and reversal, unchanged
Machine/storage state, an unchanged second apply, software checks in all
three repositories and installed session inspection followed by a frozen
Nitro/Predator campaign. This proposal supplies none of that runtime or
hardware evidence.
