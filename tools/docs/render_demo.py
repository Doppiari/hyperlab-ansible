#!/usr/bin/env python3
"""Render the shell's documentation surfaces from a fixture state file.

The renders use the offscreen production-QML harness of
`tests/host_quickshell_runtime_contract.py`: the real views, coordinator,
state validation and theme, with recording fixtures in place of every
bridge, so nothing on the host is read, started or changed. Navigation goes
through the real `ShellIpc.qml` route table (its IPC handlers adapted to
plain objects), so every capture is reached the way `capture-shell` reaches
it on a live session.

    python3 tools/docs/render_demo.py --out DIR [--fixture FILE]

Each surface is written at 1920x1080 and, with the same layout at twice the
pixel density, at 3840x2160:

    demo-<route>-<size>.png        every `navigate` route
    demo-machine-<name>-<size>.png the selected Machine
    demo-bar-<focus>-<size>.png    the rail for host, each domain, Unknown

The lock surface is not drawn by the shell (hyprlock under Hyprland,
swaylock under Sway), so it has no demo render.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "tools/hyperlabctl"))

import host_quickshell_runtime_contract as runtime  # noqa: E402

FIXTURE = ROOT / "tests/fixtures/documentation-demo.json"
NETWORKS = ROOT / "group_vars/all/networks.yml"
WALLPAPERS = ROOT / "roles/host_desktop_common/files/wallpapers"
# Output name -> device pixel ratio over the 1920x1080 layout.
SIZES = {"1920x1080": 1, "3840x2160": 2}
LAYOUT = (1920, 1080)
DOMAINS = ("clean", "dev", "services", "dirty", "lab")
FOCUS = ("host",) + DOMAINS + ("unknown",)
NAME = re.compile(r"[a-z][a-z0-9-]{1,30}")
LOCK_NOTE = "lock: not drawn by the shell (hyprlock or swaylock); no demo render"


class FixtureError(ValueError):
    pass


def refuse(condition: bool, message: str) -> None:
    if not condition:
        raise FixtureError(message)


def load_fixture(path: Path) -> dict:
    """The fixture, or a refusal: five Machines, one per domain, two
    running, one GPU owner that runs, one disposable, and one focus state
    for the host, each domain and Unknown, in that order."""
    refuse(not path.is_symlink() and path.is_file(), f"{path} is not a regular file")
    try:
        document = json.loads(path.read_text(encoding="utf-8"),
                              object_pairs_hook=_no_duplicates)
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise FixtureError(f"unreadable fixture: {error}") from None
    refuse(isinstance(document, dict)
           and set(document) == {"machines", "gpu_owner", "selected", "focus"},
           "the fixture must hold exactly machines, gpu_owner, selected and focus")
    machines = document["machines"]
    refuse(isinstance(machines, list) and len(machines) == len(DOMAINS),
           "the fixture must hold five Machines")
    for row in machines:
        refuse(isinstance(row, dict) and set(row) == {"name", "domain", "state", "lifecycle"},
               "a Machine must hold exactly name, domain, state and lifecycle")
        refuse(isinstance(row["name"], str) and NAME.fullmatch(row["name"]) is not None,
               f"invalid Machine name {row['name']!r}")
        refuse(row["state"] in {"running", "shut off"}, f"invalid state for {row['name']}")
        refuse(row["lifecycle"] in {"permanent", "disposable"},
               f"invalid lifecycle for {row['name']}")
    names = [row["name"] for row in machines]
    refuse(len(set(names)) == len(names), "a Machine name is repeated")
    refuse(sorted(row["domain"] for row in machines) == sorted(DOMAINS),
           "the five Machines must be in the five domains")
    running = [row["name"] for row in machines if row["state"] == "running"]
    refuse(len(running) == 2, "exactly two Machines must run")
    refuse(sum(row["lifecycle"] == "disposable" for row in machines) == 1,
           "exactly one Machine must be disposable")
    refuse(document["gpu_owner"] in running, "the GPU owner must be a running Machine")
    owner_domain = next(row["domain"] for row in machines if row["name"] == document["gpu_owner"])
    refuse(owner_domain in gpu_ladder(), "the GPU owner's domain has no GPU handoff level")
    refuse(document["selected"] in names, "the selected Machine is not in the fixture")
    focus = document["focus"]
    refuse(isinstance(focus, list) and [entry.get("id") for entry in focus
                                        if isinstance(entry, dict)] == list(FOCUS),
           "focus must list host, the five domains and unknown, in that order")
    domain_of = {row["name"]: row["domain"] for row in machines}
    for entry in focus:
        if entry["id"] in DOMAINS:
            refuse(set(entry) == {"id", "machine"} and domain_of.get(entry["machine"]) == entry["id"],
                   f"focus {entry['id']} must name a Machine of that domain")
        else:
            refuse(set(entry) == {"id"}, f"focus {entry['id']} names no Machine")
    return document


def gpu_ladder() -> dict[str, int]:
    """The configured GPU handoff levels (`gpu_trust_levels`)."""
    levels = yaml.safe_load(NETWORKS.read_text(encoding="utf-8")).get("gpu_trust_levels")
    if not isinstance(levels, dict) or not all(
            isinstance(name, str) and isinstance(level, int) and not isinstance(level, bool)
            for name, level in levels.items()):
        raise FixtureError("networks.yml has no readable gpu_trust_levels")
    return levels


def boot_claim(fixture: dict) -> dict:
    """The boot claim the owner leaves: its domain at that domain's level.

    A handoff to a lower-ranked domain lowers the recorded level
    (docs/gpu-handoff-policy.md), so a demo with a Dev owner cannot show a
    Clean claim.
    """
    domain = next(row["domain"] for row in fixture["machines"] if row["name"] == fixture["gpu_owner"])
    level = gpu_ladder()[domain]
    return {"text": f"{domain} {level}", "tooltip": f"GPU claimed for {domain}", "class": "warn",
            "known": True, "claimed": True, "identity": domain, "level": level}


def _no_duplicates(items: list[tuple[str, object]]) -> dict:
    keys = [key for key, _ in items]
    refuse(len(keys) == len(set(keys)), "a fixture object repeats a key")
    return dict(items)


def rows(fixture: dict) -> list[dict]:
    """Inventory rows in the bridge's shape."""
    owner = fixture["gpu_owner"]
    return [dict(runtime.MACHINE_TEMPLATE, name=row["name"], provenance=row["domain"],
                 network=row["domain"], trust_profile=row["domain"], networks=[row["domain"]],
                 state=row["state"], lifecycle=row["lifecycle"], runtime_present=True,
                 runtime_drift=False, gpu="GPU held" if row["name"] == owner else "",
                 gpu_relation="held" if row["name"] == owner else "none",
                 vfio=row["name"] == owner)
            for row in fixture["machines"]]


