"""A PCI device held outside both GPU handoff policy surfaces.

The qemu hook acts only at prepare. A device attached to a running domain
(`virsh attach-device`) never reaches it, so the recorded rung can be cleaner
than the GPU's real history. These tests read each live domain XML, the way
`hyperlabctl doctor` and the shell's trust field do, and require that such a
holder, or a domain whose live XML cannot be read, is never reported as clean.
"""

import io
import json
from contextlib import redirect_stdout
from unittest import mock

import world
from harness import check, equals
from hyperlabctl import document
from hyperlabctl.cli import main
from hyperlabctl.panel.model import tiles
from hyperlabctl.providers.domains import observe_pci_holders
from hyperlabctl.render import as_text, as_waybar, trust_claim, waybar_field

QEMU = "http://libvirt.org/schemas/domain/qemu/1.0"
MANAGED = "hyperlabctl.providers.domains.observe_managed_gpu_policies"


def _virsh(ctx):
    return [ctx.config.virsh_bin, "-c", ctx.config.libvirt_uri, "-q"]


def _live(ctx, name, devices, root_attributes=""):
    ctx.runner.register(_virsh(ctx) + ["dumpxml", name],
                        "<domain type='kvm'%s><name>%s</name><memory unit='KiB'>1048576</memory>"
                        "<devices>%s</devices></domain>" % (root_attributes, name, devices))


def _run(argv, ctx):
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = main(argv, ctx=ctx)
    return code, buffer.getvalue()


def _holder(name="rogue-tmp", state="running", trust=2):
    return world.build(domains=[{"name": name, "state": state, "memory_mb": 1024,
                                 "network": "lab", "vfio": True}], trust=trust)


def _managed(policies=None, surface="ok"):
    return mock.patch(MANAGED, return_value=(policies or {}, surface))


def test_mapped_static_holder_keeps_the_recorded_rung():
    ctx = _holder("win11clean-valley", trust=3)
    with _managed():
        built = document.build(ctx)
    equals("static_holder_state", built["trust"]["ladder_state"], "recorded")
    equals("static_holder_claim", trust_claim(built),
           {"known": True, "claimed": True, "identity": "clean", "level": 3,
            "ladder": "recorded"})
    check("static_holder_no_problem",
          not [p for p in built["problems"] if p["id"].startswith("trust.")])


def test_mapped_managed_holder_keeps_the_recorded_rung():
    ctx = _holder("dev-01", trust=2)
    with _managed({"dev-01": "dev"}):
        built = document.build(ctx)
    equals("managed_holder_state", built["trust"]["ladder_state"], "recorded")
    equals("managed_holder_claim", trust_claim(built)["identity"], "dev")


def test_unmapped_holder_makes_the_ladder_unknown_and_names_it():
    ctx = _holder("rogue-tmp", trust=3)
    with _managed({"dev-01": "dev"}):
        built = document.build(ctx)
    trust = built["trust"]
    equals("outside_state", trust["ladder_state"], "outside-policy")
    equals("outside_names", trust["outside_policy"], ["rogue-tmp"])
    equals("outside_cannot_ascend", trust["can_ascend"], False)
    claim = trust_claim(built)
    equals("outside_claim", claim, {"known": False, "claimed": False, "identity": None,
                                    "level": None, "ladder": "outside-policy"})
    found = [p for p in built["problems"] if p["id"] == "trust.gpu_outside_policy"]
    equals("outside_one_problem", len(found), 1)
    equals("outside_problem_error", found[0]["severity"], "error")
    check("outside_problem_names_domain", "rogue-tmp" in found[0]["message"], found)
    payload = waybar_field(built, "trust")
    equals("outside_field_text", payload["text"], "?")
    equals("outside_field_class", payload["class"], "error")
    check("outside_field_reboot", "unknown, reboot to reset" in payload["tooltip"], payload)
    check("outside_field_no_rung", "clean" not in payload["tooltip"], payload)
    check("outside_summary_reboot", "unknown, reboot to reset" in as_waybar(built)["tooltip"])
    check("outside_text_reboot", "unknown, reboot to reset" in as_text(built, color=False))
    trust_tile = [tile for tile in tiles(built) if tile["label"] == "trust"][0]
    equals("outside_tile", (trust_tile["value"], trust_tile["tone"]),
           ("unknown, reboot to reset", "error"))


