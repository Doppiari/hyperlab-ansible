# Mutations

Every mutation below was applied, the suite executed, the result recorded, and
the file restored. A mutation that does not turn the suite red is reported as
green with the reason, not quietly dropped.

| # | File | Mutation | Result | Assertion that caught it |
|---|------|----------|--------|--------------------------|
| 1 | `document.py` | catch `ValueError` instead of `Exception` | red | `test_document_survives_a_crashing_provider` |
| 2 | `providers/memory.py` | drop the VFIO fixed overhead term | red | `overhead_mb` expected 768, got 512 |
| 3 | `providers/domains.py` | invert the blocked comparison | red | `test_stopped_domain_reports_how_much_it_is_short` |
| 4 | `providers/gpu.py` | `all()` becomes `any()` when deciding `bound` | red, after a test was added | `half_bound_not_bound` |
| 5 | `providers/trust.py` | a claimed level reports `can_ascend: true` | red | `claimed_can_ascend` |
| 6 | `registry.py` | the unprivileged filter returns everything | red | `action_vm.create_subcommand_exists` |
| 7 | `render.py` | waybar payload grows a fifth key | red | `waybar_keys` |
| 8 | `operations.py` | `start` no longer checks the budget | red | `refused_exit_code` expected 2, got 0 |
| 9 | `providers/__init__.py` | remove the discovery import loop | red | `status_exit_code_error` |
| 10 | `panel/model.py` | the footer offers start on a blocked domain | red | `start_disabled_when_blocked` |
| 11 | `panel/model.py` | the selection is no longer clamped to existing rows | red | `test_selection_is_clamped_to_the_rows_that_exist` |
| 12 | `remedies.py` | one problem loses its remedy | red, after a test was added | `no_problem_without_a_remedy` |
| 13 | `journal.py` | priority 4 read as info instead of warn | red | `warn_level` |
| 14 | `render.py` | an unreadable pill stays yellow instead of going red | red | `unreadable_class` |
| 15 | `operations.py` | the refusal no longer names the shortfall | red | `refusal_states_the_shortfall` |
| 16 | `providers/__init__.py` | a broken extension becomes fatal | red | `test_a_broken_extension_does_not_stop_a_good_one` |
| 17 | `panel/views.py` | two views may claim the same key | red, after a test was added | `duplicate_view_key_refused` |
| 18 | `panel/model.py` | the gauge is no longer clamped to 0..1 | red | `gauge_width_2.0` expected 14, got 28 |
| 19 | `commands/watch.py` | `watch` keeps looping with no virsh | red, after a test was added | `watch_bailed` |
| 20 | `config.py` | an override is ignored | red | `nitro_status_exit` |
| 21 | `commands/net.py` | an inactive network is reported active | red | `lab_inactive` |
| 22 | `providers/images.py` | sealed without a checksum stops being an error | red, after a test was added | `sealed_without_checksum_flagged` |
| 23 | `registry.py` | an unavailable action is offered anyway | red | `no_available_action_may_reference_a_missing_playbook` |
| 24 | `cli.py` | remove global-option normalization, so `actions --json` is rejected | red | `test_global_json_flag_is_accepted_after_the_subcommand` |
| 25 | `runner.py` | stop forcing the C locale for parsed subprocess output | red | `test_runner_forces_machine_parseable_locale` |
| 26 | `runner.py` | turn explicit `timeout=None` back into the default timeout | red | `test_runner_preserves_an_explicit_no_timeout` |
| 27 | `commands/watch.py` | treat every libvirt failure like a heartbeat timeout | red | `test_watch_stops_on_a_real_libvirt_error_instead_of_spinning` |
| 28 | `registry.py` | allow `vm-specs/` to redirect outside the repository | red | `test_target_choices_refuse_a_redirected_spec_directory` |
| 29 | `operations.py` | let a managed M3 domain use direct `virsh start` | red | `test_managed_domain_cannot_bypass_the_m3_start_playbook` |
| 30 | `operations.py` | start anyway when the memory budget cannot be read | red | `test_start_refuses_when_the_memory_budget_cannot_be_read` |
| 31 | `operations.py` | start a VFIO domain absent from `gpu_domain_profiles` | red | `test_unguarded_vfio_domain_cannot_start_from_the_cockpit` |
| 32 | `commands/panic.py` | pause a domain before its links go down | red | `panic_failure_count` |
| 33 | `commands/panic.py` | restore without `--confirm` | red | `panic_unconfirmed_exit` |
| 34 | `commands/panic.py` | a second engage starts a new record | red | `panic_second_keeps_time` |
| 35 | `commands/panic.py` | a link the operator had set down is recorded | red | `panic_restored_links` |
| 36 | `commands/panic.py` | restore resumes a recorded domain the stop did not pause | red, after a test was added | `panic_unpaused_stays_paused` |
| 37 | `commands/panic.py` | the record is written 0644 | red | `panic_file_mode` |
| 38 | `commands/net.py` | a definition that names another network is accepted | red, after a test was added | `lab_gateway_unknown` expected None, got '10.10.3.1' |
| 39 | `commands/net.py` | the gateway is copied from `group_vars` instead of `net-dumpxml` | red, after a test was added | `lab_gateway` expected '10.10.4.1', got None |
| 40 | `commands/net.py` | an unparseable definition reads as declaring no gateway or DHCP | red, after a test was added | `services_gateway_unknown` expected None, got False |


