"""Raw runtime counters in `machine inventory --json`, read-only and stateless.

The shell turns two consecutive samples into a load and a traffic rate; here
only the raw libvirt counters and their sample time are read. Whatever cannot
be read is left out, never written as zero.
"""

import io
import json
import tempfile
from contextlib import redirect_stdout

from harness import check, equals
from hyperlabctl.commands import machine
from hyperlabctl.config import Config, Context
from hyperlabctl.runner import RecordedRunner, Result

VIRSH = ["/usr/bin/virsh", "-c", "qemu:///system", "-q"]
STATS = VIRSH + ["domstats", "--raw", "--cpu-total", "--interface", "--list-active"]

DOMAIN = """<domain type='kvm'>
  <name>{name}</name>
  <vcpu placement='static'>4</vcpu>
  <devices>
    {interfaces}
  </devices>
</domain>"""

INTERFACE = ("<interface type='network'><source network='{network}' bridge='virbr-{network}'/>"
             "<target dev='{tap}'/></interface>")
BRIDGED = "<interface type='bridge'><source bridge='{bridge}'/><target dev='{tap}'/></interface>"
USER = "<interface type='user'><target dev='{tap}'/></interface>"
NETWORK = "<network><name>{name}</name><bridge name='virbr-{name}' stp='on'/></network>"


def _row(name, state="running", networks=("dev",), vcpus=4):
    return {"name": name, "state": state, "networks": list(networks) if networks is not None else None,
            "vcpus": vcpus}


def _ctx(stats="", domains=None, xml=None, networks=None):
    """`domains`: name -> [(tap, network)]; `xml`: name -> raw interface XML
    or a Result; `networks`: the libvirt networks net-dumpxml knows."""
    runner = RecordedRunner()
    for name, interfaces in (domains or {}).items():
        runner.register(VIRSH + ["dumpxml", name], DOMAIN.format(
            name=name, interfaces="".join(INTERFACE.format(network=network, tap=tap)
                                          for tap, network in interfaces)))
    for name, value in (xml or {}).items():
        runner.register(VIRSH + ["dumpxml", name],
                        value if isinstance(value, Result) else DOMAIN.format(name=name, interfaces=value))
    if networks is not None:
        runner.register(VIRSH + ["net-list", "--all", "--name"], "\n".join(networks) + "\n")
        for name in networks:
            runner.register(VIRSH + ["net-dumpxml", name], NETWORK.format(name=name))
    runner.register(STATS, stats)
    return Context(Config(repo_root=tempfile.gettempdir(), read_files=False), runner), runner


def _clock(*values):
    ticks = iter(values)
    return lambda: next(ticks)


DEV_STATS = """Domain: 'dev-01'
  cpu.time=5000000000
  cpu.user=3000000000
  cpu.system=2000000000
  net.count=1
  net.0.name=vnet3
  net.0.rx.bytes=1000
  net.0.rx.pkts=10
  net.0.tx.bytes=250
  net.0.tx.pkts=4

Domain: 'dirty-web'
  cpu.time=70
  net.count=1
  net.0.name=vnet7
  net.0.rx.bytes=5
  net.0.tx.bytes=6

"""

EXTERNAL_STATS = """Domain: 'hand-made'
  cpu.time=40
  net.count=1
  net.0.name=vnet9
  net.0.rx.bytes=300
  net.0.tx.bytes=30

"""


def test_counters_are_raw_libvirt_values_with_one_sample_time():
    ctx, runner = _ctx(DEV_STATS, {"dev-01": [("vnet3", "dev")], "dirty-web": [("vnet7", "dirty")]})
    rows = [_row("dev-01"), _row("dirty-web", networks=("dirty",), vcpus=2),
            _row("dev-02", state="shut off"), _row("lab-01", state="shut off", networks=("lab",))]
    counters = machine.runtime_counters(ctx, rows, clock=_clock(100, 300))
    equals("counters_available", counters["available"], True)
    equals("sample_is_the_midpoint_of_the_read", counters["sampled_ns"], 200)
    equals("cpu_counters", counters["machines"],
           {"dev-01": {"cpu_time_ns": 5000000000, "vcpus": 4},
            "dirty-web": {"cpu_time_ns": 70, "vcpus": 2}})
    # lab has no active interface: nothing was observed there, so it is
    # left out (unknown), never a zero.
    equals("network_counters", counters["networks"], {
        "dev": {"rx_bytes": 1000, "tx_bytes": 250, "interfaces": ["dev-01/vnet3"]},
        "dirty": {"rx_bytes": 5, "tx_bytes": 6, "interfaces": ["dirty-web/vnet7"]},
    })
    equals("one_raw_stats_read_for_every_active_domain",
           [call for call in runner.calls if "domstats" in call], [tuple(STATS)])
    # Read-only: the only libvirt verbs are the statistics and the definitions.
    equals("only_read_verbs", {call[len(VIRSH)] for call in runner.calls}, {"domstats", "dumpxml"})