def test_doctor_reports_the_unmapped_holder_as_an_error():
    ctx = _holder("rogue-tmp", trust=2)
    with _managed():
        code, output = _run(["--json", "doctor"], ctx)
    entries = [entry for entry in json.loads(output) if entry["id"] == "trust.gpu_outside_policy"]
    equals("doctor_outside_exit", code, 2)
    equals("doctor_outside_count", len(entries), 1)
    check("doctor_outside_names", "rogue-tmp" in entries[0]["message"], entries)
    check("doctor_outside_remedy", "reboot" in (entries[0]["remedy"] or ""), entries)


def test_trust_command_refuses_to_list_reachable_levels_for_an_outside_holder():
    ctx = _holder("rogue-tmp", trust=None)
    with _managed():
        code, output = _run(["--json", "trust"], ctx)
    payload = json.loads(output)
    equals("trust_outside_rc", code, 1)
    equals("trust_outside_known", payload["known"], False)
    equals("trust_outside_ladder", payload["ladder"], [])
    equals("trust_outside_state", payload["ladder_state"], "outside-policy")


def test_an_unclaimed_boot_with_an_outside_holder_cannot_rise():
    # Unclaimed is the only state from which a rung may rise; an outside
    # holder has used the GPU anyway, so nothing is reachable any more.
    ctx = _holder("rogue-tmp", trust=None)
    with _managed():
        built = document.build(ctx, only={"trust"})
    equals("unclaimed_outside_cannot_ascend", built["trust"]["can_ascend"], False)
    equals("unclaimed_outside_claim_known", trust_claim(built)["known"], False)


def test_a_paused_holder_still_holds_the_device():
    ctx = _holder("rogue-tmp", state="paused")
    with _managed():
        built = document.build(ctx, only={"trust"})
    equals("paused_outside", built["trust"]["outside_policy"], ["rogue-tmp"])


def test_a_stopped_unmapped_definition_holds_nothing():
    ctx = _holder("rogue-tmp", state="shut off")
    with _managed():
        built = document.build(ctx, only={"trust"})
    equals("stopped_recorded", built["trust"]["ladder_state"], "recorded")


def test_no_holder_keeps_the_recorded_rung():
    ctx = world.build(domains=[{"name": "debian-dev", "state": "running", "memory_mb": 1024,
                                "network": "dev"}], trust=2)
    with _managed():
        built = document.build(ctx, only={"trust"})
    equals("no_holder_state", built["trust"]["ladder_state"], "recorded")
    equals("no_holder_lists", (built["trust"]["outside_policy"], built["trust"]["unverified"]),
           ([], []))
    equals("no_holder_claim_level", trust_claim(built)["level"], 2)


def test_no_domain_at_all_is_unclaimed():
    ctx = world.build(domains=[], trust=None)
    with _managed(surface="missing"):
        built = document.build(ctx, only={"trust"})
    equals("empty_claim", trust_claim(built),
           {"known": True, "claimed": False, "identity": None, "level": None,
            "ladder": "recorded"})


def test_unreadable_live_xml_is_unknown_not_clean():
    ctx = world.build(domains=[{"name": "debian-dev", "state": "running", "memory_mb": 1024,
                                "network": "dev"}], trust=3)
    ctx.runner.register(_virsh(ctx) + ["dumpxml", "debian-dev"], (1, "", "error: permission"))
    with _managed():
        built = document.build(ctx)
    trust = built["trust"]
    equals("unreadable_state", trust["ladder_state"], "unverified")
    equals("unreadable_names", trust["unverified"], ["debian-dev"])
    equals("unreadable_cannot_ascend", trust["can_ascend"], False)
    claim = trust_claim(built)
    equals("unreadable_claim_unknown", (claim["known"], claim["ladder"]), (False, "unverified"))
    found = [p for p in built["problems"] if p["id"] == "trust.gpu_holders_unverified"]
    equals("unreadable_problem", [p["severity"] for p in found], ["error"])
    check("unreadable_problem_names", "debian-dev" in found[0]["message"], found)
    check("unreadable_not_reboot", "reboot to reset" not in waybar_field(built, "trust")["tooltip"])


def test_malformed_live_xml_is_unknown_not_clean():
    ctx = world.build(domains=[{"name": "debian-dev", "state": "running", "memory_mb": 1024,
                                "network": "dev"}], trust=None)
    ctx.runner.register(_virsh(ctx) + ["dumpxml", "debian-dev"], "<domain><name>debian-dev")
    with _managed():
        built = document.build(ctx, only={"trust"})
    equals("malformed_state", built["trust"]["ladder_state"], "unverified")
    equals("malformed_claim_known", trust_claim(built)["known"], False)


