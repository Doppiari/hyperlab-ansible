"""A PCI device held outside both installed GPU handoff policy surfaces.

The qemu hook acts only at prepare. A device attached to a running domain
(`virsh attach-device`) never reaches it, so the recorded rung can be cleaner
than the GPU's real history. These tests read each live domain XML, the way
`hyperlabctl doctor` and the shell's trust field do, against the policy the
hook actually reads (the installed static file and `domains.d`, never the
checkout), and require that such a holder, or anything that cannot be read,
is never reported as clean.
"""

import errno
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import world
from harness import check, equals
from hyperlabctl import document
from hyperlabctl.cli import main
from hyperlabctl.panel.model import tiles
from hyperlabctl.providers.domains import observe_pci_holders
from hyperlabctl.remedies import REMEDIES
from hyperlabctl.render import as_text, as_waybar, trust_claim, waybar_field

QEMU = "http://libvirt.org/schemas/domain/qemu/1.0"
MANAGED = "hyperlabctl.providers.domains.observe_managed_gpu_policies"


def _virsh(ctx):
    return [ctx.config.virsh_bin, "-c", ctx.config.libvirt_uri, "-q"]


def _live(ctx, name, devices, root_attributes="", tail=""):
    ctx.runner.register(_virsh(ctx) + ["dumpxml", name],
                        "<domain type='kvm'%s><name>%s</name><memory unit='KiB'>1048576</memory>"
                        "<devices>%s</devices>%s</domain>" % (root_attributes, name, devices, tail))


def _run(argv, ctx):
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = main(argv, ctx=ctx)
    return code, buffer.getvalue()


def _holder(name="rogue-tmp", state="running", trust=2, **policy):
    return world.build(domains=[{"name": name, "state": state, "memory_mb": 1024,
                                 "network": "lab", "vfio": True}], trust=trust, **policy)


def _ids(built, prefix="trust."):
    return sorted(p["id"] for p in built["problems"] if p["id"].startswith(prefix))


def _failing_read(ctx, error):
    target = str(ctx.config.gpu_handoff_state)
    real = Path.read_text

    def read_text(self, *args, **kwargs):
        if str(self) == target:
            raise error
        return real(self, *args, **kwargs)

    return mock.patch.object(Path, "read_text", read_text)


def test_mapped_static_holder_keeps_the_recorded_rung():
    built = document.build(_holder("win11clean-valley", trust=3))
    equals("static_holder_state", built["trust"]["ladder_state"], "recorded")
    equals("static_holder_claim", trust_claim(built),
           {"known": True, "claimed": True, "identity": "clean", "level": 3,
            "ladder": "recorded"})
    equals("static_holder_no_problem", _ids(built), [])


def test_mapped_managed_holder_keeps_the_recorded_rung():
    built = document.build(_holder("dev-01", trust=2, installed_managed={"dev-01": "dev"}))
    equals("managed_holder_state", built["trust"]["ladder_state"], "recorded")
    equals("managed_holder_claim", trust_claim(built)["identity"], "dev")


def test_the_installed_static_policy_decides_not_the_checkout():
    # Checkout maps win11clean-valley; the installed file (an older apply)
    # does not: the hook would refuse it, so it is outside policy.
    built = document.build(_holder("win11clean-valley", trust=3,
                                   installed_static={"win11dirty-disposable": "dirty"}))
    equals("checkout_only_outside", built["trust"]["outside_policy"], ["win11clean-valley"])
    equals("checkout_only_claim", trust_claim(built)["ladder"], "outside-policy")
    code, output = _run(["--json", "doctor"], _holder(
        "win11clean-valley", trust=3, installed_static={"win11dirty-disposable": "dirty"}))
    named = [e for e in json.loads(output) if e["id"] == "trust.gpu_outside_policy"]
    check("checkout_only_doctor_names", code == 2 and named
          and "win11clean-valley" in named[0]["message"], output)
    # The installed file maps a domain the checkout does not know: mapped.
    built = document.build(_holder("lab-gpu", trust=0, installed_static={"lab-gpu": "lab"}))
    equals("installed_only_recorded", built["trust"]["ladder_state"], "recorded")
    equals("installed_only_claim", trust_claim(built)["identity"], "lab")
    equals("installed_only_field", waybar_field(built, "trust")["text"], "lab 0")