def test_an_unmanaged_domain_counts_toward_its_network():
    ctx, _ = _ctx(DEV_STATS.split("\n\n")[0] + "\n\n" + EXTERNAL_STATS,
                  {"dev-01": [("vnet3", "dev")], "hand-made": [("vnet9", "dev")]})
    counters = machine.runtime_counters(ctx, [_row("dev-01")], clock=_clock(1, 2))
    equals("unmanaged_traffic_counted", counters["networks"],
           {"dev": {"rx_bytes": 1300, "tx_bytes": 280, "interfaces": ["dev-01/vnet3", "hand-made/vnet9"]}})
    equals("unmanaged_has_no_load", sorted(counters["machines"]), ["dev-01"])


def test_a_bridged_interface_counts_toward_the_network_owning_the_bridge():
    ctx, runner = _ctx(EXTERNAL_STATS, xml={"hand-made": BRIDGED.format(bridge="virbr-dev", tap="vnet9")},
                       networks=["dev", "lab"])
    counters = machine.runtime_counters(ctx, [], clock=_clock(1, 2))
    equals("bridged_traffic_counted", counters["networks"],
           {"dev": {"rx_bytes": 300, "tx_bytes": 30, "interfaces": ["hand-made/vnet9"]}})
    check("bridged_read_network_bridges", tuple(VIRSH + ["net-dumpxml", "dev"]) in runner.calls)


def test_a_bridge_no_network_owns_carries_no_listed_traffic():
    ctx, _ = _ctx(DEV_STATS.split("\n\n")[0] + "\n\n" + EXTERNAL_STATS,
                  {"dev-01": [("vnet3", "dev")]},
                  xml={"hand-made": BRIDGED.format(bridge="br0", tap="vnet9")}, networks=["dev"])
    counters = machine.runtime_counters(ctx, [_row("dev-01")], clock=_clock(1, 2))
    equals("foreign_bridge_skipped", sorted(counters["networks"]), ["dev"])
    equals("foreign_bridge_dev_alone", counters["networks"]["dev"]["interfaces"], ["dev-01/vnet3"])


def test_unreadable_bridges_leave_every_network_unknown():
    ctx, _ = _ctx(DEV_STATS.split("\n\n")[0] + "\n\n" + EXTERNAL_STATS,
                  {"dev-01": [("vnet3", "dev")]},
                  xml={"hand-made": BRIDGED.format(bridge="virbr-dev", tap="vnet9")})
    ctx.runner.register(VIRSH + ["net-list", "--all", "--name"], Result([], 1, "", "error"))
    counters = machine.runtime_counters(ctx, [_row("dev-01")], clock=_clock(1, 2))
    equals("unreadable_bridges_networks", counters["networks"], {})
    equals("unreadable_bridges_cpu_kept", sorted(counters["machines"]), ["dev-01"])


def test_an_interface_on_no_network_is_skipped():
    ctx, _ = _ctx(EXTERNAL_STATS, xml={"hand-made": USER.format(tap="vnet9")})
    counters = machine.runtime_counters(ctx, [], clock=_clock(1, 2))
    equals("userspace_interface_available", counters["available"], True)
    equals("userspace_interface_skipped", counters["networks"], {})


def test_an_unreadable_unmanaged_domain_leaves_every_network_unknown():
    ctx, _ = _ctx(DEV_STATS.split("\n\n")[0] + "\n\n" + EXTERNAL_STATS,
                  {"dev-01": [("vnet3", "dev")]}, xml={"hand-made": Result([], 1, "", "error")})
    counters = machine.runtime_counters(ctx, [_row("dev-01")], clock=_clock(1, 2))
    equals("unreadable_unmanaged_networks", counters["networks"], {})


def test_nothing_active_reads_one_empty_answer():
    ctx, runner = _ctx("")
    counters = machine.runtime_counters(ctx, [_row("dev-02", state="shut off")], clock=_clock(7, 9))
    equals("idle_available", counters["available"], True)
    equals("idle_machines", counters["machines"], {})
    equals("idle_networks", counters["networks"], {})
    equals("idle_one_read", runner.calls, [tuple(STATS)])


def test_a_failed_read_is_unavailable_never_zero():
    ctx, _ = _ctx(Result([], 1, "", "error: failed to connect"), {"dev-01": [("vnet3", "dev")]})
    counters = machine.runtime_counters(ctx, [_row("dev-01")], clock=_clock(1, 2))
    equals("failed_unavailable", counters["available"], False)
    check("failed_has_no_counters", "machines" not in counters and "networks" not in counters)