def test_an_unlisted_inventory_is_unknown_not_clean():
    ctx = world.build(domains=[], trust=None)
    ctx.runner.register(_virsh(ctx) + ["list", "--all", "--name"], (1, "", "error: denied"))
    with _managed():
        built = document.build(ctx, only={"trust"})
    equals("unlisted_state", built["trust"]["ladder_state"], "unverified")
    equals("unlisted_claim_known", trust_claim(built)["known"], False)


def test_an_unreadable_policy_surface_cannot_clear_a_holder():
    ctx = _holder("dev-01")
    for surface in ("missing", "unsafe", "unavailable", "collision"):
        ctx.cache.clear()
        with _managed({}, surface):
            built = document.build(ctx, only={"trust"})
        equals("surface_%s_state" % surface, built["trust"]["ladder_state"], "unverified")
        equals("surface_%s_names" % surface, built["trust"]["unverified"], ["dev-01"])


def test_a_policy_collision_between_surfaces_is_not_ok():
    ctx = _holder("win11clean-valley")
    with _managed({"win11clean-valley": "clean"}):
        holders = observe_pci_holders(ctx)
    # The hook refuses every prepare while both surfaces name a domain; the
    # static entry still maps it, so the holder itself is not outside policy.
    equals("collision_static_still_maps", holders["state"], "recorded")
    ctx = _holder("dev-01")
    with _managed({"dev-01": "dev", "win11clean-valley": "clean"}):
        holders = observe_pci_holders(ctx)
    equals("collision_managed_unverified", holders["state"], "unverified")


def test_every_passthrough_shape_counts_and_only_the_live_xml_is_read():
    for label, devices, attributes in (
        ("pci", "<hostdev mode='subsystem' type='pci'/>", ""),
        ("interface", "<interface type='hostdev'><source><address type='pci'/></source></interface>",
         ""),
        ("commandline", "", " xmlns:q='%s'><q:commandline><q:arg value='-device'/>"
         "<q:arg value='vfio-pci,host=01:00.0'/></q:commandline" % QEMU),
    ):
        ctx = _holder("rogue-tmp")
        if label == "commandline":
            ctx.runner.register(_virsh(ctx) + ["dumpxml", "rogue-tmp"],
                                "<domain type='kvm'%s><name>rogue-tmp</name></domain>" % attributes)
        else:
            _live(ctx, "rogue-tmp", devices)
        with _managed():
            built = document.build(ctx, only={"trust"})
        equals("shape_%s_outside" % label, built["trust"]["outside_policy"], ["rogue-tmp"])
        reads = [call for call in ctx.runner.calls if "dumpxml" in call]
        check("shape_%s_live_read" % label, reads and all("--inactive" not in call for call in reads),
              reads)


def test_mixed_holders_report_outside_policy_before_unknown():
    ctx = world.build(domains=[
        {"name": "rogue-tmp", "state": "running", "memory_mb": 1024, "vfio": True},
        {"name": "debian-dev", "state": "running", "memory_mb": 1024},
    ], trust=1)
    ctx.runner.register(_virsh(ctx) + ["dumpxml", "debian-dev"], (1, "", "error"))
    with _managed():
        built = document.build(ctx, only={"trust"})
    trust = built["trust"]
    equals("mixed_state", trust["ladder_state"], "outside-policy")
    equals("mixed_lists", (trust["outside_policy"], trust["unverified"]),
           (["rogue-tmp"], ["debian-dev"]))
    ids = sorted(p["id"] for p in built["problems"])
    equals("mixed_problems", ids, ["trust.gpu_holders_unverified", "trust.gpu_outside_policy"])


def test_an_unknown_domain_state_with_passthrough_is_unknown():
    ctx = _holder("rogue-tmp", state="unknown")
    with _managed():
        built = document.build(ctx, only={"trust"})
    equals("unknown_state_holder", built["trust"]["ladder_state"], "unverified")


def test_a_section_without_ladder_state_is_never_known():
    for label, section in (
        ("missing", {"claimed": True, "name": "dev", "level": 2}),
        ("other", {"claimed": True, "name": "dev", "level": 2, "ladder_state": "clean"}),
    ):
        equals("ladder_%s_unknown" % label, trust_claim({"trust": section})["known"], False)