def test_an_unusable_installed_static_policy_cannot_clear_a_holder():
    def broken(label, change):
        ctx = _holder("win11clean-valley", trust=3)
        path = Path(ctx.config.gpu_handoff_domains_file)
        change(path)
        built = document.build(ctx, only={"trust"})
        equals("static_%s_state" % label, built["trust"]["ladder_state"], "unverified")
        equals("static_%s_names" % label, built["trust"]["unverified"], ["win11clean-valley"])
        equals("static_%s_claim" % label, trust_claim(built)["known"], False)

    broken("missing", lambda path: path.unlink())
    broken("writable", lambda path: path.chmod(0o666))
    broken("duplicate", lambda path: path.write_text(
        "win11clean-valley clean\nwin11clean-valley clean\n"))
    broken("extra_field", lambda path: path.write_text("win11clean-valley clean extra\n"))
    broken("bad_profile", lambda path: path.write_text("win11clean-valley Clean\n"))
    broken("bad_name", lambda path: path.write_text("Win11 clean\n"))

    def redirect(path):
        real = path.with_name("real-domains")
        path.rename(real)
        path.symlink_to(real)
    broken("symlink", redirect)

    def directory(path):
        path.unlink()
        path.mkdir()
    broken("directory", directory)


def test_a_duplicate_across_policy_surfaces_is_unknown_not_recorded():
    # The hook refuses every prepare when both surfaces name one domain.
    ctx = _holder("win11clean-valley", trust=3,
                  installed_managed={"win11clean-valley": "clean"})
    built = document.build(ctx, only={"trust"})
    equals("collision_static_holder_state", built["trust"]["ladder_state"], "unverified")
    equals("collision_claim_unknown", trust_claim(built)["known"], False)
    equals("collision_field", waybar_field(built, "trust")["text"], "?")
    ctx = _holder("dev-01", installed_managed={"dev-01": "dev", "win11clean-valley": "clean"})
    equals("collision_managed_holder", observe_pci_holders(ctx)["state"], "unverified")


def test_a_static_holder_with_an_unusable_managed_surface_is_unknown():
    for label, change in (
        ("missing", lambda path: (path.rmdir())),
        ("writable", lambda path: path.chmod(0o777)),
        ("corrupt", lambda path: (path / "x-1.conf").write_text("y-1 dev\n")),
    ):
        ctx = _holder("win11clean-valley", trust=3)
        change(Path(ctx.config.gpu_handoff_managed_dir))
        built = document.build(ctx, only={"trust"})
        equals("managed_%s_static_holder" % label, built["trust"]["ladder_state"], "unverified")
    ctx = _holder("win11clean-valley", trust=3)
    with mock.patch(MANAGED, return_value=({}, "unavailable")):
        equals("managed_unavailable_static_holder", observe_pci_holders(ctx)["state"],
               "unverified")


def test_unmapped_holder_makes_the_ladder_unknown_and_names_it():
    built = document.build(_holder("rogue-tmp", trust=3, installed_managed={"dev-01": "dev"}))
    trust = built["trust"]
    equals("outside_state", trust["ladder_state"], "outside-policy")
    equals("outside_names", trust["outside_policy"], ["rogue-tmp"])
    equals("outside_cannot_ascend", trust["can_ascend"], False)
    equals("outside_claim", trust_claim(built), {"known": False, "claimed": False,
                                                 "identity": None, "level": None,
                                                 "ladder": "outside-policy"})
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
    code, output = _run(["--json", "doctor"], _holder("rogue-tmp", trust=2))
    entries = [entry for entry in json.loads(output) if entry["id"] == "trust.gpu_outside_policy"]
    equals("doctor_outside_exit", code, 2)
    equals("doctor_outside_count", len(entries), 1)
    check("doctor_outside_names", "rogue-tmp" in entries[0]["message"], entries)
    check("doctor_outside_remedy", "reboot" in (entries[0]["remedy"] or ""), entries)


