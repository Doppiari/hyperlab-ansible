"""What the shell may offer when it creates a Machine, and how it is provisioned.

The creation plan is computed by the same factory code that writes the
Machine record, so the shell only shows limits the factory enforces. The
provisioning steps are the documented commands of docs/first-machine.md,
derived from one Machine record and its projected VM spec; the reviewed
provisioner runs them, never anything a caller supplies. See ADR 0017.

The provisioner leaves a receipt of every run below
$XDG_STATE_HOME/hyperlab/provisioning/; `provisioning_status` reads it, and
only a receipt that says every step of this record's plan ended with 0 reads
as provisioned. A missing, unreadable or foreign receipt reads "unknown",
anything else "incomplete", with the command that resumes the run.
"""

from __future__ import annotations

import base64
import binascii
import fcntl
import hashlib
import json
import os
import re
import shlex
import stat
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .errors import ContractError, HyperlabError, Unavailable
from .machine_factory import (
    MACHINE_ID_RE,
    _image,
    _repo_root,
    _resource_values,
    custom_limits,
    os_label,
    project_vm_spec,
    read_generated_spec,
    template_catalog,
)
from .machine_registry import _state_home, read_machine

# The one guest key of this host. Only the public half is ever read.
GUEST_KEY = Path(".ssh/hyperlab_ed25519.pub")
GUEST_KEY_LIMIT = 4096
KEY_RE = re.compile(r"^ssh-ed25519 (AAAAC3NzaC1lZDI1NTE5[A-Za-z0-9+/]+={0,2})(?: [^\r\n]*)?$")
# A key type is named in a refusal only when it looks like one.
KEY_TYPE_RE = re.compile(r"^[a-z0-9][a-z0-9@.-]{0,63}$")

# Reviewed profile playbooks. A Template whose workspace is not a server must
# have one here, or it is not offered for creation.
SERVER_WORKSPACE = "server"
PROFILE_PLAYBOOKS = {
    "workstation-dev": "playbooks/guest-arch-dev-vfio.yml",
    "workstation-dev-standard": "playbooks/guest-arch-dev.yml",
    "gaming-clean": "playbooks/guest-arch-gaming-clean.yml",
    "gaming-dirty": "playbooks/guest-arch-gaming-dirty.yml",
}

# Placeholder for the private hash file; the provisioner substitutes it.
ACCESS_FILE = "{access_file}"

# The steps of each kind of Machine, in order. A workstation ends by proving
# what the steps before it should have left: passwordless sudo gone and, for
# a VFIO Machine with Linux Looking Glass, a sender that reaches capture.
SERVER_STEP_IDS = ("create-domain", "inventory", "close-access")
WORKSTATION_STEP_IDS = ("create-domain", "inventory", "profile-first", "profile-second",
                        "close-access", "verify")


def guest_key(home: Path) -> dict[str, str]:
    """Validate the host's guest key; return its key line and fingerprint.

    Every refusal names what is wrong and never repeats the file's content.
    """
    path = Path(home) / GUEST_KEY
    if path.is_symlink():
        raise Unavailable(f"the guest key ~/{GUEST_KEY} is a symbolic link")
    if not path.is_file():
        raise Unavailable(f"the guest key ~/{GUEST_KEY} is missing")
    data = path.read_bytes()
    if len(data) > GUEST_KEY_LIMIT:
        raise ContractError(f"~/{GUEST_KEY} is too large to be one public key")
    text = data.decode("ascii", "replace")
    if "PRIVATE KEY" in text:
        raise ContractError(f"~/{GUEST_KEY} holds a private key; it must hold the public one")
    # Physical lines, blank ones included; only the final newline is not a line.
    lines = text.removesuffix("\n").split("\n")
    if not text.strip():
        raise ContractError(f"~/{GUEST_KEY} is empty")
    if len(lines) > 1:
        raise ContractError(f"~/{GUEST_KEY} holds {len(lines)} lines; it must hold exactly one public key")
    lines = [lines[0].strip()]
    kind = lines[0].split()[0]
    if kind != "ssh-ed25519":
        named = kind if KEY_TYPE_RE.fullmatch(kind) else "an unknown type"
        raise ContractError(f"~/{GUEST_KEY} is not an ed25519 key ({named})")
    match = KEY_RE.fullmatch(lines[0])
    if match is None:
        raise ContractError(f"~/{GUEST_KEY} is not one ssh-ed25519 public key line")
    try:
        blob = base64.b64decode(match.group(1), validate=True)
    except binascii.Error as exc:
        raise ContractError(f"~/{GUEST_KEY} is not valid base64") from exc
    if len(blob) != 51 or blob[4:15] != b"ssh-ed25519" or blob[15:19] != b"\x00\x00\x00\x20":
        raise ContractError(f"~/{GUEST_KEY} has the wrong ed25519 shape")
    fingerprint = base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")
    # The comment stays on the host: the guest gets type and key only.
    return {"path": f"~/{GUEST_KEY}", "line": f"ssh-ed25519 {match.group(1)}",
            "fingerprint": f"SHA256:{fingerprint}"}


