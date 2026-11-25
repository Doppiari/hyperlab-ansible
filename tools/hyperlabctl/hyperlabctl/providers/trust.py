"""Where the GPU sits on the trust ladder inside this boot.

The hook writes one number to /run/gpu-handoff/trust. No file means the GPU was
never claimed since boot, which is the only state from which anything can rise.

The hook sees only prepares. `ladder_state` says whether that record still
describes the GPU: "recorded" when every live domain was read and none holds a
passthrough device outside the installed GPU policy, "outside-policy" when one
does (only a reboot resets the GPU then), "unverified" when that could not be
read. The holders are observed whether or not the record itself is readable.
"""

from ..errors import HyperlabError, Missing, Unavailable
from .base import Provider
from .domains import observe_pci_holders


def _read_rung(ctx, levels):
    try:
        raw = ctx.read_text(ctx.config.gpu_handoff_state).strip()
    except Missing:
        # Only genuine absence means "never claimed since boot".
        return {"level": None, "name": None, "claimed": False, "can_ascend": True,
                "ladder": levels}
    try:
        level = int(raw)
    except ValueError as exc:
        raise Unavailable("trust state %r is not a number" % raw) from exc
    name = next((key for key, value in levels.items() if value == level), None)
    return {"level": level, "name": name, "claimed": True, "can_ascend": False,
            "ladder": levels}


class TrustProvider(Provider):
    key = "trust"
    order = 20
    summary = "current GPU trust level and whether it can still rise"

    def collect(self, ctx):
        levels = ctx.config.var("gpu_trust_levels", {}) or {}
        holders = observe_pci_holders(ctx)
        try:
            section = _read_rung(ctx, levels)
        except HyperlabError as exc:
            # A permission or I/O failure, or a nonnumeric record, leaves the
            # section null: every renderer reports the claim as unknown
            # instead of affirming "unclaimed". A confirmed outside holder is
            # the exception: it must still be named and still read "reboot to
            # reset", so the section survives without a rung and keeps the
            # read failure as its own problem.
            if holders["state"] != "outside-policy":
                raise
            section = {"level": None, "name": None, "claimed": None, "can_ascend": False,
                       "ladder": levels,
                       "rung_error": {"id": exc.problem_id, "severity": exc.severity,
                                      "message": str(exc)}}
        section["ladder_state"] = holders["state"]
        section["outside_policy"] = holders["outside_policy"]
        section["unverified"] = holders["unverified"]
        section["unverified_reasons"] = holders["reasons"]
        if holders["state"] != "recorded":
            section["can_ascend"] = False
        return section

    def problems(self, ctx, section):
        found = []
        if not section:
            return found
        if section.get("rung_error"):
            found.append(dict(section["rung_error"]))
        if section.get("claimed") and section.get("name") is None:
            found.append({
                "id": "trust.level_unmapped",
                "severity": "error",
                "message": "trust level %s matches no entry in gpu_trust_levels"
                           % section["level"],
            })
        for name in section.get("outside_policy") or []:
            found.append({
                "id": "trust.gpu_outside_policy",
                "severity": "error",
                "message": "%s holds a PCI passthrough device but is in neither the "
                           "installed static GPU policy nor domains.d: the recorded "
                           "rung no longer describes the GPU; GPU state unknown, "
                           "reboot to reset" % name,
            })
        reasons = section.get("unverified_reasons") or {}
        for name in section.get("unverified") or []:
            found.append({
                "id": "trust.gpu_holders_unverified",
                "severity": "error",
                "message": "whether %s holds a passthrough device outside the GPU "
                           "policy is unknown: %s"
                           % (name, reasons.get(name, "it could not be read")),
            })
        if section.get("ladder_state") == "unverified" and not section.get("unverified"):
            found.append({
                "id": "trust.gpu_holders_unverified",
                "severity": "error",
                "message": "the libvirt domain list could not be read: whether a domain "
                           "outside the GPU policy holds a passthrough device is unknown",
            })
        return found