def provenance(entry: dict, pid: int, domain_of: dict[str, str]) -> dict:
    """A resolver answer shaped as ShellState validates it."""
    base = {"schema": 1, "guest_metadata_authoritative": False, "pid": pid}
    if entry["id"] == "host":
        # HOST is the empty desktop only: no process, no window.
        return dict(base, pid=None, resolved=True, reason="no-focused-client",
                    surface_class="host-native", trust="host", presentation_identity="host",
                    trust_source="host-native", domain=None, network_profile=None,
                    wallpaper_allowed=True, rgb_allowed=True)
    if entry["id"] == "unknown":
        return dict(base, resolved=False, reason="managed-surface-not-registered",
                    surface_class="managed-unresolved", trust=None,
                    presentation_identity="host", trust_source=None, domain=None,
                    network_profile=None, wallpaper_allowed=False, rgb_allowed=False)
    domain = domain_of[entry["machine"]]
    return dict(base, resolved=True, reason="managed-surface-resolved",
                surface_class="managed-guest", surface_kind="looking-glass", trust=domain,
                presentation_identity=domain, network_profile=domain,
                trust_source="host-owned-vm-spec", domain=entry["machine"],
                spec=f"vm-specs/{entry['machine']}.yml", spec_sha256="0" * 64,
                wallpaper_allowed=True, rgb_allowed=True)


