"""The read commands, end to end through argparse with a fake host."""

import io
import json
from contextlib import redirect_stdout

import world
from harness import check, equals
from hyperlabctl.cli import main

DOMAINS = [{"name": "win11clean-valley", "state": "running", "memory_mb": 6144, "vfio": True},
           {"name": "debian-dev", "state": "shut off", "memory_mb": 1024, "network": "dev"}]


def _run(argv, ctx):
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = main(argv, ctx=ctx)
    return code, buffer.getvalue()


def test_net_list_reports_every_declared_domain():
    code, output = _run(["--json", "net", "list"], world.build(trust=None))
    rows = json.loads(output)
    equals("net_row_count", len(rows), 5)
    equals("net_all_active", {row["state"] for row in rows}, {"active"})
    equals("net_exit", code, 0)


def test_net_list_marks_an_inactive_domain_and_keeps_its_trust():
    _, output = _run(["--json", "net", "list"],
                     world.build(trust=None, networks_active=["clean"]))
    rows = {row["name"]: row for row in json.loads(output)}
    equals("clean_active", rows["clean"]["state"], "active")
    equals("lab_inactive", rows["lab"]["state"], "inactive")
    equals("lab_trust", rows["lab"]["trust"], 0)


VIRSH = ["/usr/bin/virsh", "-c", "qemu:///system", "-q"]

NETWORK_XML = """<network>
  <name>{name}</name>
  <bridge name="virbr-{name}" stp="on" delay="0"/>
  {forward}
  <ip family="ipv6" address="fd00::1" prefix="64"/>
  <ip address="{gateway}" netmask="255.255.255.0">
    <dhcp>
      <range start="{prefix}.100" end="{prefix}.199"/>
    </dhcp>
  </ip>
</network>
"""


def _definitions(ctx, names=("clean", "dirty", "dev", "lab", "services")):
    numbers = {"clean": 1, "dirty": 2, "dev": 3, "lab": 4, "services": 5}
    for name in names:
        prefix = "10.10.%d" % numbers[name]
        ctx.runner.register(VIRSH + ["net-dumpxml", name], NETWORK_XML.format(
            name=name, gateway=prefix + ".1", prefix=prefix,
            forward="" if name == "lab" else '<forward mode="nat"/>'))
    return ctx


def test_net_list_reads_gateway_and_dhcp_from_the_live_definition():
    ctx = _definitions(world.build(trust=None))
    _, output = _run(["--json", "net", "list"], ctx)
    rows = {row["name"]: row for row in json.loads(output)}
    equals("lab_gateway", rows["lab"]["gateway"], "10.10.4.1")
    equals("lab_dhcp", rows["lab"]["dhcp"], {"start": "10.10.4.100", "end": "10.10.4.199"})
    equals("dev_gateway", rows["dev"]["gateway"], "10.10.3.1")
    equals("every_row_keys", {tuple(sorted(row)) for row in rows.values()},
           {("dhcp", "forward", "gateway", "name", "state", "subnet", "trust")})
    reads = [call[len(VIRSH):] for call in ctx.runner.calls if tuple(call[:len(VIRSH)]) == tuple(VIRSH)]
    check("net_list_reads_only", all(call[0] in ("net-list", "net-dumpxml") for call in reads), reads)
    equals("dumpxml_once_per_network", sorted(call[1] for call in reads if call[0] == "net-dumpxml"),
           ["clean", "dev", "dirty", "lab", "services"])


def test_net_list_says_none_when_the_definition_declares_none():
    ctx = _definitions(world.build(trust=None), names=("clean", "dirty", "dev", "services"))
    ctx.runner.register(VIRSH + ["net-dumpxml", "lab"],
                        "<network><name>lab</name><ip address='10.10.4.1'/></network>\n")
    ctx.runner.register(VIRSH + ["net-dumpxml", "dev"],
                        "<network><name>dev</name><ip family='ipv6' address='fd00::1'/></network>\n")
    _, output = _run(["--json", "net", "list"], ctx)
    rows = {row["name"]: row for row in json.loads(output)}
    equals("no_dhcp_is_false", rows["lab"]["dhcp"], False)
    equals("gateway_without_dhcp", rows["lab"]["gateway"], "10.10.4.1")
    equals("no_ipv4_gateway_is_false", rows["dev"]["gateway"], False)
    equals("no_ipv4_dhcp_is_false", rows["dev"]["dhcp"], False)