## Cockpit/M3 integration mutations

Mutations 24-31 were replayed after the semi-final cockpit was integrated with
M3. All eight turned the component suite red. They pin the defects found in
review rather than only the original design: shell-surface option order, stable
locale, the watch heartbeat timeout, repository target containment, and the
three fail-closed boundaries around managed, over-budget and unregistered VFIO
domains.

## Mutation 4 survived the first run

`all()` to `any()` was not killed, because the only unbound fixture put both
PCI functions on non-VFIO drivers, where `any()` is false as well.

The state that separates them is the mixed one: VGA on `vfio-pci`, audio still
on `snd_hda_intel`. That is not hypothetical - it is what the Nitro reported on
19/07 when the profile IDs did not match the installed card. A test for it was
added (`test_gpu_half_bound_is_not_bound`), and the mutation was replayed and
seen red on `half_bound_not_bound`.

The gap was in the tests, not in the code. The mutation is what found it.


## Mutation 12 survived the first run

Deleting the `gpu.not_bound` remedy changed nothing, because the only test that
walked the remedies used a host with no hardware profile, where the GPU section
fails earlier with a different problem id. The remedy table was checked by
accident, not on purpose.

`tests/test_remedies.py` now scans the provider sources for every declared
problem id and asserts the table covers all of them, so a new problem arrives
with its remedy or the suite says so. The mutation was replayed and is red.

## A mutation replay can lie to you

Mutations 13 and 14 first reported red for the wrong reason: mutation 13
replaces `warn` with `info`, which leaves the file byte-for-byte the same
length, and with a coarse mtime Python reused the cached bytecode from the
mutated run after the file had already been restored. The suite was reporting
on code that was no longer on disk.

Every mutation in this file was replayed with `PYTHONDONTWRITEBYTECODE=1` and
the caches removed. Same-length edits are the dangerous ones: a mutation that
changes the file size hides this bug instead of exposing it.


## Three more survived their first run

- **17** - nothing asserted that two views may not claim the same key, so the
  guard could be deleted silently. `test_two_views_may_not_claim_the_same_key`
  now does.
- **19** - `watch` bailing out when virsh is absent had no test. It does now,
  and the mutation is interesting: without the guard the suite does not fail,
  it *hangs*, because the loop never terminates. The replay harness runs each
  mutation with a timeout and treats a hang as red, which is the honest reading.
- **22** - the sealed-without-checksum rule was never exercised, because the
  fake host only carried a `not-built` manifest. The fixture takes extra
  manifests now, and both the violating and the clean case are pinned.

## A mutation replay can lie to you, twice

Mutations 13 and 14 first reported red for the wrong reason: replacing `warn`
with `info` leaves the file exactly the same length, and with a coarse mtime
Python reused the bytecode from the mutated run after the file was restored.