def adapt_ipc(source: str) -> str:
    """ShellIpc with its IPC handlers as plain objects, everything else
    unchanged, the same way the harness adapts every window host."""
    for line in ("import Quickshell\n", "import Quickshell.Io\n"):
        if line not in source:
            raise SystemExit("ShellIpc.qml lost an expected import: " + line.strip())
        source = source.replace(line, "")
    if source.count("\nScope {\n") != 1:
        raise SystemExit("ShellIpc.qml is not one Scope")
    source = source.replace("\nScope {\n", "\nItem {\n", 1)
    return re.sub(r"(?m)^    IpcHandler \{\n", "    QtObject {\n        property string target\n",
                  source)


def stage() -> Path:
    directory = runtime.stage()
    (directory / "ShellIpc.qml").write_text(
        adapt_ipc((runtime.QML / "ShellIpc.qml").read_text(encoding="utf-8")), encoding="utf-8")
    return directory


# Injected after the harness state: the root's visibility bindings, the real
# IPC routes, and the handler lookup every scenario uses.
IPC = """ShellState { id: sharedState
@@BINDINGS@@
    }
    ShellIpc { id: sharedIpc; shellState: sharedState; shellSurfaces: sharedSurfaces; theme: sharedTheme }
    function ipcTarget(name) {
        const objects = sharedIpc.resources;
        for (let index = 0; index < objects.length; index++)
            if (objects[index].target === name)
                return objects[index];
        return null;
    }
"""


def harness(width: int, height: int, inventory: list[dict], body: str,
            gpu: dict | None = None, trust: dict | None = None) -> tuple[str, list[str]]:
    """The runtime harness with the real ShellIpc beside the real state."""
    root = (runtime.QML / "shell.qml").read_text(encoding="utf-8")
    bindings = []
    for name in ("networksMachinesVisible", "networksMapVisible"):
        match = re.search(name + r":\s*(.*?)\n\s*\w+:", root, re.S)
        if match is None:
            raise SystemExit(f"shell.qml lost its {name} binding")
        bindings.append(f"        {name}: {match[1].strip()}")
    source, messages = runtime.scenario_source(width, height, inventory, body, gpu=gpu, trust=trust)
    anchor = "ShellState { id: sharedState }"
    if source.count(anchor) != 1:
        raise SystemExit("the runtime harness lost its ShellState declaration")
    return source.replace(anchor, IPC.replace("@@BINDINGS@@", "\n".join(bindings))), messages