def test_net_list_never_guesses_an_unread_definition():
    ctx = _definitions(world.build(trust=None, networks_active=["clean", "dev", "dirty", "services"]),
                       names=("clean", "dirty"))
    ctx.runner.register(VIRSH + ["net-dumpxml", "dev"], (1, "", "error: failed to get network 'dev'"))
    ctx.runner.register(VIRSH + ["net-dumpxml", "services"], "<network><ip address='10.10.5.1'>")
    ctx.runner.register(VIRSH + ["net-dumpxml", "lab"],
                        "<network><name>dev</name><ip address='10.10.3.1'/></network>\n")
    _, output = _run(["--json", "net", "list"], ctx)
    rows = {row["name"]: row for row in json.loads(output)}
    for name in ("dev", "services", "lab"):
        equals(name + "_gateway_unknown", rows[name]["gateway"], None)
        equals(name + "_dhcp_unknown", rows[name]["dhcp"], None)
    equals("clean_still_read", rows["clean"]["gateway"], "10.10.1.1")


def test_net_list_reads_no_definition_for_a_missing_network():
    ctx = world.build(trust=None)
    ctx.runner.register(VIRSH + ["net-list", "--all", "--name"], "clean\n")
    ctx.runner.register(VIRSH + ["net-list", "--name"], "clean\n")
    _definitions(ctx, names=("clean",))
    _, output = _run(["--json", "net", "list"], ctx)
    rows = {row["name"]: row for row in json.loads(output)}
    equals("missing_state", rows["lab"]["state"], "missing")
    equals("missing_gateway", rows["lab"]["gateway"], None)
    equals("missing_dhcp", rows["lab"]["dhcp"], None)
    check("no_dumpxml_for_missing",
          not any(call[-2:] == ("net-dumpxml", "lab") for call in ctx.runner.calls))


def test_net_start_calls_net_start_not_define():
    ctx = world.build(trust=None)
    ctx.runner.register(["/usr/bin/virsh", "-c", "qemu:///system", "-q", "net-start", "lab"],
                        "Network lab started\n")
    code, _ = _run(["net", "start", "lab"], ctx)
    equals("net_start_exit", code, 0)
    check("net_start_called",
          any(call[-2:] == ("net-start", "lab") for call in ctx.runner.calls))


def test_image_list_reports_the_manifest_and_its_sealing_state():
    _, output = _run(["--json", "image", "list"], world.build(trust=None))
    images = json.loads(output)
    equals("image_count", len(images), 1)
    equals("image_status", images[0]["status"], "not-built")
    equals("image_has_no_checksum", images[0]["sha256"], False)


def test_trust_reports_every_level_as_reachable_when_unclaimed():
    _, output = _run(["--json", "trust"], world.build(trust=None))
    payload = json.loads(output)
    equals("unclaimed", payload["claimed"], False)
    check("all_reachable", all(row["reachable"] for row in payload["ladder"]))


def test_trust_reports_unknown_when_the_state_cannot_be_read():
    import errno
    from pathlib import Path
    from unittest import mock

    ctx = world.build(trust=2)
    target = str(ctx.config.gpu_handoff_state)
    real = Path.read_text

    def read_text(self, *args, **kwargs):
        if str(self) == target:
            raise OSError(errno.EIO, "Input/output error")
        return real(self, *args, **kwargs)

    with mock.patch.object(Path, "read_text", read_text):
        code, output = _run(["--json", "trust"], ctx)
    payload = json.loads(output)
    equals("unreadable_rc", code, 1)
    equals("unreadable_claimed", payload["claimed"], None)
    equals("unreadable_known", payload["known"], False)
    equals("unreadable_no_reachable_levels", payload["ladder"], [])


def test_trust_closes_the_levels_above_the_current_one():
    _, output = _run(["--json", "trust"], world.build(trust=1))
    ladder = {row["name"]: row for row in json.loads(output)["ladder"]}
    equals("clean_closed", ladder["clean"]["reachable"], False)
    equals("dev_closed", ladder["dev"]["reachable"], False)
    equals("dirty_current", ladder["dirty"]["current"], True)
    equals("lab_still_reachable", ladder["lab"]["reachable"], True)