Then a replay timed out mid-run and left `commands/watch.py` mutated on disk,
which quietly poisoned the next three test runs until the diff was read. Both
lessons are in the harness now: `PYTHONDONTWRITEBYTECODE=1`, a per-mutation
timeout, and the restore in a `finally`.


## What the linter found that the suite did not

`ruff check` with pyflakes and bugbear selected found four unused imports, a
loop variable that was never read, and eight places where an exception was
re-raised without its cause - which on a diagnostic tool is the difference
between "PyYAML is not importable" and knowing which import failed.

It also caught a defect introduced while fixing those: `raise ... from exc` in a
handler that had never bound `exc`, which would have raised `NameError` on the
one path it was meant to describe. The suite did not catch it because that path
only fires on a host without PyYAML. `ruff.toml` records the ruleset so the
check is reproducible rather than a one-off.


## Terminal domain spheres

`tests/cli_domain_spheres_contract.py` and the focused render component suite
were run against isolated copies of the current CLI sources. Each changed file
was backed up before the break, restored
byte-for-byte afterwards, and checked green before the next mutation. All 33
final breaks exited 1 and every restored check exited 0. The complete component
suite also passes.

| Mutation | File | Break | Result | Observed check |
| --- | --- | --- | --- | --- |
| `pipe-colour` | `cli.py` | Ignore stdout TTY detection | red | The plain-output inventory sentinel fires before the frozen pipe-byte check |
| `ignore-no-color` | `cli.py` | Ignore NO_COLOR presence | red | The inventory sentinel forbids reads with NO_COLOR present and empty |
| `ignore-dumb` | `cli.py` | Ignore TERM=dumb | red | The inventory sentinel forbids reads with TERM=dumb |
| `ignore-never` | `cli.py` | Ignore never mode | red | The inventory sentinel forbids reads in never mode |
| `alias-always` | `cli.py` | Make --no-color select always | red | The inventory sentinel forbids reads with the legacy alias |
| `drop-color-normalization` | `cli.py` | Stop normalizing --color=VALUE | red | Trailing --color=always is rejected in the plain-path fixture |
| `suppress-always` | `cli.py` | Remove the explicit always environment override | red | Explicit always overrides terminal environment suppression |
| `literal-colour` | `render.py` | Replace domain RGB lookup with a hex literal | red | AST refuses a typed CLI colour |
| `fixed-rgb` | `render.py` | Replace domain RGB lookup with a fixed RGB triple | red | Exact RGB domain prefix differs from the palette |
| `theme-domains` | `render.py` | Read the appearance variant as the domain table | red | Appearance tokens fail semantic table validation |
| `wrong-256` | `render.py` | Choose the farthest indexed colour | red | Fixed-index nearest/tie oracle, before the independent row-prefix comparison |
| `ignore-truecolor` | `render.py` | Always emit indexed ANSI | red | Exact truecolor prefix oracle |
| `missing-reset` | `render.py` | Omit the reset after the dot | red | Exact prefix includes a reset before the existing row |
| `filled-external` | `render.py` | Return a filled dot for neutral identities | red | Neutral prefix is an uncoloured outline |
| `guest-host-grey` | `render.py` | Allow a guest domain named host to use HOST grey | red | HOST grey remains reserved |
| `fold-domain-case` | `render.py` | Fold domain case before lookup | red | Noncanonical Dev remains neutral |
| `duplicate-keys` | `render.py` | Remove YAML duplicate-key refusal | red after added fixtures | Complete duplicate maps and repeated domain keys are refused |
| `redirected-palette` | `render.py` | Remove palette path symlink refusal | red | Symlinked palette is refused |
| `aliased-palette` | `render.py` | Remove YAML alias refusal | red | Aliased complete domain table is refused |
| `incomplete-palette` | `render.py` | Remove exact domain-key validation | red after added fixtures | Additional unreviewed domain key is refused |
| `raw-vm-identity` | `commands/vm.py` | Use the raw trust_profile instead of product provenance | red | External GPU-profile fallback remains neutral |
| `machine-intent-identity` | `commands/machine.py` | Use record network_profile instead of inventory provenance | red | The drifting sample-5 must have a neutral outline |
| `machine-membership-refusal` | `commands/machine.py` | Catch only ContractError instead of HyperlabError during classification | red | An unreadable membership reread must still print neutral Machine rows |
| `plain-vm-inventory` | `commands/vm.py` | Replace the args.color inventory guard with True | red | The failing call sentinel detects a product-inventory read on a pipe |
| `plain-machine-inventory` | `commands/machine.py` | Replace the args.color inventory guard with True | red | The failing call sentinel detects a product-inventory read on a pipe |
| `json-colour-guard` | `cli.py` | Remove not args.json from the colour policy | red | test_json_dispatch_disables_colour_even_with_a_terminal_and_always observes True instead of False |
| `missing-vm-dot` | `commands/vm.py` | Remove the VM row prefix | red | VM terminal prefix |
| `missing-machine-dot` | `commands/machine.py` | Remove the Machine row prefix | red | Machine confirmed-provenance terminal prefix |
| `missing-net-dot` | `commands/net.py` | Remove the network row prefix | red | Network terminal prefix |
| `missing-trust-dot` | `commands/trust.py` | Remove the ladder row prefix | red | Trust ladder terminal prefix |
| `invalid-mode` | `cli.py` | Remove the colour option choices | red | An unknown colour mode must be rejected |
| `tie-high-index` | `render.py` | Walk fixed colour indices backwards when choosing the minimum | red | Equidistant greys select the lowest fixed index |
| `standalone-import` | `render.py` | Add a top-level package-relative import | red | `test_status_renderers_still_support_loading_by_filename` raises the original import error |

