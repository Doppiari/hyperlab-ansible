"""Every domain, and for the stopped ones the reason they cannot start.

`blocked` is the point of this provider. A VM manager tells you a domain is off;
this tells you it is off and short 1.9 GB, which is the difference between a
panel and a list.
"""

import errno
import os
import re
import stat
from pathlib import Path

from ..errors import HyperlabError, Unavailable
from ..inventory import bridge_networks
from ..inventory import domains as all_domains
from .base import Provider


def network_identity(domain, declared):
    """The network trust identity of a HyperLab-managed guest, or None.

    The reviewed guest role writes `network-profile` from the guest's spec
    into the libvirt metadata. It is believed only for a managed domain whose
    every interface is attached to exactly that declared network, so neither
    a stale record nor an unreadable domain can invent an identity.
    """
    if domain.get("managed") is not True:
        return None
    profile = domain.get("network_profile")
    networks = domain.get("networks")
    if profile not in declared or not networks:
        return None
    if any(network != profile for network in networks):
        return None
    return profile


def resolve_trust(domain, gpu_profiles, declared):
    """Resolve presentation identity without conflating GPU handoff policy.

    A managed guest's reviewed network profile owns its presentation identity.

    gpu_domain_profiles remains the host hardware handoff policy consumed by
    the root-owned VFIO hook. It may use a different reviewed contamination
    class without reclassifying the guest's network identity.

    Unmanaged legacy domains retain the historical GPU-profile fallback because
    they have no managed network-profile authority.
    """
    gpu = gpu_profiles.get(domain["name"])
    network = network_identity(domain, declared)

    if network is not None:
        return network, "network-profile"

    if domain.get("managed") is False and gpu is not None:
        return gpu, "gpu-domain-profile"

    return None, None


ROOT_POLICY_UID = 0
GPU_POLICY_MAX_BYTES = 4096
GPU_POLICY_NAME_RE = re.compile(
    r"^[a-z0-9][a-z0-9-]{1,30}$"
)


def observe_managed_gpu_policies(
    directory,
    trust_levels,
    *,
    expected_uid=ROOT_POLICY_UID,
):
    """Read the root-owned C10 policy surface without treating metadata as proof."""

    base = Path(
        directory
    )

    try:
        directory_info = base.lstat()
    except FileNotFoundError:
        return {}, "missing"
    except OSError:
        return {}, "unavailable"

    if (
        not stat.S_ISDIR(
            directory_info.st_mode
        )
        or stat.S_ISLNK(
            directory_info.st_mode
        )
        or directory_info.st_uid != expected_uid
        or stat.S_IMODE(
            directory_info.st_mode
        )
        != 0o755
    ):
        return {}, "unsafe"

    try:
        targets = sorted(
            base.glob(
                "*.conf"
            )
        )
    except OSError:
        return {}, "unavailable"

    result = {}

    for target in targets:
        try:
            info = target.lstat()
        except OSError:
            return {}, "unavailable"

        if (
            not stat.S_ISREG(
                info.st_mode
            )
            or stat.S_ISLNK(
                info.st_mode
            )
            or info.st_uid != expected_uid
            or stat.S_IMODE(
                info.st_mode
            )
            != 0o644
            or info.st_size > GPU_POLICY_MAX_BYTES
        ):
            return {}, "unsafe"

        filename = target.name

        if not filename.endswith(
            ".conf"
        ):
            return {}, "unsafe"

        expected_name = filename[:-5]

        if (
            GPU_POLICY_NAME_RE.fullmatch(
                expected_name
            )
            is None
        ):
            return {}, "unsafe"

        try:
            content = target.read_text(
                encoding="utf-8"
            )
        except UnicodeDecodeError:
            return {}, "unsafe"
        except OSError:
            return {}, "unavailable"

        entry = None

        for raw in content.splitlines():
            line = raw.strip()

            if (
                not line
                or line.startswith("#")
            ):
                continue

            parts = line.split()

            if (
                len(parts) != 2
                or entry is not None
            ):
                return {}, "unsafe"

            name, profile = parts

            if (
                name != expected_name
                or GPU_POLICY_NAME_RE.fullmatch(
                    name
                )
                is None
                or profile not in trust_levels
            ):
                return {}, "unsafe"

            entry = (
                name,
                profile,
            )

        if entry is None:
            return {}, "unsafe"

        name, profile = entry

        if name in result:
            return {}, "collision"

        result[name] = profile

    return result, "ok"