def _provision(template_id: str, workspace: str) -> dict[str, Any]:
    if workspace == SERVER_WORKSPACE:
        return {"profile_playbook": None, "password": False}
    playbook = PROFILE_PLAYBOOKS.get(template_id)
    if playbook is None:
        return {"profile_playbook": None, "password": False,
                "blocked_reason": "no reviewed profile playbook for this Template"}
    return {"profile_playbook": playbook, "password": True}


def creation_plan(repo_root: Path | str, *, home: Path, cpu_count: int) -> dict[str, Any]:
    root = _repo_root(repo_root)
    if not isinstance(cpu_count, int) or cpu_count < 1:
        raise Unavailable("the host CPU count is unknown")

    try:
        key = guest_key(home)
        key_entry = {"available": True, "path": key["path"], "fingerprint": key["fingerprint"],
                     "reason": ""}
    except (Unavailable, ContractError, OSError) as exc:
        key_entry = {"available": False, "path": f"~/{GUEST_KEY}", "fingerprint": None,
                     "reason": str(exc)}

    templates = []
    for entry in template_catalog(root):
        if not entry["ready"]:
            continue
        image = _image(root, entry["image"]["id"])
        profiles = {}
        for profile in entry["resource_profiles"]:
            if profile != "custom":
                profiles[profile] = _resource_values(image, profile, memory_mb=None,
                                                     vcpus=None, disk_gib=None)
        custom = None
        if "custom" in entry["resource_profiles"]:
            # The same bounds the factory holds a custom request to.
            custom = custom_limits(image, cpu_count=cpu_count)
        provision = _provision(entry["id"], entry["presentation"]["workspace_profile"])
        blocked = provision.pop("blocked_reason", None)
        if blocked is None and not key_entry["available"]:
            blocked = key_entry["reason"]
        templates.append({
            "id": entry["id"],
            "display_name": entry["display_name"],
            "version": entry["version"],
            "image": entry["image"]["id"],
            # The same label the Machine cards show, from the manifest.
            "os": os_label(image),
            "lifecycles": entry["lifecycles"],
            "default_lifecycle": entry["defaults"]["lifecycle"],
            "device_capability": entry["defaults"]["device_capability"],
            "network_profiles": entry["network_profiles"],
            "default_network": entry["defaults"]["network_profile"],
            "resource_profiles": entry["resource_profiles"],
            "default_resource_profile": entry["defaults"]["resource_profile"],
            "profiles": profiles,
            "custom": custom,
            "looking_glass_mode": entry["presentation"]["looking_glass_mode"],
            "provision": provision,
            "creatable": blocked is None,
            "blocked_reason": blocked or "",
        })

    return {
        "schema": 1,
        "machine_id_pattern": MACHINE_ID_RE.pattern,
        "host": {"vcpus": cpu_count},
        "guest_key": key_entry,
        "templates": templates,
    }


def same_document(left: Any, right: Any) -> bool:
    """Equality that keeps YAML's scalar types.

    Plain equality takes true for 1, 0 for false and 2048.0 for 2048; the
    spec's readers do not, so neither does the projection comparison.
    """
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return ({(type(key), key) for key in left} == {(type(key), key) for key in right}
                and all(same_document(value, right[key]) for key, value in left.items()))
    if isinstance(left, list):
        return len(left) == len(right) and all(map(same_document, left, right))
    return left == right