def test_an_unreadable_rung_does_not_hide_an_outside_holder():
    for label, error, trust in (
        ("permission", PermissionError(errno.EACCES, "Permission denied"), 2),
        ("io", OSError(errno.EIO, "Input/output error"), 2),
        ("nonnumeric", None, "garbage"),
    ):
        ctx = _holder("rogue-tmp", trust=trust)
        reading = _failing_read(ctx, error) if error else mock.patch.object(
            Path, "read_text", Path.read_text)
        with reading:
            built = document.build(ctx)
            code, output = _run(["--json", "doctor"], _holder("rogue-tmp", trust=trust))
        trust_section = built["trust"]
        check("rung_%s_section_kept" % label, trust_section is not None, built["problems"])
        equals("rung_%s_state" % label, trust_section["ladder_state"], "outside-policy")
        equals("rung_%s_no_rung" % label, (trust_section["claimed"], trust_section["level"]),
               (None, None))
        equals("rung_%s_claim" % label, trust_claim(built)["ladder"], "outside-policy")
        check("rung_%s_read_failure_kept" % label,
              any(p["id"] == "hyperlab.unavailable" and p["provider"] == "trust"
                  for p in built["problems"]), built["problems"])
        check("rung_%s_named_error" % label,
              any(p["id"] == "trust.gpu_outside_policy" and "rogue-tmp" in p["message"]
                  for p in built["problems"]), built["problems"])
        check("rung_%s_reboot" % label,
              "unknown, reboot to reset" in waybar_field(built, "trust")["tooltip"])
        if label == "nonnumeric":
            equals("rung_doctor_exit", code, 2)
            check("rung_doctor_named", any(e["id"] == "trust.gpu_outside_policy"
                                           for e in json.loads(output)), output)
    # Without an outside holder, an unreadable rung is still an unreadable
    # section: unknown, never unclaimed.
    ctx = world.build(trust=2)
    with _failing_read(ctx, OSError(errno.EIO, "Input/output error")):
        built = document.build(ctx, only={"trust"})
    equals("rung_unreadable_alone_section", built["trust"], None)


def test_trust_command_refuses_to_list_reachable_levels_for_an_outside_holder():
    code, output = _run(["--json", "trust"], _holder("rogue-tmp", trust=None))
    payload = json.loads(output)
    equals("trust_outside_rc", code, 1)
    equals("trust_outside_known", payload["known"], False)
    equals("trust_outside_ladder", payload["ladder"], [])
    equals("trust_outside_state", payload["ladder_state"], "outside-policy")


def test_an_unclaimed_boot_with_an_outside_holder_cannot_rise():
    # Unclaimed is the only state from which a rung may rise; an outside
    # holder has used the GPU anyway, so nothing is reachable any more.
    built = document.build(_holder("rogue-tmp", trust=None), only={"trust"})
    equals("unclaimed_outside_cannot_ascend", built["trust"]["can_ascend"], False)
    equals("unclaimed_outside_claim_known", trust_claim(built)["known"], False)


def test_a_paused_holder_still_holds_the_device():
    built = document.build(_holder("rogue-tmp", state="paused"), only={"trust"})
    equals("paused_outside", built["trust"]["outside_policy"], ["rogue-tmp"])


def test_a_stopped_unmapped_definition_holds_nothing():
    built = document.build(_holder("rogue-tmp", state="shut off"), only={"trust"})
    equals("stopped_recorded", built["trust"]["ladder_state"], "recorded")


def test_no_holder_keeps_the_recorded_rung():
    ctx = world.build(domains=[{"name": "debian-dev", "state": "running", "memory_mb": 1024,
                                "network": "dev"}], trust=2)
    built = document.build(ctx, only={"trust"})
    equals("no_holder_state", built["trust"]["ladder_state"], "recorded")
    equals("no_holder_lists", (built["trust"]["outside_policy"], built["trust"]["unverified"]),
           ([], []))
    equals("no_holder_claim_level", trust_claim(built)["level"], 2)


def test_no_holder_never_reads_the_installed_policy():
    ctx = world.build(domains=[{"name": "debian-dev", "state": "running", "memory_mb": 1024,
                                "network": "dev"}], trust=2)
    Path(ctx.config.gpu_handoff_domains_file).unlink()
    built = document.build(ctx, only={"trust"})
    equals("no_holder_policy_unread", built["trust"]["ladder_state"], "recorded")