The read-boundary fixtures forbid the additional product-inventory call on
pipes, suppressed terminals and JSON, and forbid palette reads on JSON. They
raise `AssertionError` rather than a handled availability error, so unchanged
output bytes cannot hide an unwanted read. The JSON dispatch component test
separately detects a lost colour-policy guard even when each JSON renderer
returns before painting. Machine fixtures also cover uncreated and unreadable
runtime, while an unreadable initial registry still refuses its record listing.

### Two palette mutations first stayed green

Removing duplicate-key refusal initially stayed green: the duplicated fixtures
also removed required keys, so the independent completeness check still refused
them. Complete duplicate top-level maps and repeated domain keys now isolate
that invariant; replay is red.

Removing exact-key validation initially stayed green too: missing required keys
were still refused by the subsequent mandatory lookups. A complete table with
an extra, unreviewed domain now isolates exact-key validation; replay is red.
Neither green result was evidence that unsafe input was accepted. Both exposed
a fixture that failed to distinguish the individual guard from another refusal.

## Raw runtime counters

`machine inventory --json` carries the `counters` object the seal's live
layer rates (`runtime_counters` in `commands/machine.py`): the CPU time of
running product Machines and the interface bytes of every active domain, per
network. The check is
`python3 tools/hyperlabctl/tests/run.py`; the assertions are in
`tests/test_machine_counters.py`. Each break was made on the file, the suite
run, the saved copy restored byte-identical and the suite run green again.

| Mutation | File | Break | Result | Assertion that caught it |
| --- | --- | --- | --- | --- |
| `failed-read-zeros` | `commands/machine.py` | A failed `virsh domstats` returns an available sample with empty Machines and networks | red | `failed_unavailable` expected False, got True; `failed_has_no_counters` |
| `unmapped-tap-counted` | `commands/machine.py` | An interface that no definition places is skipped instead of making its networks unknown | red, after a test was added | `unmapped_network_unknown` expected {}, got `dev` from the placed interface alone |
| `missing-bytes-zero` | `commands/machine.py` | A missing `rx.bytes` or `tx.bytes` counts as 0 | red | `missing_tx_network_absent` expected {}, got `dev` with `tx_bytes` 0 |
| `absent-machine-counted` | `commands/machine.py` | A running Machine absent from the answer no longer makes its networks unknown | red | `absent_machine_network` expected {}, got `dev` |
| `unmanaged-not-counted` | `commands/machine.py` | Domains that are not product Machines are skipped | red | `unmanaged_traffic_counted` got 1000 bytes instead of 1300; `unreadable_unmanaged_networks`; `unreadable_bridges_networks`; `bridged_read_network_bridges` |
| `bridge-not-resolved` | `commands/machine.py` | An interface on a bare bridge counts under the bridge's name, not its network's | red | `bridged_traffic_counted` got `virbr-dev` instead of `dev` |
| `unplaced-unmanaged-ignored` | `commands/machine.py` | An unmanaged domain whose definition cannot be read is ignored instead of leaving every network unknown | red | `unreadable_unmanaged_networks` expected {}, got `dev` |

