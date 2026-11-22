"""Shared libvirt reads. Cached on the context, so five providers cost one call."""

import xml.etree.ElementTree as ET

from .domainxml import parse_domain
from .errors import HyperlabError, Unavailable


def _names(result, what):
    if result.rc == 127:
        raise Unavailable("virsh is not installed on this host")
    if not result.ok:
        raise Unavailable("virsh could not list %s: %s" % (what, result.stderr.strip()))
    return result.lines()


def domain_names(ctx):
    return _names(ctx.virsh("list", "--all", "--name"), "domains")


def network_names(ctx, active_only=False):
    args = ["net-list", "--name"] if active_only else ["net-list", "--all", "--name"]
    return _names(ctx.virsh(*args), "networks")


def _bridge_networks(ctx) -> dict[str, str] | None:
    """Every libvirt network's bridge -> its name, from net-dumpxml; None
    when any network cannot be read."""

    try:
        names = network_names(ctx)
    except HyperlabError:
        return None

    if len(names) != len(set(names)):
        return None

    bridges: dict[str, str] = {}

    for name in names:
        result = ctx.virsh("net-dumpxml", name)

        if not result.ok:
            return None

        try:
            root = ET.fromstring(result.stdout)
        except ET.ParseError:
            return None

        bridge = root.find("bridge")

        if root.tag != "network" or len(root.findall("name")) != 1 or root.findtext("name") != name:
            return None

        if len(root.findall("bridge")) > 1:
            return None
        if bridge is not None:
            bridge_name = bridge.get("name")
            if not bridge_name or bridge_name in bridges:
                return None
            bridges[bridge_name] = name

    return bridges


def bridge_networks(ctx) -> dict[str, str] | None:
    if "inventory.bridges" not in ctx.cache:
        ctx.cache["inventory.bridges"] = _bridge_networks(ctx)
    return ctx.cache["inventory.bridges"]


def domain_state(ctx, name):
    result = ctx.virsh("domstate", name)
    if not result.ok:
        return "unknown"
    return (result.stdout.strip() or "unknown").lower()


def domain_detail(ctx, name):
    result = ctx.virsh("dumpxml", name)
    if not result.ok:
        raise Unavailable("dumpxml failed for %s" % name)
    detail = parse_domain(result.stdout)
    detail["name"] = detail["name"] or name
    detail["state"] = domain_state(ctx, name)
    return detail


def domains(ctx):
    if "inventory.domains" not in ctx.cache:
        collected = []
        for name in domain_names(ctx):
            try:
                collected.append(domain_detail(ctx, name))
            except Unavailable:
                collected.append(
                    # None is not []: an unreadable domain has unknown
                    # networks, while [] means the domain really declares none.
                    # Likewise managed/vfio are unknown here, not False: an
                    # unreadable domain is neither external nor VFIO-free.
                    {"name": name, "state": "unknown", "memory_mb": None,
                     "vcpus": None,
                     "networks": None, "hostdevs": [], "vfio": None,
                     "passthrough": None,
                     "managed": None, "product_managed": None,
                     "image": None, "image_sha256": None,
                     "device_profile": None, "lifecycle": None,
                     "network_profile": None, "gpu_handoff_profile": None}
                )
        ctx.cache["inventory.domains"] = collected
    return ctx.cache["inventory.domains"]


def running(ctx):
    return [domain for domain in domains(ctx) if domain["state"] == "running"]