def test_no_domain_at_all_is_unclaimed():
    built = document.build(world.build(domains=[], trust=None), only={"trust"})
    equals("empty_claim", trust_claim(built),
           {"known": True, "claimed": False, "identity": None, "level": None,
            "ladder": "recorded"})


def test_unreadable_live_xml_is_unknown_not_clean():
    ctx = world.build(domains=[{"name": "debian-dev", "state": "running", "memory_mb": 1024,
                                "network": "dev"}], trust=3)
    ctx.runner.register(_virsh(ctx) + ["dumpxml", "debian-dev"], (1, "", "error: permission"))
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
    built = document.build(ctx, only={"trust"})
    equals("malformed_state", built["trust"]["ladder_state"], "unverified")
    equals("malformed_claim_known", trust_claim(built)["known"], False)


def test_a_live_xml_for_another_identity_is_unknown_and_the_scan_goes_on():
    for label, body in (
        ("wrong_root", "<network><name>%s</name><hostdev type='pci'/></network>"),
        ("missing_name", "<domain type='kvm'><devices/></domain>"),
        ("duplicate_name", "<domain type='kvm'><name>%s</name><name>%s</name><devices/></domain>"),
        ("other_name", "<domain type='kvm'><name>win11clean-valley</name><devices/></domain>"),
        ("nested_name", "<domain type='kvm'><devices><name>%s</name></devices></domain>"),
    ):
        ctx = world.build(domains=[
            {"name": "debian-dev", "state": "running", "memory_mb": 1024},
            {"name": "rogue-tmp", "state": "running", "memory_mb": 1024, "vfio": True},
        ], trust=2)
        ctx.runner.register(_virsh(ctx) + ["dumpxml", "debian-dev"],
                            body.replace("%s", "debian-dev"))
        built = document.build(ctx, only={"trust"})
        trust = built["trust"]
        equals("identity_%s_unknown" % label, trust["unverified"], ["debian-dev"])
        equals("identity_%s_scan_continues" % label, trust["outside_policy"], ["rogue-tmp"])
        equals("identity_%s_state" % label, trust["ladder_state"], "outside-policy")


def test_an_unlisted_inventory_is_unknown_not_clean():
    ctx = world.build(domains=[], trust=None)
    ctx.runner.register(_virsh(ctx) + ["list", "--all", "--name"], (1, "", "error: denied"))
    built = document.build(ctx, only={"trust"})
    equals("unlisted_state", built["trust"]["ladder_state"], "unverified")
    equals("unlisted_claim_known", trust_claim(built)["known"], False)
    equals("unlisted_problem", _ids(built), ["trust.gpu_holders_unverified"])


def test_every_device_shape_counts_and_only_the_live_xml_is_read():
    for label, devices in (
        ("pci", "<hostdev mode='subsystem' type='pci'/>"),
        ("interface", "<interface type='hostdev'><source><address type='pci'/></source>"
                      "</interface>"),
    ):
        ctx = _holder("rogue-tmp")
        _live(ctx, "rogue-tmp", devices)
        built = document.build(ctx, only={"trust"})
        equals("shape_%s_outside" % label, built["trust"]["outside_policy"], ["rogue-tmp"])
        reads = [call for call in ctx.runner.calls if "dumpxml" in call]
        check("shape_%s_live_read" % label, reads and all("--inactive" not in call for call in reads),
              reads)