The read first covered product Machines only, so a domain made by hand on
a network moved bytes the seal would call "none"; it now covers every
active domain, and the last three breaks pin that.
`unmapped-tap-counted` stayed green on its first run against that version:
the test's only interface was the unmapped one, so skipping it left the same
empty answer as refusing it. The test now gives the Machine a placed
interface on the same network too, and only refusing it leaves that network
out.

### Bridge-backed Machine attachments

In the domain provider, resolve every interface source through the bridge
map, including explicit network sources. Run the CLI test suite. The mixed
interface fixture uses the same spelling for a bridge and a network and
fails `only_bridge_sources_use_ownership_map`. Restoring the source-type
check gives the network names in interface order and preserves the raw
names in the domain listing.

## GPU held outside the handoff policy

The trust section reads every live domain XML and sets `ladder_state`:
`recorded`, `outside-policy` (a domain in neither installed GPU policy surface
holds a PCI hostdev or a hostdev interface the hook never saw) or
`unverified` (something it needed could not be read, or an unmapped domain
carries a QEMU extension whose devices are unknown). The policy is the one
the hook reads, `/etc/gpu-handoff/domains` and `domains.d`; the test world
installs its own copy and never reads this host's `/etc`. The check is
`python3 tools/hyperlabctl/tests/run.py`; the assertions are in
`tests/test_gpu_holders.py`. Each break was made on the file, the suite run,
the saved copy restored and the suite run green again.

| Mutation | File | Break | Result | Assertion that caught it |
| --- | --- | --- | --- | --- |
| `unreadable-is-no-holder` | `providers/domains.py` | An unreadable live XML is skipped, as if it held nothing | red | `unreadable_state` expected `unverified`, got `recorded` |
| `unreadable-entry-false` | `inventory.py` | The unreadable inventory entry says it holds no device and no extension | red | `unreadable_state` |
| `managed-surface-ignored` | `providers/domains.py` | A mapped holder is not cleared by the installed policy | red | `managed_holder_state` |
| `surface-failure-trusted` | `providers/domains.py` | An unusable installed policy is not a reason for unknown | red | `static_missing_state` and every unusable surface |
| `paused-skipped` | `providers/domains.py` | Only a running domain counts as a holder | red | `paused_outside` |
| `unknown-state-skipped` | `providers/domains.py` | A holder whose state cannot be read counts as stopped | red | `unknown_state_holder` |
| `claim-ignores-outside` | `render.py` | `trust_claim` ignores an outside holder | red | `outside_claim` and the projection checks |
| `missing-ladder-state-believed` | `render.py` | A section without `ladder_state` keeps its rung | red | `ladder_missing_unknown` |
| `inactive-xml-read` | `inventory.py` | `dumpxml --inactive`, the persistent definition | red | `shape_pci_outside` and every unregistered read |
| `commandline-not-seen` | `domainxml.py` | A QEMU extension is not observed at all | red | `extension_environment_state` |
| `interface-not-a-device` | `domainxml.py` | A hostdev interface is not a held device | red | `shape_interface_outside` |
| `holder-unnamed` | `providers/trust.py` | The doctor problem omits the domain's name | red | `outside_problem_names_domain` |
| `outside-can-ascend` | `providers/trust.py` | An outside holder leaves `can_ascend` as read from the file | red, after a test was added | `unclaimed_outside_cannot_ascend` |

`outside-can-ascend` stayed green on its first run: the only outside-holder
fixture had a claimed rung, where `can_ascend` is already false. An unclaimed
boot with an outside holder now pins it.

### Review: the installed policy, identity, extensions and the rung

