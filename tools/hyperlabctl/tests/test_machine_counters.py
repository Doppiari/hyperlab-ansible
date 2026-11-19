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
STATS = VIRSH + ["domstats", "--cpu-total", "--interface"]

DOMAIN = """<domain type='kvm'>
  <name>{name}</name>
  <vcpu placement='static'>4</vcpu>
  <devices>
    {interfaces}
  </devices>
</domain>"""

INTERFACE = ("<interface type='network'><source network='{network}' bridge='virbr-{network}'/>"
             "<target dev='{tap}'/></interface>")


def _row(name, state="running", networks=("dev",), vcpus=4):
    return {"name": name, "state": state, "networks": list(networks) if networks is not None else None,
            "vcpus": vcpus}


def _ctx(stats=None, domains=None):
    runner = RecordedRunner()
    for name, interfaces in (domains or {}).items():
        runner.register(VIRSH + ["dumpxml", name], DOMAIN.format(
            name=name, interfaces="".join(INTERFACE.format(network=network, tap=tap)
                                          for tap, network in interfaces)))
    for argv, value in (stats or {}).items():
        runner.register(STATS + list(argv), value)
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


def test_counters_are_raw_libvirt_values_with_one_sample_time():
    ctx, runner = _ctx({("dev-01", "dirty-web"): DEV_STATS},
                       {"dev-01": [("vnet3", "dev")], "dirty-web": [("vnet7", "dirty")]})
    rows = [_row("dev-01"), _row("dirty-web", networks=("dirty",), vcpus=2),
            _row("dev-02", state="shut off"), _row("lab-01", state="shut off", networks=("lab",))]
    counters = machine.runtime_counters(ctx, rows, clock=_clock(100, 300))
    equals("counters_available", counters["available"], True)
    equals("sample_is_the_midpoint_of_the_read", counters["sampled_ns"], 200)
    equals("cpu_counters", counters["machines"],
           {"dev-01": {"cpu_time_ns": 5000000000, "vcpus": 4},
            "dirty-web": {"cpu_time_ns": 70, "vcpus": 2}})
    equals("network_counters", counters["networks"], {
        "dev": {"rx_bytes": 1000, "tx_bytes": 250, "interfaces": ["dev-01/vnet3"]},
        "dirty": {"rx_bytes": 5, "tx_bytes": 6, "interfaces": ["dirty-web/vnet7"]},
        # A network with no running interface moves nothing: a known zero.
        "lab": {"rx_bytes": 0, "tx_bytes": 0, "interfaces": []},
    })
    equals("one_stats_read_for_running_machines_only",
           [call for call in runner.calls if "domstats" in call],
           [tuple(STATS + ["dev-01", "dirty-web"])])
    # Read-only: the only libvirt verbs are the statistics and the definitions.
    equals("only_read_verbs", {call[len(VIRSH)] for call in runner.calls}, {"domstats", "dumpxml"})


def test_nothing_running_reads_no_statistics():
    ctx, runner = _ctx()
    counters = machine.runtime_counters(ctx, [_row("dev-02", state="shut off")], clock=_clock(7, 9))
    equals("idle_available", counters["available"], True)
    equals("idle_machines", counters["machines"], {})
    equals("idle_networks", counters["networks"], {"dev": {"rx_bytes": 0, "tx_bytes": 0, "interfaces": []}})
    equals("idle_no_virsh", runner.calls, [])


def test_a_failed_read_is_unavailable_never_zero():
    ctx, _ = _ctx({("dev-01",): Result([], 1, "", "error: failed to connect")}, {"dev-01": [("vnet3", "dev")]})
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
        ctx, _ = _ctx({("dev-01",): text}, {"dev-01": [("vnet3", "dev")]})
        counters = machine.runtime_counters(ctx, [_row("dev-01")], clock=_clock(1, 2))
        equals("unparsable_%s" % name, counters["available"], False)


def test_a_missing_counter_leaves_that_fact_unknown():
    stats = "Domain: 'dev-01'\n  net.count=1\n  net.0.name=vnet3\n  net.0.rx.bytes=1\n"
    ctx, _ = _ctx({("dev-01",): stats}, {"dev-01": [("vnet3", "dev")]})
    counters = machine.runtime_counters(ctx, [_row("dev-01")], clock=_clock(1, 2))
    equals("missing_cpu_absent", counters["machines"], {})
    # tx.bytes is missing: the network's total is unknown, not rx alone.
    equals("missing_tx_network_absent", counters["networks"], {})


def test_an_interface_without_a_network_makes_its_networks_unknown():
    stats = ("Domain: 'dev-01'\n  cpu.time=9\n  net.count=1\n  net.0.name=vnet9\n"
             "  net.0.rx.bytes=1\n  net.0.tx.bytes=2\n")
    ctx, _ = _ctx({("dev-01",): stats}, {"dev-01": [("vnet3", "dev")]})
    counters = machine.runtime_counters(ctx, [_row("dev-01")], clock=_clock(1, 2))
    equals("unmapped_cpu_still_known", counters["machines"], {"dev-01": {"cpu_time_ns": 9, "vcpus": 4}})
    equals("unmapped_network_unknown", counters["networks"], {})


def test_a_machine_without_a_vcpu_count_has_no_load_counter():
    ctx, _ = _ctx({("dev-01",): "Domain: 'dev-01'\n  cpu.time=9\n  net.count=0\n"}, {"dev-01": []})
    counters = machine.runtime_counters(ctx, [_row("dev-01", vcpus=None)], clock=_clock(1, 2))
    equals("no_vcpus_no_load", counters["machines"], {})
    equals("no_interfaces_network_zero", counters["networks"],
           {"dev": {"rx_bytes": 0, "tx_bytes": 0, "interfaces": []}})


def test_a_running_machine_absent_from_the_answer_is_unknown():
    ctx, _ = _ctx({("dev-01", "dev-02"): "Domain: 'dev-01'\n  cpu.time=9\n  net.count=0\n"},
                  {"dev-01": [], "dev-02": [("vnet4", "dev")]})
    counters = machine.runtime_counters(ctx, [_row("dev-01"), _row("dev-02")], clock=_clock(1, 2))
    equals("absent_machine_cpu", sorted(counters["machines"]), ["dev-01"])
    equals("absent_machine_network", counters["networks"], {})


def test_inventory_json_carries_counters_and_leaves_rows_alone():
    rows = [dict(_row("dev-01"), provenance="dev", runtime_present=True)]
    payload = {"text": "1/1", "class": "ok", "tooltip": "1 product Machine", "machines_available": True,
               "runtime_available": True, "machines": rows}
    ctx, _ = _ctx({("dev-01",): DEV_STATS.split("\n\n")[0] + "\n"}, {"dev-01": [("vnet3", "dev")]})
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