def test_a_qemu_extension_without_a_device_is_unknown_not_a_holder():
    # The prepare preflight refuses this domain, but a running one may carry
    # any argument: its device effects are unknown, never a confirmed holder.
    for label, extension in (
        ("environment", "<q:commandline><q:env name='TZ' value='UTC'/></q:commandline>"),
        ("arguments", "<q:commandline><q:arg value='-device'/>"
                      "<q:arg value='vfio-pci,host=01:00.0'/></q:commandline>"),
    ):
        ctx = _holder("rogue-tmp")
        _live(ctx, "rogue-tmp", "", " xmlns:q='%s'" % QEMU, extension)
        built = document.build(ctx)
        trust = built["trust"]
        equals("extension_%s_state" % label, trust["ladder_state"], "unverified")
        equals("extension_%s_names" % label, (trust["outside_policy"], trust["unverified"]),
               ([], ["rogue-tmp"]))
        equals("extension_%s_problems" % label, _ids(built), ["trust.gpu_holders_unverified"])
        message = [p["message"] for p in built["problems"]
                   if p["id"] == "trust.gpu_holders_unverified"][0]
        check("extension_%s_reason" % label, "QEMU command-line" in message, message)
        check("extension_%s_no_reboot" % label,
              "reboot" not in REMEDIES["trust.gpu_holders_unverified"]
              and "reboot to reset" not in waybar_field(built, "trust")["tooltip"])
    # A device beside an extension is still a confirmed holder.
    ctx = _holder("rogue-tmp")
    _live(ctx, "rogue-tmp", "<hostdev type='pci'/>", " xmlns:q='%s'" % QEMU,
          "<q:commandline><q:env name='TZ' value='UTC'/></q:commandline>")
    equals("extension_with_device_outside",
           document.build(ctx, only={"trust"})["trust"]["outside_policy"], ["rogue-tmp"])
    # A mapped domain's extension is the reviewed Looking Glass block.
    ctx = _holder("win11clean-valley", trust=3)
    _live(ctx, "win11clean-valley", "<hostdev type='pci'/>", " xmlns:q='%s'" % QEMU,
          "<q:commandline><q:arg value='-device'/></q:commandline>")
    equals("extension_mapped_recorded",
           document.build(ctx, only={"trust"})["trust"]["ladder_state"], "recorded")


def test_mixed_holders_report_outside_policy_before_unknown():
    ctx = world.build(domains=[
        {"name": "rogue-tmp", "state": "running", "memory_mb": 1024, "vfio": True},
        {"name": "debian-dev", "state": "running", "memory_mb": 1024},
    ], trust=1)
    ctx.runner.register(_virsh(ctx) + ["dumpxml", "debian-dev"], (1, "", "error"))
    built = document.build(ctx, only={"trust"})
    trust = built["trust"]
    equals("mixed_state", trust["ladder_state"], "outside-policy")
    equals("mixed_lists", (trust["outside_policy"], trust["unverified"]),
           (["rogue-tmp"], ["debian-dev"]))
    equals("mixed_problems", _ids(built), ["trust.gpu_holders_unverified",
                                           "trust.gpu_outside_policy"])


def test_an_unknown_domain_state_with_passthrough_is_unknown():
    built = document.build(_holder("rogue-tmp", state="unknown"), only={"trust"})
    equals("unknown_state_holder", built["trust"]["ladder_state"], "unverified")


def test_a_managed_only_domain_is_not_called_unguarded():
    # Named only in domains.d, without product Machine metadata: the hook
    # guards it, so doctor must not ask for a static entry (which would make
    # the duplicate the hook refuses). The metadata gap is reported apart.
    ctx = _holder("svc-gpu", trust=2, installed_managed={"svc-gpu": "dev"})
    code, output = _run(["--json", "doctor"], ctx)
    entries = json.loads(output)
    ids = sorted(entry["id"] for entry in entries)
    check("managed_only_not_unguarded", "domains.unguarded_vfio" not in ids, ids)
    check("managed_only_no_static_remedy",
          not any("gpu_domain_profiles" in (entry["remedy"] or "") for entry in entries), entries)
    check("managed_only_metadata_reported",
          "domains.gpu_policy_without_product_metadata" in ids, ids)
    check("managed_only_trust_clean", not [i for i in ids if i.startswith("trust.")], ids)
    built = document.build(_holder("svc-gpu", trust=2, installed_managed={"svc-gpu": "dev"}))
    equals("managed_only_recorded", built["trust"]["ladder_state"], "recorded")
    # Absent from both installed surfaces it is still unguarded.
    built = document.build(_holder("rogue-tmp", trust=2))
    check("absent_still_unguarded", "domains.unguarded_vfio" in _ids(built, "domains."))


def test_a_section_without_ladder_state_is_never_known():
    for label, section in (
        ("missing", {"claimed": True, "name": "dev", "level": 2}),
        ("other", {"claimed": True, "name": "dev", "level": 2, "ladder_state": "clean"}),
    ):
        equals("ladder_%s_unknown" % label, trust_claim({"trust": section})["known"], False)