def test_schema_lists_every_registered_section():
    from hyperlabctl.providers import REGISTRY
    _, output = _run(["--json", "schema"], world.build(trust=None))
    payload = json.loads(output)
    equals("schema_version", payload["schema_version"], 1)
    equals("schema_sections", len(payload["sections"]), len(REGISTRY))


def test_completion_names_every_subcommand_that_exists():
    from hyperlabctl.commands import REGISTRY
    _, output = _run(["completion"], world.build(trust=None))
    for name in REGISTRY:
        check("completion_offers_%s" % name, name in output)


def test_watch_emits_one_line_per_cycle_and_stops_when_told():
    ctx = world.build(domains=DOMAINS, trust=3)
    _, output = _run(["watch", "--field", "trust", "--max-cycles", "2"], ctx)
    lines = [line for line in output.splitlines() if line.strip()]
    equals("watch_line_count", len(lines), 2)
    equals("watch_payload", json.loads(lines[0])["text"], "clean 3")


def test_watch_blocks_on_libvirt_instead_of_sleeping():
    ctx = world.build(domains=DOMAINS, trust=3)
    _run(["watch", "--max-cycles", "2"], ctx)
    check("watch_used_virsh_event",
          any("event" in call for call in ctx.runner.calls))


def test_doctor_prints_a_fix_for_every_problem_it_reports():
    _, output = _run(["--json", "doctor"], world.build(trust=None, profile_report=False))
    for entry in json.loads(output):
        check("doctor_fix_for_%s" % entry["id"], entry["remedy"] is not None)


def test_watch_gives_up_when_virsh_is_missing_instead_of_spinning():
    """An unregistered command returns 127 from RecordedRunner, which is exactly
    what a host without virsh looks like. The loop must stop, not spin."""
    ctx = world.build(domains=DOMAINS, trust=3)
    for call in list(ctx.runner.table):
        if "event" in call:
            del ctx.runner.table[call]
    code, output = _run(["watch", "--max-cycles", "3"], ctx)
    lines = [line for line in output.splitlines() if line.strip()]
    equals("watch_bailed", code, 2)
    equals("watch_emitted_once_before_bailing", len(lines), 1)


def test_a_sealed_image_without_a_checksum_is_an_error():
    ctx = world.build(trust=None, images={
        "arch": "---\nname: arch\nvirtual_size_gib: 10\nstatus: sealed\n"})
    _, output = _run(["--json", "status"], ctx)
    problems = json.loads(output)["problems"]
    check("sealed_without_checksum_flagged",
          any(p["id"] == "images.sealed_without_checksum" and p["severity"] == "error"
              for p in problems))


def test_a_sealed_image_with_a_checksum_raises_nothing():
    ctx = world.build(trust=None, images={
        "arch": "---\nname: arch\nvirtual_size_gib: 10\nstatus: sealed\n"
                "sha256: abc123\nsource_url: https://example.invalid/a.qcow2\n"})
    _, output = _run(["--json", "status"], ctx)
    problems = json.loads(output)["problems"]
    check("sealed_with_checksum_quiet",
          not any(p["id"] == "images.sealed_without_checksum" for p in problems))


def test_watch_gives_virsh_the_full_heartbeat_window():
    ctx = world.build(domains=DOMAINS, trust=3)
    _run(["watch", "--max-cycles", "2", "--heartbeat", "60"], ctx)
    timeout = next(value for call, value in zip(ctx.runner.calls, ctx.runner.timeouts)
                   if "event" in call)
    equals("watch_runner_timeout", timeout, 65)


def test_watch_stops_on_a_real_libvirt_error_instead_of_spinning():
    from hyperlabctl.runner import Result
    ctx = world.build(domains=DOMAINS, trust=3)
    argv = ("/usr/bin/virsh", "-c", "qemu:///system", "-q",
            "event", "--all", "--timeout", "60")
    ctx.runner.register(argv, Result(argv, 1, "", "failed to connect"))
    code, output = _run(["watch", "--max-cycles", "3"], ctx)
    equals("watch_real_error_exit", code, 2)
    equals("watch_real_error_single_emit", len(output.splitlines()), 1)

def test_vm_inventory_refuses_an_unreviewed_spec():
    ctx = world.build(trust=None)
    (ctx.config.repo_root / "vm-specs").mkdir(exist_ok=True)
    code, _ = _run(["vm", "inventory", "../../escape.yml"], ctx)
    equals("inventory_unreviewed_spec_exit", code, 2)
