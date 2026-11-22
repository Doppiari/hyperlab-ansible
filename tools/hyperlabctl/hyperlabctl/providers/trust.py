"""Where the GPU sits on the trust ladder inside this boot.

The hook writes one number to /run/gpu-handoff/trust. No file means the GPU was
never claimed since boot, which is the only state from which anything can rise.

The hook sees only prepares. `ladder_state` says whether that record still
describes the GPU: "recorded" when every live domain was read and none holds a
passthrough device outside the GPU policy, "outside-policy" when one does (only
a reboot resets the GPU then), "unverified" when that could not be read.
"""

from ..errors import Missing, Unavailable
from .base import Provider
from .domains import observe_pci_holders


class TrustProvider(Provider):
    key = "trust"
    order = 20
    summary = "current GPU trust level and whether it can still rise"

    def collect(self, ctx):
        levels = ctx.config.var("gpu_trust_levels", {}) or {}
        try:
            raw = ctx.read_text(ctx.config.gpu_handoff_state).strip()
        except Missing:
            # Only genuine absence means "never claimed since boot". A
            # permission or I/O failure propagates as Unavailable: the section
            # becomes null, a problem is recorded, and every renderer reports
            # the claim as unknown instead of affirming "unclaimed".
            section = {"level": None, "name": None, "claimed": False, "can_ascend": True,
                       "ladder": levels}
        else:
            try:
                level = int(raw)
            except ValueError as exc:
                raise Unavailable("trust state %r is not a number" % raw) from exc
            name = next((key for key, value in levels.items() if value == level), None)
            section = {"level": level, "name": name, "claimed": True, "can_ascend": False,
                       "ladder": levels}
        holders = observe_pci_holders(ctx)
        section["ladder_state"] = holders["state"]
        section["outside_policy"] = holders["outside_policy"]
        section["unverified"] = holders["unverified"]
        if holders["state"] != "recorded":
            section["can_ascend"] = False
        return section

    def problems(self, ctx, section):
        found = []
        if section and section.get("claimed") and section.get("name") is None:
            found.append({
                "id": "trust.level_unmapped",
                "severity": "error",
                "message": "trust level %s matches no entry in gpu_trust_levels"
                           % section["level"],
            })
        for name in (section or {}).get("outside_policy") or []:
            found.append({
                "id": "trust.gpu_outside_policy",
                "severity": "error",
                "message": "%s holds a passthrough device but is in neither "
                           "gpu_domain_profiles nor the managed GPU policy: the "
                           "recorded rung no longer describes the GPU; GPU state "
                           "unknown, reboot to reset" % name,
            })
        if section and (section.get("unverified")
                        or section.get("ladder_state") == "unverified"):
            unread = section.get("unverified") or []
            found.append({
                "id": "trust.gpu_holders_unverified",
                "severity": "error",
                "message": "could not read %s: whether a domain outside the GPU "
                           "policy holds a passthrough device is unknown"
                           % (", ".join(unread) + " (live XML, state or GPU policy)"
                              if unread else "the libvirt domain list"),
            })
        return found