STATIC_POLICY_MAX_BYTES = 65536
HOOK_PROFILE_RE = re.compile(r"^[a-z]+$")


def observe_static_gpu_policy(path, *, expected_uid=ROOT_POLICY_UID):
    """Read the installed static policy the qemu hook reads, as it reads it.

    `/etc/gpu-handoff/domains`, not the checkout's gpu_domain_profiles: the
    two differ between a checkout update and a host apply. One line is
    `<domain> <profile>`; blank lines and `#` lines are skipped; anything
    else, a duplicate name, or an unsafe file is refused like the hook does.
    """
    target = Path(path)
    try:
        descriptor = os.open(target, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return {}, "missing"
    except OSError as exc:
        return {}, "unsafe" if exc.errno == errno.ELOOP else "unavailable"
    try:
        with os.fdopen(descriptor, "rb") as handle:
            info = os.fstat(handle.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != expected_uid
                or info.st_mode & 0o022
                or info.st_size > STATIC_POLICY_MAX_BYTES
            ):
                return {}, "unsafe"
            raw = handle.read(STATIC_POLICY_MAX_BYTES + 1)
    except OSError:
        return {}, "unavailable"
    if len(raw) > STATIC_POLICY_MAX_BYTES:
        return {}, "unsafe"
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {}, "unsafe"
    result = {}
    for line in content.splitlines():
        parts = line.split()
        if not parts or parts[0].startswith("#"):
            continue
        if (
            len(parts) != 2
            or GPU_POLICY_NAME_RE.fullmatch(parts[0]) is None
            or HOOK_PROFILE_RE.fullmatch(parts[1]) is None
        ):
            return {}, "unsafe"
        if parts[0] in result:
            return {}, "collision"
        result[parts[0]] = parts[1]
    return result, "ok"


def installed_gpu_policy(ctx):
    """Both policy surfaces the qemu hook reads, validated together.

    `state` is "ok" only when the static file and `domains.d` are both safe
    and readable and no domain is named by both (the hook refuses every
    prepare then). `mapping` is their union, empty unless the state is ok.
    """
    cache = getattr(ctx, "cache", None)
    if cache is not None and "gpu.installed_policy" in cache:
        return cache["gpu.installed_policy"]
    owner = getattr(ctx, "policy_owner_uid", ROOT_POLICY_UID)
    static, static_state = observe_static_gpu_policy(
        ctx.config.gpu_handoff_domains_file, expected_uid=owner)
    managed, managed_state = observe_managed_gpu_policies(
        ctx.config.gpu_handoff_managed_dir,
        ctx.config.var("gpu_trust_levels", {}) or {},
        expected_uid=owner,
    )
    if static_state != "ok":
        state = "static policy %s" % static_state
    elif managed_state != "ok":
        state = "managed policy %s" % managed_state
    elif set(static) & set(managed):
        state = "policy collision"
    else:
        state = "ok"
    policy = {
        "state": state,
        "static": static if state == "ok" else {},
        "managed": managed if state == "ok" else {},
        "mapping": {**static, **managed} if state == "ok" else {},
    }
    if cache is not None:
        cache["gpu.installed_policy"] = policy
    return policy


def observe_pci_holders(ctx):
    """Which live domains hold a passthrough device outside the GPU policy.

    The qemu hook decides only at prepare. A device attached to a running
    domain never reaches it, so the rung it recorded may be cleaner than the
    GPU's real history. This reads every domain's live XML (`virsh dumpxml`
    without `--inactive`, so attached devices are included) and compares
    each holder with the installed policy the hook reads: the static file
    and the root-owned domains.d, never the checkout.

    `state` is "recorded" only when every domain was read and no holder is
    outside policy. "outside-policy" names domains holding a PCI hostdev or
    a hostdev interface the hook would refuse; only a host reboot resets the
    GPU then. "unverified" means a domain, the domain list or the installed
    policy could not be read, or an unmapped domain carries a QEMU
    command-line extension whose device effects are unknown: unknown, never
    clean. `reasons` says why each unverified domain is unknown.
    """
    result = {"state": "recorded", "outside_policy": [], "unverified": [], "reasons": {}}

    def unknown(name, reason):
        result["unverified"].append(name)
        result["reasons"][name] = reason

    try:
        listed = all_domains(ctx)
    except HyperlabError:
        result["state"] = "unverified"
        return result

    policy = None
    for domain in listed:
        name = domain["name"]
        devices = domain.get("pci_devices")
        extension = domain.get("qemu_extension")
        if devices is None or extension is None:
            unknown(name, "its live XML could not be read")
            continue
        if not devices and not extension:
            continue
        if domain.get("state") == "shut off":
            continue
        if domain.get("state") == "unknown":
            unknown(name, "its state could not be read")
            continue
        if policy is None:
            policy = installed_gpu_policy(ctx)
        if policy["state"] != "ok":
            unknown(name, "the installed GPU policy is unusable (%s)" % policy["state"])
        elif name in policy["mapping"]:
            continue
        elif devices:
            result["outside_policy"].append(name)
        else:
            unknown(name, "it carries a QEMU command-line extension outside the GPU "
                          "policy, whose devices cannot be read")

    if result["outside_policy"]:
        result["state"] = "outside-policy"
    elif result["unverified"]:
        result["state"] = "unverified"
    return result


class DomainProvider(Provider):
    key = "domains"
    order = 60
    summary = "domains with state, allocation and why a stopped one is blocked"

    def collect(self, ctx):
        from .memory import budget
        try:
            available = budget(ctx)["assignable_mb"]
        except (Unavailable, KeyError):
            available = None

        profiles = ctx.config.var("gpu_domain_profiles", {}) or {}
        trust_levels = ctx.config.var("gpu_trust_levels", {}) or {}

        managed_policies, managed_policy_surface = (
            observe_managed_gpu_policies(
                ctx.config.gpu_handoff_managed_dir,
                trust_levels,
                expected_uid=getattr(ctx, "policy_owner_uid", ROOT_POLICY_UID),
            )
        )

        if managed_policy_surface == "ok":
            if set(managed_policies) & set(profiles):
                managed_policies = {}
                managed_policy_surface = "collision"

        declared = {entry.get("name") for entry in
                    ctx.config.var("network_domains", []) or []
                    if isinstance(entry, dict)}
        listed = []
        for domain in all_domains(ctx):
            running_now = domain["state"] == "running"
            blocked = None
            wanted = domain["memory_mb"]
            if not running_now and available is not None and wanted:
                if wanted > available:
                    blocked = {"reason": "memory",
                               "short_mb": wanted - available,
                               "available_mb": available}
            trust, source = resolve_trust(domain, profiles, declared)

            product_managed = (
                domain.get("product_managed") is True
            )

            requested_handoff = (
                domain.get("gpu_handoff_profile")
                if product_managed
                else profiles.get(domain["name"])
            )

            observed_handoff = profiles.get(
                domain["name"]
            )

            gpu_policy_state = (
                "legacy-static"
                if observed_handoff is not None
                else "not-configured"
            )

            if product_managed:
                dynamic_handoff = (
                    managed_policies.get(
                        domain["name"]
                    )
                    if managed_policy_surface == "ok"
                    else None
                )

                observed_handoff = dynamic_handoff

                if domain["vfio"]:
                    if managed_policy_surface != "ok":
                        gpu_policy_state = managed_policy_surface
                    elif requested_handoff is None:
                        gpu_policy_state = "metadata-missing"
                    elif dynamic_handoff is None:
                        gpu_policy_state = "missing"
                    elif dynamic_handoff != requested_handoff:
                        gpu_policy_state = "mismatch"
                    else:
                        gpu_policy_state = "verified"
                else:
                    gpu_policy_state = (
                        "unexpected"
                        if dynamic_handoff is not None
                        else "not-required"
                    )

            sources = domain.get("interface_sources", [])
            attachment = {}
            if any(kind == "bridge" for kind, _ in sources):
                owners = bridge_networks(ctx)
                resolved = [name if kind == "network" else (owners or {}).get(name) for kind, name in sources]
                attachment["attached_networks"] = resolved if None not in resolved else None

            listed.append({
                "name": domain["name"],
                "state": domain["state"],
                "memory_mb": wanted,
                "network": domain["networks"][0] if domain["networks"] else None,
                "networks": domain["networks"],
                **attachment,
                "vcpus": domain.get("vcpus"),
                "vfio": domain["vfio"],
                "managed": domain.get("managed"),
                "device_profile": domain.get("device_profile"),
                "lifecycle": domain.get("lifecycle"),
                "network_profile": domain.get("network_profile"),
                "image": domain.get("image"),
                "image_sha256": domain.get("image_sha256"),
                "product_managed": domain.get("product_managed"),
                # Requested policy from libvirt metadata for C10 Machines.
                # This is intent, never proof that the root hook will accept it.
                "gpu_handoff_profile": requested_handoff,
                # Observed effective policy. For product Machines this comes
                # from the root-owned domains.d surface, not from metadata.
                "gpu_trust_profile": observed_handoff,
                "gpu_policy_state": gpu_policy_state,
                "trust_profile": trust,
                "trust_source": source,
                "blocked": blocked,
            })
        return listed

    def problems(self, ctx, section):
        found = []
        for domain in section or []:
            gpu = domain.get("gpu_trust_profile")
            network = domain.get("network_profile")
            product_managed = (
                domain.get("product_managed") is True
            )
            policy_state = domain.get(
                "gpu_policy_state"
            )

            if product_managed:
                if (
                    domain["vfio"]
                    and policy_state != "verified"
                ):
                    found.append({
                        "id": "domains.gpu_policy_unverified",
                        "severity": "error",
                        "message": (
                            "%s requests GPU handoff profile %s but "
                            "the root-owned managed policy is %s"
                            % (
                                domain["name"],
                                domain.get("gpu_handoff_profile")
                                or "missing",
                                policy_state or "unknown",
                            )
                        ),
                    })

                if (
                    not domain["vfio"]
                    and policy_state == "unexpected"
                ):
                    found.append({
                        "id": "domains.gpu_policy_unexpected",
                        "severity": "error",
                        "message": (
                            "%s is a standard product Machine but "
                            "still has a root-owned GPU handoff policy"
                            % domain["name"]
                        ),
                    })

            elif domain["vfio"]:
                # Effective membership is what the hook reads: the installed
                # static file and domains.d. Only when that cannot be read
                # does the checkout's gpu_domain_profiles stand in.
                installed = installed_gpu_policy(ctx)
                if installed["state"] == "ok":
                    guarded = domain["name"] in installed["mapping"]
                else:
                    guarded = gpu is not None
                if not guarded:
                    found.append({
                        "id": "domains.unguarded_vfio",
                        "severity": "error",
                        "message": "%s owns a hostdev but is absent from the installed "
                                   "GPU policy (the static file and domains.d): the trust "
                                   "hook cannot guard it" % domain["name"],
                    })
                elif domain["name"] in installed["managed"]:
                    found.append({
                        "id": "domains.gpu_policy_without_product_metadata",
                        "severity": "warn",
                        "message": "%s is named by a root-owned managed GPU policy in "
                                   "domains.d but carries no product Machine metadata"
                                   % domain["name"],
                    })
            if not domain.get("managed"):
                continue
            if domain.get("trust_source") is None and network is not None:
                found.append({
                    "id": "domains.network_identity_mismatch",
                    "severity": "warn",
                    "message": "%s declares network %s but is attached to %s"
                               % (
                                   domain["name"],
                                   network,
                                   ", ".join(domain.get("networks") or [])
                                   or "no known network",
                               ),
                })
        return found