The first version read the static policy from the checkout, skipped
`domains.d` for a static match, lost the holder when the rung was unreadable,
trusted the live XML's identity and called any QEMU extension a held device
([problem record](../../problems/gpu-held-outside-the-handoff-policy.md)).

| Mutation | File | Break | Result | Assertion that caught it |
| --- | --- | --- | --- | --- |
| `checkout-policy-clears-holder` | `providers/domains.py` | A name in the checkout's `gpu_domain_profiles` clears a holder | red | `checkout_only_outside` |
| `cross-surface-collision-accepted` | `providers/domains.py` | A domain named by both surfaces is accepted | red | `collision_static_holder_state` |
| `managed-failure-ignored` | `providers/domains.py` | An unusable `domains.d` does not stop a static match | red | `managed_missing_static_holder` |
| `static-symlink-followed` | `providers/domains.py` | The static file is read through a symlink | red | `static_symlink_state` |
| `static-duplicate-accepted` | `providers/domains.py` | A duplicate static line is accepted | red | `static_duplicate_state` |
| `static-writable-accepted` | `providers/domains.py` | A group- or world-writable static file is accepted | red | `static_writable_state` |
| `extension-is-a-holder` | `providers/domains.py` | An unmapped extension counts as a confirmed holder | red | `extension_environment_state` |
| `unguarded-from-checkout` | `providers/domains.py` | `domains.unguarded_vfio` ignores the installed policy | red | `managed_only_not_unguarded` |
| `identity-unchecked` | `inventory.py` | A live XML for another identity is used | red | `identity_other_name_unknown` and the other identity cases |
| `rung-failure-hides-holder` | `providers/trust.py` | An unreadable rung drops the section, holder and all | red | `rung_permission_section_kept` |
| `rung-error-dropped` | `providers/trust.py` | The rung read failure is not reported beside the holder | red | `rung_permission_read_failure_kept` |
| `claim-needs-a-rung-first` | `render.py` | `trust_claim` needs a readable rung before it sees an outside holder | red | `rung_permission_claim` |

Replay from `tools/hyperlabctl` on an otherwise idle tree:

```bash
python3 - <<'PY'
from pathlib import Path
import shutil
import subprocess
import tempfile

D = Path('hyperlabctl/providers/domains.py'); R = Path('hyperlabctl/render.py')
I = Path('hyperlabctl/inventory.py'); X = Path('hyperlabctl/domainxml.py'); T = Path('hyperlabctl/providers/trust.py')
M = [
 ('unreadable-is-no-holder', D, [('        if devices is None or extension is None:\n            unknown(name, "its live XML could not be read")\n            continue\n', '')], 'unreadable_state'),
 ('unreadable-entry-false', I, [('"pci_devices": None, "qemu_extension": None,', '"pci_devices": False, "qemu_extension": False,')], 'unreadable_state'),
 ('managed-surface-ignored', D, [('        elif name in policy["mapping"]:\n            continue\n', '')], 'managed_holder_state'),
 ('surface-failure-trusted', D, [('        if policy["state"] != "ok":\n', '        if False:\n')], 'static_missing_state'),
 ('paused-skipped', D, [('        if domain.get("state") == "shut off":\n', '        if domain.get("state") != "running":\n')], 'paused_outside'),
 ('unknown-state-skipped', D, [('        if domain.get("state") == "unknown":\n            unknown(name, "its state could not be read")\n            continue\n', '')], 'unknown_state_holder'),
 ('claim-ignores-outside', R, [('    if isinstance(trust, dict) and trust.get("ladder_state") == "outside-policy":\n        return {**unknown, "ladder": "outside-policy"}\n', '')], 'outside_claim'),
 ('missing-ladder-state-believed', R, [('    if trust.get("ladder_state") != "recorded":\n        return {**unknown, "ladder": "unverified"}\n', '')], 'ladder_missing_unknown'),
 ('inactive-xml-read', I, [('result = ctx.virsh("dumpxml", name)', 'result = ctx.virsh("dumpxml", "--inactive", name)')], 'shape_pci_outside'),
 ('commandline-not-seen', X, [('    return any(node.tag.startswith("{%s}" % QEMU) for node in root.iter())\n', '    return False\n')], 'extension_environment_state'),
 ('interface-not-a-device', X, [('        or node.tag == "interface" and node.get("type") == "hostdev"\n', '')], 'shape_interface_outside'),
 ('holder-unnamed', T, [('"reboot to reset" % name,', '"reboot to reset",')], 'outside_problem_names_domain'),
 ('outside-can-ascend', T, [('        if holders["state"] != "recorded":\n            section["can_ascend"] = False\n', '')], 'unclaimed_outside_cannot_ascend'),
    ('checkout-policy-clears-holder', D,
     [('        elif name in policy["mapping"]:\n',
       '        elif name in policy["mapping"] or name in (ctx.config.var("gpu_domain_profiles", {}) or {}):\n')],
     'checkout_only_outside'),
    ('cross-surface-collision-accepted', D,
     [('    elif set(static) & set(managed):\n        state = "policy collision"\n', '')],
     'collision_static_holder_state'),
    ('managed-failure-ignored', D,
     [('    elif managed_state != "ok":\n        state = "managed policy %s" % managed_state\n', '')],
     'managed_missing_static_holder'),
    ('static-symlink-followed', D,
     [('os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK', 'os.O_RDONLY | os.O_NONBLOCK')],
     'static_symlink_state'),
    ('static-duplicate-accepted', D,
     [('        if parts[0] in result:\n            return {}, "collision"\n', '')],
     'static_duplicate_state'),
    ('static-writable-accepted', D,
     [('                or info.st_mode & 0o022\n', '')],
     'static_writable_state'),
    ('extension-is-a-holder', D,
     [('        elif devices:\n', '        elif devices or extension:\n')],
     'extension_environment_state'),
    ('unguarded-from-checkout', D,
     [('                    guarded = domain["name"] in installed["mapping"]\n',
       '                    guarded = gpu is not None\n')],
     'managed_only_not_unguarded'),
    ('identity-unchecked', I,
     [('    require_identity(result.stdout, name)\n', '')],
     'identity_other_name_unknown'),
    ('rung-failure-hides-holder', T,
     [('            if holders["state"] != "outside-policy":\n                raise\n', '            raise\n')],
     'rung_permission_section_kept'),
    ('rung-error-dropped', T,
     [('            found.append(dict(section["rung_error"]))\n', '            pass\n')],
     'rung_permission_read_failure_kept'),
    ('claim-needs-a-rung-first', R,
     [('    if isinstance(trust, dict) and trust.get("ladder_state") == "outside-policy":\n'
       '        return {**unknown, "ladder": "outside-policy"}\n'
       '    if not isinstance(trust, dict) or not isinstance(trust.get("claimed"), bool):\n'
       '        return {**unknown, "ladder": "unverified"}\n',
       '    if not isinstance(trust, dict) or not isinstance(trust.get("claimed"), bool):\n'
       '        return {**unknown, "ladder": "unverified"}\n'
       '    if trust.get("ladder_state") == "outside-policy":\n'
       '        return {**unknown, "ladder": "outside-policy"}\n')],
     'rung_permission_claim'),
]
cmd = ['python3', 'tests/run.py']
with tempfile.TemporaryDirectory() as tmp:
    for name, path, edits, reason in M:
        backup = Path(tmp) / (name + path.name); shutil.copy2(path, backup)
        text = path.read_text()
        for old, new in edits:
            assert text.count(old) == 1, (name, old); text = text.replace(old, new, 1)
        try:
            path.write_text(text)
            red = subprocess.run(cmd, text=True, capture_output=True, timeout=600)
            out = red.stdout + red.stderr
            fails = [l.strip() for l in out.splitlines() if l.strip().startswith('FAIL')]
            assert red.returncode != 0 and reason in out, (name, red.returncode, fails[:5])
        finally:
            shutil.copy2(backup, path)
        green = subprocess.run(cmd, text=True, capture_output=True, timeout=600)
        assert green.returncode == 0, (name, 'restore failed')
        print(f"{name}: red ({len(fails)} failures, incl. {reason}); restored green", flush=True)
PY
```