def test_unparsable_output_is_unavailable():
    for name, text in (("no_header", "  cpu.time=5\n"),
                       ("bad_number", "Domain: 'dev-01'\n  cpu.time=five\n"),
                       ("negative", "Domain: 'dev-01'\n  cpu.time=-5\n"),
                       ("duplicate_domain", "Domain: 'dev-01'\n  cpu.time=5\nDomain: 'dev-01'\n  cpu.time=6\n"),
                       ("duplicate_field", "Domain: 'dev-01'\n  cpu.time=5\n  cpu.time=6\n"),
                       ("stray_line", "Domain: 'dev-01'\ncpu.time=5\n")):
        ctx, _ = _ctx(text, {"dev-01": [("vnet3", "dev")]})
        counters = machine.runtime_counters(ctx, [_row("dev-01")], clock=_clock(1, 2))
        equals("unparsable_%s" % name, counters["available"], False)


def test_a_missing_counter_leaves_that_fact_unknown():
    stats = "Domain: 'dev-01'\n  net.count=1\n  net.0.name=vnet3\n  net.0.rx.bytes=1\n"
    ctx, _ = _ctx(stats, {"dev-01": [("vnet3", "dev")]})
    counters = machine.runtime_counters(ctx, [_row("dev-01")], clock=_clock(1, 2))
    equals("missing_cpu_absent", counters["machines"], {})
    # tx.bytes is missing: the network's total is unknown, not rx alone.
    equals("missing_tx_network_absent", counters["networks"], {})


def test_an_interface_without_a_network_makes_its_networks_unknown():
    # vnet3 is placed on dev, vnet9 is in no definition: dev's total would
    # miss vnet9's bytes, so dev is unknown, not vnet3 alone.
    stats = ("Domain: 'dev-01'\n  cpu.time=9\n  net.count=2\n  net.0.name=vnet3\n"
             "  net.0.rx.bytes=1\n  net.0.tx.bytes=2\n  net.1.name=vnet9\n"
             "  net.1.rx.bytes=3\n  net.1.tx.bytes=4\n")
    ctx, _ = _ctx(stats, {"dev-01": [("vnet3", "dev")]})
    counters = machine.runtime_counters(ctx, [_row("dev-01")], clock=_clock(1, 2))
    equals("unmapped_cpu_still_known", counters["machines"], {"dev-01": {"cpu_time_ns": 9, "vcpus": 4}})
    equals("unmapped_network_unknown", counters["networks"], {})


def test_a_machine_without_a_vcpu_count_has_no_load_counter():
    ctx, _ = _ctx("Domain: 'dev-01'\n  cpu.time=9\n  net.count=0\n", {"dev-01": []})
    counters = machine.runtime_counters(ctx, [_row("dev-01", vcpus=None)], clock=_clock(1, 2))
    equals("no_vcpus_no_load", counters["machines"], {})
    equals("no_interfaces_no_network", counters["networks"], {})


def test_a_running_machine_absent_from_the_answer_is_unknown():
    stats = ("Domain: 'dev-01'\n  cpu.time=9\n  net.count=1\n  net.0.name=vnet3\n"
             "  net.0.rx.bytes=1\n  net.0.tx.bytes=2\n")
    ctx, _ = _ctx(stats, {"dev-01": [("vnet3", "dev")], "dev-02": [("vnet4", "dev")]})
    counters = machine.runtime_counters(ctx, [_row("dev-01"), _row("dev-02")], clock=_clock(1, 2))
    equals("absent_machine_cpu", sorted(counters["machines"]), ["dev-01"])
    equals("absent_machine_network", counters["networks"], {})


def test_inventory_json_carries_counters_and_leaves_rows_alone():
    rows = [dict(_row("dev-01"), provenance="dev", runtime_present=True)]
    payload = {"text": "1/1", "class": "ok", "tooltip": "1 product Machine", "machines_available": True,
               "runtime_available": True, "machines": rows}
    ctx, _ = _ctx(DEV_STATS.split("\n\n")[0] + "\n", {"dev-01": [("vnet3", "dev")]})
    original = machine.build_product_inventory
    machine.build_product_inventory = lambda _ctx: json.loads(json.dumps(payload))
    try:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = machine.MachineCommand()._inventory(type("Args", (), {"json": True})(), ctx)
    finally:
        machine.build_product_inventory = original
    printed = json.loads(buffer.getvalue())
    equals("inventory_exit", code, 0)
    equals("inventory_rows_unchanged", printed["machines"], rows)
    equals("inventory_counter", printed["counters"]["machines"]["dev-01"]["cpu_time_ns"], 5000000000)
    check("inventory_sampled", isinstance(printed["counters"]["sampled_ns"], int))


def test_an_unavailable_runtime_reads_no_counters():
    ctx, runner = _ctx()
    payload = {"machines_available": True, "runtime_available": False,
               "machines": [_row("dev-01", state="runtime-unavailable", networks=None)]}
    original = machine.build_product_inventory
    machine.build_product_inventory = lambda _ctx: payload
    try:
        with redirect_stdout(io.StringIO()) as buffer:
            machine.MachineCommand()._inventory(type("Args", (), {"json": True})(), ctx)
    finally:
        machine.build_product_inventory = original
    equals("runtime_unavailable_counters", json.loads(buffer.getvalue())["counters"], {"available": False})
    equals("runtime_unavailable_no_virsh", runner.calls, [])