SCENE = r"""
            sharedTokens.reducedMotion = true;
            const fixture = @@FIXTURE@@;
            const inventory = @@ROWS@@;
            const networks = @@NETWORKS@@;
            const focusAnswers = @@FOCUS@@;
            const ladder = @@LADDER@@;
            const out = @@OUT@@;
            const suffix = @@SUFFIX@@;
            const navigate = ipcTarget("navigate");
            check(navigate !== null, "the navigate IPC target is missing");
            if (window.firstFailure >= 0) { Qt.exit(@@BASE@@ + window.firstFailure); return; }

            // Every bridge answers from the fixture, as soon as it is asked.
            sharedState.applyFeatures('{"networks_view_enabled": true, "nitro_view_enabled": true}');
            sharedState.applyRamPayload(JSON.stringify({text: "11.2 GiB", tooltip: "of 32 GiB", class: ""}));
            sharedState.applyOutsideDomainsPayload(JSON.stringify({machines_available: true,
                machines: inventory.map(row => ({name: row.name, state: row.state,
                                                 networks: row.networks, managed: true}))}));
            sharedMachineActions.createPlanAnswer = @@PLAN@@;
            sharedMachineActions.workbenchAnswer = @@WORKBENCH@@;
            sharedMachineActions.usbAnswer = @@USB@@;
            sharedMachineActions.panicAnswer = {phase: "panic", engaged: false, engaged_at: null,
                                                domains: [], failures: [], notes: []};
            sharedMachineActions.requestPanicStatus();
            // The owner and the boot claim are shown together: the claim is
            // the owner's domain at its configured level, never another.
            const ownerDomain = inventory.filter(row => row.name === fixture.gpu_owner)[0].provenance;
            check(sharedState.gpuOwnership.known && sharedState.gpuOwnership.owner === fixture.gpu_owner,
                  "the demo GPU owner was not accepted");
            check(sharedState.trustClaimState === "ok" && sharedState.trustClaim.claimed
                  && sharedState.trustClaim.identity === ownerDomain
                  && sharedState.trustClaim.level === ladder[ownerDomain],
                  "the demo boot claim is not the GPU owner's domain at its configured level");
            if (window.firstFailure >= 0) { Qt.exit(@@BASE@@ + window.firstFailure); return; }
            function answerBridges() {
                if (sharedState.networksInFlight)
                    sharedState.finishNetworks(sharedState.networksFlightGeneration,
                                               JSON.stringify(networks), 0);
                if (sharedState.nitroInFlight)
                    sharedState.nitroFixtureComplete(JSON.stringify(@@NITRO@@), 0);
            }

            function focus(entry) {
                sharedState.observationNow = Date.now();
                sharedState.applyFocusPayload(JSON.stringify(focusAnswers[entry.id].surface));
                sharedState.applyProvenancePayload(JSON.stringify({
                    schema: 1, status: "ok", request: sharedState.provenanceRequest,
                    provenance: focusAnswers[entry.id].answer}));
                const kind = entry.id === "host" ? "host" : (entry.id === "unknown" ? "unknown" : "machine");
                check(sharedState.focusedMachine.kind === kind
                      && (kind !== "machine" || sharedState.focusedMachine.identity === entry.id),
                      "a focus fixture was not resolved as its state");
            }

            function inventoryWith(running) {
                sharedState.applyMachinePayload(JSON.stringify({
                    text: inventory.length + "/" + inventory.length, class: "ok",
                    machines_available: true,
                    machines: inventory.map(row => running === row.name
                        ? Object.assign({}, row, {state: "running"}) : row)}));
            }

            function open(route) {
                check(navigate.open(route) === route, "a navigate route did not land where it says");
            }

            const steps = [];
            for (const entry of fixture.focus)
                steps.push({name: "bar-" + entry.id, prepare: () => {
                    open("desktop");
                    inventoryWith(entry.machine || "");
                    focus(entry);
                }});
            steps.push({name: "machine-" + fixture.selected, prepare: () => {
                inventoryWith("");
                focus(fixture.focus[0]);
                check(navigate.machine(fixture.selected) === "selected " + fixture.selected,
                      "the fixture Machine could not be selected");
            }});
            for (const route of navigate.routes().split("\n"))
                steps.push({name: route, prepare: () => {
                    if (["launcher", "clipboard", "keys", "panel"].indexOf(route) >= 0)
                        open("desktop");
                    open(route);
                }});

            let index = 0;
            function next() {
                if (index >= steps.length || window.firstFailure >= 0) {
                    Qt.exit(window.firstFailure < 0 ? 0 : @@BASE@@ + window.firstFailure);
                    return;
                }
                const step = steps[index];
                step.prepare();
                answerBridges();
                settleTimer.callback = function() {
                    answerBridges();
                    window.contentItem.grabToImage(function(result) {
                        check(result.saveToFile(out + "/demo-" + step.name + "-" + suffix + ".png"),
                              "a render could not be saved");
                        index += 1;
                        next();
                    });
                };
                settleTimer.restart();
            }
            next();
            return;
"""