def provision_steps(repo_root: Path | str, machine_id: str, *, home: Path,
                    runtime_dir: Path, state_home: Path | None = None) -> dict[str, Any]:
    """The documented commands for one created and projected Machine."""
    root = _repo_root(repo_root)
    if not isinstance(machine_id, str) or MACHINE_ID_RE.fullmatch(machine_id) is None:
        raise ContractError("invalid Machine id")
    record = read_machine(machine_id, state_home=state_home)
    spec = f"vm-specs/.generated/{machine_id}.yml"
    # The record is the authority and the spec only its projection: what
    # stands there must be exactly what the record projects to now. A link,
    # an unreadable or malformed file, or one edited by hand is refused
    # before any step, like a missing one.
    stored = read_generated_spec(root, machine_id)
    if stored is None:
        raise Unavailable(f"{machine_id} is not projected; run hyperlabctl machine project first")
    if not same_document(stored, project_vm_spec(root, record)):
        raise ContractError(f"{spec} differs from the projection of the Machine record {machine_id}")
    provision = _provision(record["template"]["id"], record["presentation"]["workspace_profile"])
    if "blocked_reason" in provision:
        raise ContractError(provision["blocked_reason"])
    key = guest_key(home)
    runtime = Path(runtime_dir)
    if not runtime.is_absolute():
        raise ContractError("the runtime directory must be absolute")
    inventory = str(runtime / f"{machine_id}.ini")

    steps = [
        {"id": "create-domain", "label": "Create and start the domain",
         "password": False,
         "argv": ["ansible-playbook", "playbooks/vm-create.yml", "-K",
                  "-e", f"guest_spec={spec}", "-e", "guest_start_after_create=true",
                  "-e", json.dumps({"guest_cloud_init_ssh_public_keys": [key["line"]]},
                                   separators=(",", ":"))]},
        {"id": "inventory", "label": "Publish the inventory and pin the SSH host key",
         "password": False,
         "argv": ["ansible-playbook", "playbooks/vm-guest-inventory.yml", "-K",
                  "-e", f"guest_spec={spec}"]},
    ]
    playbook = provision["profile_playbook"]
    if playbook is not None:
        profile = ["ansible-playbook", "-i", "inventory.ini", "-i", inventory, playbook]
        steps.append({"id": "profile-first", "label": "Apply the profile and set the password",
                      "password": True, "argv": [*profile, "-e", "@" + ACCESS_FILE]})
        steps.append({"id": "profile-second", "label": "Apply the profile again (expect no changes)",
                      "password": False, "argv": profile})
    # Once the host key is pinned and the profile has run: restrict the guest
    # agent, and end passwordless sudo when the account has a password.
    steps.append({"id": "close-access",
                  "label": "Restrict the guest agent and end passwordless sudo",
                  "password": False,
                  "argv": ["ansible-playbook", "-i", "inventory.ini", "-i", inventory,
                           "playbooks/guest-close-access.yml"]})
    if playbook is not None:
        steps.append({"id": "verify", "label": verify_label(record), "password": False,
                      "argv": ["hyperlabctl", "machine", "verify-provisioning", machine_id]})
    return {"schema": 1, "machine": machine_id, "spec": spec, "steps": steps}


def step_ids(record: dict[str, Any]) -> list[str] | None:
    """The ids of the steps this record's Template calls for, or None when
    it has no reviewed provisioning."""
    provision = _provision(record["template"]["id"], record["presentation"]["workspace_profile"])
    if "blocked_reason" in provision:
        return None
    return list(WORKSTATION_STEP_IDS if provision["profile_playbook"] else SERVER_STEP_IDS)


def looking_glass_proof(record: dict[str, Any]) -> bool:
    """Whether the final step must see the Linux Looking Glass sender capture."""
    return (record["device_capability"] == "vfio"
            and record["presentation"]["looking_glass_mode"] == "linux-experimental")


