#!/usr/bin/env python3
"""Contract for host-owned focused-surface provenance resolution."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RESOLVER = ROOT / "tools/surface_provenance.py"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(
            f"HyperLab surface provenance contract: {message}"
        )


def load_module():
    spec = importlib.util.spec_from_file_location(
        "surface_provenance",
        RESOLVER,
    )

    require(spec is not None, "cannot load resolver")
    require(spec.loader is not None, "resolver loader missing")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def write_proc(
    proc_root: Path,
    *,
    pid: int,
    start_ticks: str,
    executable: Path,
) -> None:
    process = proc_root / str(pid)
    process.mkdir(parents=True)

    # Fields:
    # 1 pid
    # 2 comm
    # 3 state
    # ...
    # 22 starttime
    tail = [
        "S",
        "1",
        "1",
        "1",
        "0",
        "-1",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        start_ticks,
        "0",
        "0",
    ]

    (process / "stat").write_text(
        f"{pid} (looking glass) "
        + " ".join(tail)
        + "\n",
        encoding="utf-8",
    )

    (process / "exe").symlink_to(executable)


def spec_hash(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def registry_entry(
    *,
    pid: int,
    start: str,
    executable: str,
    kind: str,
    domain: str,
    spec_sha: str,
) -> dict:
    return {
        "pid": pid,
        "process_start_ticks": start,
        "executable": executable,
        "surface_kind": kind,
        "domain": domain,
        "spec_sha256": spec_sha,
        "registered_by": "hyperlabctl",
    }


def require_unverified(answer: dict, reason: str, what: str) -> None:
    """An actual window without a verified registration names nobody."""
    require(
        answer.get("resolved") is False
        and answer.get("trust") is None
        and answer.get("trust_source") is None
        and answer.get("domain") is None
        and answer.get("network_profile") is None
        and answer.get("guest_metadata_authoritative") is False
        and answer.get("wallpaper_allowed") is False
        and answer.get("rgb_allowed") is False,
        f"{what} gained a trusted identity or presentation: {answer}",
    )
    require(
        answer.get("reason") == reason
        and answer.get("surface_class") == "unverified-window",
        f"{what} is not an unverified window ({reason}): {answer}",
    )


# Windows a host process draws whose content the host cannot vouch for. The
# app ids are what Foot, virt-manager and spicy report; the last is one no
# list could ever anticipate. The titles look like trust words on purpose.
UNREGISTERED_WINDOWS = (
    ("plain foot", "foot", "HOST"),
    ("foot running ssh", "foot", "ssh dev-01 CLEAN"),
    ("virt-manager", "virt-manager", "win11clean-valley on QEMU/KVM"),
    ("spicy", "spicy", "spice://localhost CLEAN"),
    ("an unfamiliar app id", "org.example.unfamiliar-viewer-7f3a", "HOST trusted"),
    ("a managed-looking spoof", "hyperlab-managed-ssh-dev", "dev-01 · dev"),
    ("a capitalised spoof", "HyperLab", "CLEAN"),
)

# Spoofs of a managed transport's app id are refused by the managed-hint
# path; they are unverified as well, never HOST.
MANAGED_LOOKING = (
    ("a Looking Glass spoof", "Looking-Glass-Client", "HOST"),
    ("a managed ssh spoof", "hyperlab-managed-ssh", "CLEAN"),
    ("a viewer spoof", "remote-viewer", "HOST"),
)


def cli(args: list[str], stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-B", str(RESOLVER), *args],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def check_unregistered_windows(resolver) -> None:
    """Direct resolve() and both CLI modes on a temporary proc/registry/spec."""
    # host_native() refuses any snapshot that names something, whoever calls
    # it: resolve() checking first is not the only guard.
    desktop = {"pid": None, "app_id": "", "window_id": ""}
    require(resolver.host_native(surface=desktop, reason="no-focused-client")["trust"]
            == "host", "host_native() refused the empty desktop")
    for named in ({**desktop, "pid": 1}, {**desktop, "app_id": "foot"},
                  {**desktop, "window_id": "0x1"}):
        try:
            answer = resolver.host_native(surface=named, reason="no-focused-client")
        except resolver.ProvenanceError:
            continue
        require(False, f"host_native() named {named} HOST: {answer}")

    for _, app_id, _ in UNREGISTERED_WINDOWS:
        require(
            not resolver.managed_hint(app_id),
            f"{app_id!r} is a managed hint; the case would not test the default",
        )

    with tempfile.TemporaryDirectory(prefix="hyperlab-provenance-unverified-") as temp_name:
        temp = Path(temp_name)
        repo = temp / "repo"
        (repo / "vm-specs").mkdir(parents=True)
        proc = temp / "proc"
        proc.mkdir()
        spec = repo / "vm-specs" / "dev-01.yml"
        spec.write_text(
            yaml.safe_dump({"name": "dev-01", "network_profile": "dev",
                            "device_profile": "vfio", "looking_glass": True}),
            encoding="utf-8",
        )
        # A registry with a real entry for another process: unrelated
        # registrations never lend their trust to a window.
        registry = {"version": 1, "entries": [registry_entry(
            pid=47000, start="5", executable="/usr/local/bin/looking-glass-client",
            kind="looking-glass", domain="dev-01", spec_sha=spec_hash(spec))]}
        registry_path = temp / "surface-provenance.json"
        registry_path.write_text(json.dumps(registry), encoding="utf-8")
        registry_path.chmod(0o600)
        foot = temp / "foot"
        foot.write_text("#!/bin/sh\n", encoding="utf-8")

        cases = []
        for number, (label, app_id, title) in enumerate(UNREGISTERED_WINDOWS + MANAGED_LOOKING):
            pid = 47100 + number
            # The process is real and running on the host: that alone does
            # not establish the provenance of what its window shows.
            write_proc(proc, pid=pid, start_ticks="9", executable=foot)
            surface = {"pid": pid, "app_id": app_id, "window_id": f"0x{pid:x}", "title": title}
            managed = (label, app_id, title) in MANAGED_LOOKING
            reason = "managed-surface-not-registered" if managed else "unregistered-window"
            cases.append((label, surface, reason, managed))

        common = ["--repo", str(repo), "--proc-root", str(proc)]
        stream_lines = []
        for number, (label, surface, reason, managed) in enumerate(cases, start=1):
            direct = resolver.resolve(repo=repo, surface=surface, registry=registry,
                                      proc_root=proc)
            completed = cli([*common, "resolve", "--surface-json", json.dumps(surface),
                             "--registry", str(registry_path)])
            require(completed.returncode == 0,
                    f"resolve CLI failed for {label}: {completed.stderr.strip()}")
            printed = json.loads(completed.stdout)
            for where, answer in (("resolve()", direct), ("resolve CLI", printed)):
                if managed:
                    require(answer["resolved"] is False and answer["trust"] is None
                            and answer["reason"] == reason
                            and answer["surface_class"] == "managed-unresolved"
                            and answer["wallpaper_allowed"] is False
                            and answer["rgb_allowed"] is False,
                            f"{where}: {label} was not refused: {answer}")
                else:
                    require_unverified(answer, reason, f"{where}: {label}")
            stream_lines.append(json.dumps({"request": number, "surface": {
                key: surface[key] for key in ("pid", "app_id", "window_id")}}))

        pidless = {"pid": None, "app_id": "foot", "window_id": "0x77"}
        empty = {"pid": None, "app_id": "", "window_id": ""}
        stream_lines.append(json.dumps({"request": len(cases) + 1, "surface": pidless}))
        stream_lines.append(json.dumps({"request": len(cases) + 2, "surface": empty}))
        completed = cli([*common, "stream", "--registry", str(registry_path)],
                        stdin="\n".join(stream_lines) + "\n")
        require(completed.returncode == 0, f"stream CLI failed: {completed.stderr.strip()}")
        answers = [json.loads(line) for line in completed.stdout.splitlines()]
        require([answer.get("request") for answer in answers] == list(range(1, len(cases) + 3))
                and all(answer.get("status") == "ok" for answer in answers),
                f"the stream did not answer every request in order: {answers}")
        for (label, surface, reason, managed), answer in zip(cases, answers, strict=False):
            provenance = answer["provenance"]
            require(provenance["pid"] == surface["pid"],
                    f"stream: {label} answered about another process")
            if managed:
                require(provenance["resolved"] is False and provenance["trust"] is None
                        and provenance["reason"] == reason,
                        f"stream: {label} was not refused: {provenance}")
            else:
                require_unverified(provenance, reason, f"stream: {label}")
        require_unverified(answers[-2]["provenance"], "window-without-pid",
                           "stream: a PID-less window")
        desktop = answers[-1]["provenance"]
        require(desktop["resolved"] is True and desktop["trust"] == "host"
                and desktop["reason"] == "no-focused-client",
                f"stream: the empty desktop is no longer HOST: {desktop}")


def check_projected_machine(resolver) -> None:
    """A Machine projected into vm-specs/.generated/ resolves like a fixture."""
    with tempfile.TemporaryDirectory(prefix="hyperlab-provenance-machine-") as temp_name:
        temp = Path(temp_name)
        repo = temp / "repo"
        generated = repo / "vm-specs" / ".generated"
        generated.mkdir(parents=True)
        proc = temp / "proc"
        proc.mkdir()
        lg_real = temp / "looking-glass-client"
        lg_real.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        lg_real.chmod(0o755)
        resolver.EXPECTED_EXECUTABLES["looking-glass"] = str(lg_real.resolve())

        machine = {
            "schema_version": 1,
            "name": "dev-01",
            "image": "arch-dev-20261003",
            "device_profile": "vfio",
            "network_profile": "dev",
            "looking_glass": True,
            "looking_glass_mode": "linux-experimental",
            "tags": ["managed-machine", "linux", "dev"],
        }
        spec = generated / "dev-01.yml"
        spec.write_text(yaml.safe_dump(machine, sort_keys=False), encoding="utf-8")
        write_proc(proc, pid=45001, start_ticks="1234", executable=lg_real)
        surface = {"pid": 45001, "app_id": "looking-glass", "window_id": "0xdef", "title": "dev-01"}

        def answer():
            registry = {"version": 1, "entries": [registry_entry(
                pid=45001, start="1234", executable=str(lg_real.resolve()),
                kind="looking-glass", domain="dev-01", spec_sha=spec_hash(spec))]}
            return resolver.resolve(repo=repo, surface=surface, registry=registry, proc_root=proc)

        result = answer()
        require(result["resolved"] is True and result["trust"] == "dev",
                f"projected Machine did not resolve: {result}")
        require(result["spec"].endswith("vm-specs/.generated/dev-01.yml"), "wrong spec resolved")

        # Without the managed-machine tag a generated file is not a Machine.
        spec.write_text(yaml.safe_dump({**machine, "tags": ["linux"]}, sort_keys=False), encoding="utf-8")
        result = answer()
        require(result["resolved"] is False
                and result["reason"] == "registered-domain-spec-unavailable",
                f"untagged generated spec resolved: {result}")

        # One name, two specs: refuse rather than choose.
        spec.write_text(yaml.safe_dump(machine, sort_keys=False), encoding="utf-8")
        (repo / "vm-specs" / "dev-01.yml").write_text(
            yaml.safe_dump({**machine, "tags": []}, sort_keys=False), encoding="utf-8")
        result = answer()
        require(result["resolved"] is False
                and result["reason"] == "registered-domain-spec-unavailable",
                f"ambiguous Machine name resolved: {result}")


def main() -> int:
    require(RESOLVER.is_file(), "resolver missing")
    require(
        bool(RESOLVER.stat().st_mode & 0o111),
        "resolver not executable",
    )

    resolver = load_module()

    with tempfile.TemporaryDirectory(
        prefix="hyperlab-provenance-"
    ) as temp_name:
        temp = Path(temp_name)
        repo = temp / "repo"
        specs = repo / "vm-specs"
        proc = temp / "proc"
        bin_dir = temp / "bin"

        specs.mkdir(parents=True)
        proc.mkdir()
        bin_dir.mkdir()

        lg_real = bin_dir / "looking-glass-client"
        lg_real.write_text(
            "#!/bin/sh\nexit 0\n",
            encoding="utf-8",
        )
        lg_real.chmod(0o755)

        dev_spec = specs / "arch-dev-vfio.yml"

        dev_spec.write_text(
            yaml.safe_dump(
                {
                    "schema_version": 1,
                    "name": "arch-dev-vfio",
                    "image": "arch",
                    "device_profile": "vfio",
                    "network_profile": "dev",
                    "looking_glass": True,
                    "looking_glass_mode":
                        "linux-experimental",
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        clean_spec = specs / "win11clean-valley.yml"

        clean_spec.write_text(
            yaml.safe_dump(
                {
                    "schema_version": 1,
                    "name": "win11clean-valley",
                    "image": "win11clean",
                    "device_profile": "vfio",
                    "network_profile": "clean",
                    "looking_glass": True,
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        # For the unit contract, temporarily bind the approved path to our
        # synthetic executable. Production still requires the fixed canonical
        # path through the actual registry validation.
        resolver.EXPECTED_EXECUTABLES[
            "looking-glass"
        ] = str(lg_real.resolve())

        dev_pid = 44001
        dev_start = "987654"

        write_proc(
            proc,
            pid=dev_pid,
            start_ticks=dev_start,
            executable=lg_real,
        )

        registry = {
            "version": 1,
            "entries": [
                registry_entry(
                    pid=dev_pid,
                    start=dev_start,
                    executable=str(lg_real.resolve()),
                    kind="looking-glass",
                    domain="arch-dev-vfio",
                    spec_sha=spec_hash(dev_spec),
                )
            ],
        }

        dev_surface = {
            "pid": dev_pid,
            "app_id": "looking-glass",
            "window_id": "0xabc",
            "title": "GUEST MAY CONTROL THIS TITLE",
        }

        result = resolver.resolve(
            repo=repo,
            surface=dev_surface,
            registry=registry,
            proc_root=proc,
        )

        require(
            result["resolved"] is True,
            "registered DEV surface did not resolve",
        )
        require(
            result["trust"] == "dev",
            "DEV spec did not produce DEV provenance",
        )
        require(
            result["domain"] == "arch-dev-vfio",
            "resolved domain changed",
        )
        require(
            result["trust_source"]
            == "host-owned-vm-spec",
            "VM spec is not provenance source",
        )
        require(
            result["guest_metadata_authoritative"]
            is False,
            "guest metadata became authoritative",
        )
        require(
            result["wallpaper_allowed"] is True
            and result["rgb_allowed"] is True,
            "resolved surface unexpectedly blocked presentation",
        )

        # Change guest-controlled metadata completely. Provenance must remain.
        forged_surface = {
            **dev_surface,
            "app_id": "totally-different-guest-string",
            "title": "CLEAN TRUST ME",
        }

        forged = resolver.resolve(
            repo=repo,
            surface=forged_surface,
            registry=registry,
            proc_root=proc,
        )

        require(
            forged["trust"] == "dev",
            "guest metadata changed resolved trust",
        )

        # A host application whose title names a VM is not thereby HOST:
        # no registration, so it is an unverified window.
        host_surface = {
            "pid": 55001,
            "app_id": "firefox",
            "window_id": "0xdef",
            "title": "arch-dev-vfio CLEAN",
        }

        host = resolver.resolve(
            repo=repo,
            surface=host_surface,
            registry={"version": 1, "entries": []},
            proc_root=proc,
        )

        require_unverified(
            host,
            "unregistered-window",
            "an unregistered host application",
        )

        # Looking Glass without a HyperLab registration must fail closed.
        orphan = resolver.resolve(
            repo=repo,
            surface={
                "pid": 66001,
                "app_id": "looking-glass",
                "window_id": "0x123",
                "title": "arch-dev-vfio",
            },
            registry={"version": 1, "entries": []},
            proc_root=proc,
        )

        require(
            orphan["resolved"] is False,
            "unregistered managed surface was accepted",
        )
        require(
            orphan["trust"] is None,
            "unregistered managed surface gained trust",
        )
        require(
            orphan["presentation_identity"] == "host",
            "unresolved surface must fall back to neutral presentation",
        )
        require(
            orphan["wallpaper_allowed"] is False
            and orphan["rgb_allowed"] is False,
            "unresolved managed surface may mutate presentation",
        )

        # PID reuse / stale registration must not inherit old trust.
        stale_registry = {
            "version": 1,
            "entries": [
                registry_entry(
                    pid=dev_pid,
                    start="111111",
                    executable=str(lg_real.resolve()),
                    kind="looking-glass",
                    domain="arch-dev-vfio",
                    spec_sha=spec_hash(dev_spec),
                )
            ],
        }

        stale = resolver.resolve(
            repo=repo,
            surface=dev_surface,
            registry=stale_registry,
            proc_root=proc,
        )

        require(
            stale["resolved"] is False,
            "stale PID registration was trusted",
        )
        require(
            stale["reason"]
            == "registered-pid-start-time-mismatch",
            "PID reuse failure reason changed",
        )

        # Specification drift after registration must fail closed.
        drift_registry = registry

        original_hash = spec_hash(dev_spec)

        dev_spec.write_text(
            yaml.safe_dump(
                {
                    "schema_version": 1,
                    "name": "arch-dev-vfio",
                    "image": "arch",
                    "device_profile": "vfio",
                    "network_profile": "dirty",
                    "looking_glass": True,
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        require(
            spec_hash(dev_spec) != original_hash,
            "test failed to mutate VM spec",
        )

        drift = resolver.resolve(
            repo=repo,
            surface=dev_surface,
            registry=drift_registry,
            proc_root=proc,
        )

        require(
            drift["resolved"] is False,
            "changed VM spec reused stale provenance",
        )
        require(
            drift["reason"]
            == "registered-domain-spec-drift",
            "spec drift did not fail closed",
        )

        # A PID-less snapshot that still names a window is not the desktop.
        for label, partial in (
            ("app id only", {"app_id": "foot", "window_id": ""}),
            ("window id only", {"app_id": "", "window_id": "17"}),
            ("both", {"app_id": "org.example.Viewer", "window_id": "0x9"}),
        ):
            pidless = resolver.resolve(
                repo=repo,
                surface={"pid": None, "title": "HOST", **partial},
                registry=registry,
                proc_root=proc,
            )
            require_unverified(
                pidless,
                "window-without-pid",
                f"a PID-less window ({label})",
            )

        # Desktop/no focused client is neutral HOST.
        desktop = resolver.resolve(
            repo=repo,
            surface={
                "pid": None,
                "app_id": "",
                "window_id": "",
                "title": "",
            },
            registry={"version": 1, "entries": []},
            proc_root=proc,
        )

        require(
            desktop["trust"] == "host"
            and desktop["resolved"] is True,
            "desktop focus did not resolve to neutral HOST",
        )
        require(
            desktop["reason"] == "no-focused-client"
            and desktop["surface_class"] == "host-native"
            and desktop["wallpaper_allowed"] is True
            and desktop["rgb_allowed"] is True,
            f"the empty desktop lost its HOST presentation: {desktop}",
        )

        # The genuinely empty snapshot is the only HOST answer, whatever
        # registry is in force.
        require(
            resolver.resolve(
                repo=repo,
                surface={"pid": None, "app_id": "", "window_id": ""},
                registry=registry,
                proc_root=proc,
            )["trust"] == "host",
            "the empty desktop depends on the registry",
        )

    source = RESOLVER.read_text(
        encoding="utf-8"
    )

    # Explicit architectural invariants.
    for required in (
        '"guest_metadata_authoritative": False',
        '"registered-pid-start-time-mismatch"',
        '"registered-domain-spec-drift"',
        '"managed-surface-not-registered"',
        '"unregistered-window"',
        '"window-without-pid"',
        '"host-owned-vm-spec"',
        '"host-native"',
    ):
        require(
            required in source,
            f"resolver invariant missing: {required}",
        )

    # The old rule named every unregistered process HOST.
    require(
        '"unregistered-host-process"' not in source,
        "the resolver still knows unregistered-host-process",
    )

    check_projected_machine(load_module())
    check_unregistered_windows(load_module())

    print(
        "HyperLab host-owned focused-surface provenance contract: OK"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