def scene(fixture: dict, out: Path, size: str, wallpaper: Path) -> tuple[str, list[str]]:
    import host_quickshell_create_view_contract as create
    import sfere_view_contract as seal

    inventory = rows(fixture)
    domain_of = {row["name"]: row["domain"] for row in fixture["machines"]}
    answers = {}
    for index, entry in enumerate(fixture["focus"]):
        pid = 900 + index
        surface = ({"pid": None, "app_id": "", "window_id": ""} if entry["id"] == "host"
                   else {"pid": pid, "app_id": "looking-glass-client",
                         "window_id": f"0x5a{index:02d}"})
        answers[entry["id"]] = {
            "surface": surface,
            "answer": provenance(entry, pid, domain_of),
        }
    usb = dict(runtime.USB_ANSWER, devices=runtime.USB_ANSWER["devices"][:3])
    workbench = dict(runtime.WORKBENCH_ANSWER, errors=[])
    body = (SCENE.replace("@@FIXTURE@@", json.dumps(fixture))
            .replace("@@ROWS@@", json.dumps(inventory))
            .replace("@@NETWORKS@@", json.dumps(seal.network_rows()))
            .replace("@@FOCUS@@", json.dumps(answers))
            .replace("@@LADDER@@", json.dumps(gpu_ladder()))
            .replace("@@OUT@@", json.dumps(str(out)))
            .replace("@@SUFFIX@@", json.dumps(size))
            .replace("@@PLAN@@", json.dumps(create.real_plan()))
            .replace("@@WORKBENCH@@", json.dumps(workbench))
            .replace("@@USB@@", json.dumps(usb))
            .replace("@@NITRO@@", json.dumps(runtime.NITRO_STATUS))
            .replace("@@BASE@@", str(runtime.FAILURE_BASE)))
    owner = fixture["gpu_owner"]
    source, messages = harness(*LAYOUT, inventory, body,
                               gpu={"text": owner, "class": "", "known": True,
                                    "owner": owner, "bound": True},
                               trust=boot_claim(fixture))
    ground = "Rectangle { anchors.fill: parent; color: sharedTheme.base }"
    if source.count(ground) != 1:
        raise SystemExit("the runtime harness lost its ground plate")
    source = source.replace(ground, ground + "\n    Image { anchors.fill: parent; "
                            f"source: {json.dumps(wallpaper.as_uri())}; fillMode: Image.PreserveAspectCrop }}")
    return source, messages


def expected_names(fixture: dict, routes: list[str]) -> list[str]:
    stems = ([f"bar-{entry['id']}" for entry in fixture["focus"]]
             + [f"machine-{fixture['selected']}"] + routes)
    return [f"demo-{stem}-{size}.png" for size in SIZES for stem in stems]


def route_ids() -> list[str]:
    source = (runtime.QML / "ShellIpc.qml").read_text(encoding="utf-8")
    match = re.search(r"(?m)^    readonly property var navigationRoutes: \((\{.*?\n    \})\)$",
                      source, re.S)
    if match is None:
        raise SystemExit("ShellIpc.qml has no navigationRoutes table")
    return list(json.loads(match[1]))


def render(out: Path, fixture_path: Path = FIXTURE) -> list[Path]:
    fixture = load_fixture(fixture_path)
    runner = shutil.which("qmlscene", path="/usr/lib/qt6/bin") or shutil.which("qmlscene6")
    if not runner:
        raise SystemExit("Qt 6 qmlscene is required to render the demo surfaces")
    directory = stage()
    previous = os.environ.get("QT_SCALE_FACTOR")
    try:
        for size, ratio in SIZES.items():
            wallpaper = WALLPAPERS / f"isolation-ring-{size}.png"
            if not wallpaper.is_file():
                raise SystemExit(f"missing wallpaper {wallpaper.name}")
            os.environ["QT_SCALE_FACTOR"] = str(ratio)
            source, messages = scene(fixture, out, size, wallpaper)
            runtime.run(runner, directory, f"demo {size}", source, messages)
    finally:
        if previous is None:
            os.environ.pop("QT_SCALE_FACTOR", None)
        else:
            os.environ["QT_SCALE_FACTOR"] = previous
        shutil.rmtree(directory, ignore_errors=True)
    produced = [out / name for name in expected_names(fixture, route_ids())]
    missing = [path.name for path in produced if not path.is_file()]
    if missing:
        raise SystemExit("demo renders missing: " + ", ".join(missing))
    return produced


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, default=FIXTURE)
    args = parser.parse_args()
    out = args.out
    if out.is_symlink() or not out.is_dir():
        raise SystemExit(f"{out} is not a directory")
    out = out.resolve(strict=True)
    if out == ROOT or ROOT in out.parents:
        raise SystemExit("refusing to write renders inside the repository")
    if any(out.iterdir()):
        raise SystemExit(f"{out} is not empty")
    try:
        produced = render(out, args.fixture)
    except FixtureError as error:
        raise SystemExit(f"fixture refused: {error}") from None
    for path in produced:
        print(f"rendered {path.name}")
    print(LOCK_NOTE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