def verify_label(record: dict[str, Any]) -> str:
    if looking_glass_proof(record):
        return "Prove sudo asks for the password and Looking Glass reaches capture"
    return "Prove sudo asks for the password"


# ------------------------------------------------------------- the receipt
#
# Written only by privatestack-machine-provision, which cannot import this
# module; a contract keeps the two layouts equal.

RECEIPT_SCHEMA = 1
RECEIPT_LIMIT = 256 * 1024
RECEIPT_KEYS = {"schema", "machine", "record_sha256", "state", "started_at", "ended_at",
                "from_step", "reason", "steps"}
RECEIPT_STEP_KEYS = {"id", "label", "result", "exit"}
RECEIPT_STATES = ("running", "finished", "failed", "interrupted")
STEP_RESULTS = ("pending", "running", "ok", "failed", "interrupted")
# The result the first unfinished step may have in each state of the run.
UNFINISHED_RESULT = {"running": ("running", "pending"), "failed": ("failed",),
                     "interrupted": ("interrupted", "pending")}
PROVISIONER = "privatestack-machine-provision"
TIME_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


def receipt_directory(state_home: Path | None = None) -> Path:
    return _state_home(state_home) / "hyperlab" / "provisioning"


def _owned_directory(path: Path, *, exact_mode: int | None = None) -> bool:
    """True for a real directory of this user; False when it is absent."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
            or (exact_mode is not None and stat.S_IMODE(info.st_mode) != exact_mode)):
        raise Unavailable(f"{path} is not a private directory of this user")
    return True


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    keys = [key for key, _value in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("a key is repeated")
    return dict(pairs)


def _integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def receipt_problem(document: Any, machine_id: str) -> str:
    """Why a parsed receipt cannot be read, or "" when it holds."""
    if not isinstance(document, dict) or set(document) != RECEIPT_KEYS:
        return "the receipt does not have the receipt fields"
    if document["schema"] != RECEIPT_SCHEMA or not _integer(document["schema"]):
        return "the receipt has another schema"
    if document["machine"] != machine_id:
        return "the receipt names another Machine"
    state, steps = document["state"], document["steps"]
    if (not isinstance(document["record_sha256"], str)
            or DIGEST_RE.fullmatch(document["record_sha256"]) is None
            or state not in RECEIPT_STATES
            or not isinstance(document["started_at"], str) or TIME_RE.fullmatch(document["started_at"]) is None
            or (document["ended_at"] is not None if state == "running"
                else not isinstance(document["ended_at"], str)
                or TIME_RE.fullmatch(document["ended_at"]) is None)
            or not isinstance(document["reason"], str) or len(document["reason"]) > 1000
            or not _integer(document["from_step"])
            or not isinstance(steps, list) or not steps):
        return "the receipt has an invalid field"
    for step in steps:
        if (not isinstance(step, dict) or set(step) != RECEIPT_STEP_KEYS
                or not isinstance(step["id"], str) or not isinstance(step["label"], str)
                or step["result"] not in STEP_RESULTS
                or not (step["exit"] is None or _integer(step["exit"]))):
            return "the receipt has an invalid step"
        if step["result"] == "ok" and step["exit"] != 0:
            return "a step reads ok without exit status 0"
        if step["result"] in ("pending", "running") and step["exit"] is not None:
            return "a step that has not ended has an exit status"
        if step["result"] == "failed" and step["exit"] == 0:
            return "a failed step has exit status 0"
    results = [step["result"] for step in steps]
    unfinished = next((index for index, result in enumerate(results) if result != "ok"), None)
    if state == "finished":
        return "" if unfinished is None else "a finished receipt has a step that did not end with 0"
    if (unfinished is None or results[unfinished] not in UNFINISHED_RESULT[state]
            or any(result != "pending" for result in results[unfinished + 1:])):
        return f"the steps of a {state} receipt are out of order"
    if not 1 <= document["from_step"] <= unfinished + 1:
        return "the receipt resumed after a step that had not ended with 0"
    return ""


def read_receipt(machine_id: str, *, state_home: Path | None = None) -> tuple[dict[str, Any] | None, str]:
    """The receipt and "", (None, "missing") or (None, why it is unreadable)."""
    try:
        directory = receipt_directory(state_home)
        if not (_owned_directory(directory.parent) and _owned_directory(directory, exact_mode=0o700)):
            return None, "missing"
        path = directory / f"{machine_id}.json"
        try:
            info = path.lstat()
        except FileNotFoundError:
            return None, "missing"
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > RECEIPT_LIMIT):
            return None, "the receipt is not a private regular file of this user"
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        with os.fdopen(descriptor, "rb") as stream:
            data = stream.read(RECEIPT_LIMIT + 1)
        document = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)
    except (HyperlabError, OSError, UnicodeDecodeError, ValueError) as exc:
        return None, f"the receipt cannot be read ({exc})"
    problem = receipt_problem(document, machine_id)
    return (None, problem) if problem else (document, "")


def provisioning_running(machine_id: str, *, state_home: Path | None = None) -> bool | None:
    """Whether a provisioner holds this Machine's lock now; None if unknown."""
    try:
        path = receipt_directory(state_home) / f"{machine_id}.lock"
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except FileNotFoundError:
        return False
    except (HyperlabError, OSError):
        return None
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            return None
        try:
            fcntl.flock(descriptor, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        except OSError:
            return None
        return False
    finally:
        os.close(descriptor)


def resume_command(machine_id: str, step: int, repo_root: Path | str | None) -> str:
    """The command that runs this Machine's provisioning again from `step`."""
    command = f"{PROVISIONER} {machine_id}" + (f" --from {step}" if step > 1 else "")
    return f"cd {shlex.quote(str(repo_root))} && {command}" if repo_root is not None else command


def provisioning_status(record: dict[str, Any], *, record_sha256: str, state_home: Path | None = None,
                        repo_root: Path | str | None = None) -> dict[str, Any]:
    """What the receipt says about this record's provisioning.

    Only "finished" means provisioned. Nothing here raises for a receipt:
    whatever cannot be read reads "unknown".
    """
    machine_id = record["id"]
    expected = step_ids(record)
    try:
        log: Path | None = receipt_directory(state_home) / f"{machine_id}.log"
        if not stat.S_ISREG(log.lstat().st_mode):
            log = None
    except (HyperlabError, OSError):
        log = None
    status: dict[str, Any] = {
        "status": "unknown", "receipt": "missing", "record_sha256": record_sha256,
        "step": None, "steps": len(expected) if expected else None, "label": None,
        "step_ids": expected, "running": False, "text": "Provisioning unknown",
        "resume": resume_command(machine_id, 1, repo_root) if expected else None,
        "log": str(log) if log is not None else None, "reason": "",
    }
    if expected is None:
        status.update(receipt="unreadable", reason="this Template has no reviewed provisioning")
        return status
    receipt, problem = read_receipt(machine_id, state_home=state_home)
    if receipt is None:
        status.update(receipt="missing" if problem == "missing" else "unreadable",
                      reason=("no provisioning receipt: provisioned before receipts existed, "
                              "or never provisioned") if problem == "missing" else problem)
        return status
    if receipt["record_sha256"] != record_sha256:
        status.update(receipt="stale", reason="the receipt belongs to another Machine record of this name")
        return status
    if [step["id"] for step in receipt["steps"]] != expected:
        status.update(receipt="stale", reason="the receipt's steps are not the ones this Machine calls for")
        return status
    if receipt["state"] == "finished":
        status.update(status="finished", receipt="finished", text="Provisioned", resume=None)
        return status
    index = next(index for index, step in enumerate(receipt["steps"]) if step["result"] != "ok")
    step = receipt["steps"][index]
    state = receipt["state"]
    reason = receipt["reason"]
    if state == "running":
        running = provisioning_running(machine_id, state_home=state_home)
        if running is None:
            status.update(receipt="unreadable", reason="the provisioning lock cannot be read")
            return status
        if running:
            status.update(status="incomplete", receipt="running", running=True, step=index + 1,
                          label=step["label"], resume=None,
                          text=f"Provisioning incomplete: step {index + 1} of {len(expected)} "
                               f"({step['label']}), running now")
            return status
        state, reason = "interrupted", "the run ended without recording how (killed, or the host stopped)"
    status.update(status="incomplete", receipt=state, step=index + 1, label=step["label"], reason=reason,
                  resume=resume_command(machine_id, index + 1, repo_root),
                  text=f"Provisioning incomplete: step {index + 1} of {len(expected)} ({step['label']})")
    return status


# ---------------------------------------------------------- the last step

# Streams in which the Looking Glass sender has started a capture: it got
# past the screen-cast portal's source selection.
CAPTURED_STREAMS = ("starting", "streaming")
VERIFY_DEADLINE = 300.0
VERIFY_POLL = 3.0


def sudo_verdict(returncode: int, stderr: str) -> str:
    """`sudo -n true` in the guest: "refused" only when sudo itself asked
    for a password; "passwordless" when it ran; anything else is unproven."""
    if returncode == 0:
        return "passwordless"
    if returncode == 1 and "a password is required" in stderr.lower():
        return "refused"
    return "unverified"


def capture_reached(report: Any) -> bool:
    """A `looking-glass health` report whose sender has started a capture."""
    return (isinstance(report, dict) and report.get("agent") == "yes"
            and report.get("sender") == "running" and report.get("stream") in CAPTURED_STREAMS)


PROBE_ERRORS = (HyperlabError, OSError, subprocess.TimeoutExpired)


def verify_provisioning(record: dict[str, Any], *, sudo_probe: Callable[[], tuple[int, str]],
                        restart_capture: Callable[[], Any], health: Callable[[], Any],
                        say: Callable[[str], None], sleep: Callable[[float], None],
                        clock: Callable[[], float], deadline: float = VERIFY_DEADLINE,
                        poll: float = VERIFY_POLL) -> dict[str, Any]:
    """The final step of a workstation's provisioning; `ok` only when every
    proof held. The probes are injected; nothing here reaches a guest."""
    machine_id = record["id"]
    ids = step_ids(record)
    if ids is None or "verify" not in ids:
        raise ContractError(f"{machine_id} has no verification step: a server keeps passwordless sudo")
    report: dict[str, Any] = {"machine": machine_id, "sudo": "unverified",
                              "looking_glass": "not-required", "stream": None, "ok": False, "reason": ""}
    try:
        returncode, stderr = sudo_probe()
    except PROBE_ERRORS as exc:
        report["reason"] = f"sudo -n true could not be run in the guest: {exc}"
        return report
    report["sudo"] = sudo_verdict(returncode, stderr)
    if report["sudo"] == "passwordless":
        report["reason"] = "sudo -n true succeeded in the guest: passwordless sudo is still open"
        return report
    if report["sudo"] != "refused":
        report["reason"] = (f"sudo -n true ended with {returncode} without asking for a password: "
                            f"{stderr.strip()[-200:]}")
        return report
    say("sudo asks for the password: passwordless sudo has ended.")
    if looking_glass_proof(record):
        report["looking_glass"] = "unproven"
        end = clock() + deadline
        restarted = False
        said = ""
        while True:
            try:
                if not restarted:
                    restart_capture()
                    restarted = True
                    say("Capture restarted; waiting for the sender to reach Capture Start.")
                observed = health()
                if capture_reached(observed):
                    report.update(looking_glass="captured", stream=observed["stream"])
                    break
                detail = (f"agent {observed.get('agent')}, sender {observed.get('sender')}, "
                          f"stream {observed.get('stream')}") if isinstance(observed, dict) else "no report"
                report["stream"] = observed.get("stream") if isinstance(observed, dict) else None
            except PROBE_ERRORS as exc:
                detail = str(exc)
            if detail != said:
                say(f"Not yet: {detail}. Open Looking Glass for {machine_id} "
                    f"(hyperlabctl open looking-glass {machine_id}) and log in if asked.")
                said = detail
            if clock() >= end:
                report["reason"] = (f"the Looking Glass sender did not reach Capture Start within "
                                    f"{int(deadline)} s ({detail})")
                return report
            sleep(poll)
        say(f"The Looking Glass sender reached capture (stream {report['stream']}).")
    report["ok"] = True
    return report
