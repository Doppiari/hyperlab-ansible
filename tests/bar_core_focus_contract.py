#!/usr/bin/env python3
"""The host bar's core and focus item say which Machine has focus.

ADR 0064 makes the core of the product glyph in the host bar a trust
indicator: the domain colour of the Machine that owns the focused window,
the HOST grey only while a host surface has focus, and a hollow core with
the word Unknown when focus cannot be proven to belong to either. Beside it
the focus item draws a MachineSphere with the Machine's name and domain as
words.

This contract runs the whole host-side chain on fixtures, for Sway and for
Hyprland:

  compositor focus (fake swaymsg / hyprctl) -> the real compositor adapter
      -> the real ShellState (runtime harness) -> its resolver request
      -> the real provenance resolver's answer -> the real bar

and reads the captured bar pixels, the runtime properties and the words for
five states: a host terminal, a dev viewer, a dirty viewer, a window with no
mapping and a stale focus source. Every fixture window carries a title that
names another Machine, so a mapping that read titles would be caught. It
also proves the resolver's answer does not depend on the title and that the
shell's mapping reads nothing but host provenance and the inventory.
Removing each domain palette key makes both the core and the words Unknown
under host and Machine focus; restoring it recovers the current answer.
Inventory states crashed and unknown keep the proven domain core, draw a
neutral sphere and display the state word beside the Machine name and domain.

`--renders DIR` keeps the fourteen bar captures (`<compositor>-<state>.png`).
What this does not prove: the real Quickshell runtime, real compositor
events and how the core reads on a real display. That is the operator's
check on the Nitro under both compositors.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml

import host_quickshell_runtime_contract as runtime
from trust_pool_v3_generated_contract import png_pixels

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "roles/host_desktop_common/files/quickshell/hyperlab"
ADAPTER = ROOT / "roles/host_desktop_common/files/privatestack-compositor-adapter.sh"
RESOLVER = ROOT / "tools/surface_provenance.py"
FIXTURE = ROOT / "tests/fixtures/bar-core-focus.json"
PALETTE = ROOT / "themes/trust-model/rendered/hyperlab-palette-quickshell.json"
COMPOSITORS = ("sway", "hyprland")
DOMAINS = ("host", "clean", "dev", "services", "dirty", "lab")
WIDTH, HEIGHT = 1440, 900
# Least per-channel distance between the Unknown core outline and the HOST
# grey or any domain colour (the neutral distance of ADR 0064).
NEUTRAL_DISTANCE = 48

# What the shell's mapping may read: host provenance, the reviewed identity
# list and the inventory row of the same Machine. Nothing a window or a guest
# supplies.
MAPPING_READS = {
    "provenance": {"state", "identity", "source", "domain", "reason"},
    "row": {"name", "provenance", "state"},
    "state": {"guestProvenanceIdentities"},
}

SCENARIO = r"""
            const states = @@STATES@@;
            const extra = @@EXTRA@@;
            const glyph = window.find(rail, "identity-glyph");
            const badge = window.find(rail, "provenance-badge");
            const sphere = window.find(rail, "focus-sphere");
            const words = window.find(rail, "focus-words");
            check(glyph !== null && badge !== null && sphere !== null && words !== null,
                  "the bar has no glyph core, focus item, sphere or words");
            if (window.firstFailure >= 0) {
                Qt.exit(@@BASE@@ + window.firstFailure);
                return;
            }
            check(badge.visible, "the focus item is hidden on a wide rail");

            function focus(event) {
                sharedState.observationNow = Date.now();
                sharedState.applyFocusPayload(event.line);
                check(Object.keys(sharedState.focusPayload).indexOf("title") < 0,
                      "the focused window title entered shell state");
                const asked = JSON.parse(sharedState.provenanceRequestLine).surface;
                check(asked.pid === event.request.pid && asked.app_id === event.request.app_id
                      && asked.window_id === event.request.window_id
                      && Object.keys(asked).length === 3,
                      "the resolver was asked about something other than the focused process");
                check(sharedState.focusedMachine.kind === "unknown" && glyph.coreHollow
                      && words.text === "Unknown",
                      "a surface still being resolved kept the previous answer");
            }

            function answer(event) {
                sharedState.applyProvenancePayload(JSON.stringify({
                    "schema": 1, "status": "ok",
                    "request": sharedState.provenanceRequest,
                    "provenance": event.answer
                }));
                if (event.stale_seconds)
                    sharedState.observationNow = Date.now() + event.stale_seconds * 1000;
            }

            function record(event) {
                const core = glyph.mapToItem(rail, glyph.width / 2, glyph.height / 2);
                const ball = sphere.mapToItem(rail, sphere.width / 2, sphere.height / 2);
                console.log("BARCORE " + JSON.stringify({
                    "name": event.name, "kind": rail.focusedMachine.kind,
                    "core": [core.x, core.y], "coreRadius": glyph.coreRadius,
                    "outerRadius": glyph.outerRadius,
                    "hollow": glyph.coreHollow, "level": rail.coreLevel,
                    "sphere": [ball.x, ball.y], "sphereSize": sphere.size,
                    "classified": sphere.classified, "sphereDomain": sphere.domain,
                    "sphereTone": String(sphere.tone),
                    "isHost": sphere.isHost, "sphereState": String(sphere.state),
                    "words": words.text, "wordsVisible": words.visible,
                    "wordsColour": String(words.color), "text": String(sharedTheme.textPrimary),
                    "accessible": badge.accessibleName,
                    "rail": String(sharedTheme.rail),
                    "width": rail.width, "height": rail.height
                }));
            }

            let index = 0;
            let previous = "";

            function next() {
                if (index >= states.length) {
                    finish();
                    return;
                }
                const event = states[index];
                sharedState.applyMachinePayload(JSON.stringify(event.inventory));
                focus(event);
                answer(event);
                if (event.machineState) {
                    check(String(sphere.state) === event.machineState && !sphere.classified,
                          "an unsupported Machine state was normalized or drawn as supported");
                    check(words.text === event.words,
                          "an unsupported Machine state has no visible state word");
                }
                // A new proven colour fades in; it never jumps or blends
                // through another hue.
                if (event.expect !== "unknown" && event.expect !== previous)
                    check(rail.coreLevel < 1, "a new core colour did not fade in");
                if (event.expect !== "unknown")
                    previous = event.expect;
                settleTimer.callback = function() {
                    record(event);
                    rail.grabToImage(function(result) {
                        check(result.saveToFile(@@OUT@@ + "-" + event.name + ".png"),
                              "the bar capture could not be saved");
                        index += 1;
                        next();
                    });
                };
                settleTimer.restart();
            }

            function finish() {
                const dev = states[1];
                const host = states[0];
                sharedState.applyMachinePayload(JSON.stringify(dev.inventory));

                // Re-validating the same Machine reads Unknown until the
                // resolver answers (checked in focus()), and the answer then
                // restores the colour without restarting the fade.
                focus(dev);
                answer(dev);
                check(sharedState.focusedMachine.kind === "machine" && rail.coreLevel === 1,
                      "re-validating the same Machine restarted the fade");

                // A missing domain colour makes both signals Unknown, even
                // when it belongs to another domain. Check live palette
                // changes as well as answers received during the gap.
                const palette = sharedTheme.palette;
                for (const event of [host, dev]) {
                    focus(event);
                    answer(event);
                    for (const domain of sharedTheme.provenanceIdentities) {
                        const partial = Object.assign({}, palette);
                        delete partial["dom_" + domain];
                        sharedTheme.palette = partial;
                        check(!sharedTheme.provenanceAvailable,
                              "the partial palette is still complete");
                        checkPaletteGap(event);
                        focus(event);
                        answer(event);
                        checkPaletteGap(event);
                        sharedTheme.palette = palette;
                        check(sharedTheme.provenanceAvailable && !glyph.coreHollow
                              && words.text === event.words && sphere.classified
                              && rail.focusedMachine.kind === sharedState.focusedMachine.kind,
                              "restoring the palette did not restore the focus answer");
                    }
                }

                function checkPaletteGap(event) {
                    check(sharedState.focusedMachine.kind ===
                          (event.expect === "host" ? "host" : "machine")
                          && rail.focusedMachine.kind === "unknown" && glyph.coreHollow
                          && words.text === "Unknown" && !sphere.classified
                          && badge.accessibleName.indexOf("Focus unknown") === 0,
                          "an incomplete palette left the core and the focus item disagreeing");
                }

                // With reduced motion a colour change is instant.
                sharedTokens.reducedMotion = true;
                focus(host);
                answer(host);
                check(sharedState.focusedMachine.kind === "host" && rail.coreLevel === 1,
                      "reduced motion still faded the core");
                sharedTokens.reducedMotion = false;

                // Two host sources that disagree prove nothing.
                sharedState.applyMachinePayload(JSON.stringify(extra.contradiction));
                focus(dev);
                answer(dev);
                check(sharedState.focusedMachine.kind === "unknown" && glyph.coreHollow
                      && words.text === "Unknown",
                      "the inventory named another domain and the bar still chose one");

                // A Machine the inventory has not confirmed keeps its proven
                // domain; only its state is not drawn.
                sharedState.applyMachinePayload(JSON.stringify(extra.unlisted));
                focus(dev);
                answer(dev);
                check(sharedState.focusedMachine.kind === "machine" && !glyph.coreHollow
                      && words.text === dev.words + " · state not confirmed" && !sphere.classified,
                      "an unconfirmed Machine state was drawn, or its domain was lost");

                // State updates do not need a new focus or resolver answer.
                const request = sharedState.provenanceRequest;
                for (const event of states.filter(event => event.machineState)) {
                    sharedState.applyMachinePayload(JSON.stringify(event.inventory));
                    check(sharedState.provenanceRequest === request
                          && rail.focusedMachine.kind === "machine" && !glyph.coreHollow
                          && rail.coreIdentity === dev.expect && !sphere.classified
                          && String(sphere.state) === event.machineState
                          && words.visible && words.text === event.words,
                          "an inventory-only update hid the unsupported state or its domain");
                }
                sharedState.applyMachinePayload(JSON.stringify(dev.inventory));
                check(sharedState.provenanceRequest === request && sphere.classified
                      && String(sphere.state) === "running" && words.text === dev.words,
                      "a confirmed running state did not clear the unsupported-state word");

                Qt.exit(window.firstFailure < 0 ? 0 : @@BASE@@ + window.firstFailure);
            }

            next();
"""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("Bar core focus contract: " + message)


def load_fixture() -> dict:
    try:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SystemExit(f"Bar core focus contract: unreadable fixture: {error}") from None
    names = [state["name"] for state in fixture["states"]]
    require(names == ["host", "dev", "dirty", "unmapped", "stale"],
            f"the fixture must hold the five reviewed states in order: {names}")
    require(len({machine["name"] for machine in fixture["machines"]}) == len(fixture["machines"]),
            "duplicated fixture Machine")
    require([case["state"] for case in fixture["inventory_states"]] == ["crashed", "unknown"],
            "the fixture must exercise crashed and unknown inventory states")
    return fixture


def focus_states(fixture: dict) -> list[dict]:
    """Reuse the registered dev window with each unsupported inventory state."""
    dev = fixture["states"][1]
    unsupported = [
        dict(dev, name="dev-" + case["state"], machine_state=case["state"], words=case["words"])
        for case in fixture["inventory_states"]
    ]
    # Capture inventory states before the stale fixture moves the clock
    # forward: returning it would revalidate the previous window as well.
    return fixture["states"][:-1] + unsupported + fixture["states"][-1:]


# ------------------------------------------------------------ compositors

def adapter_lines(fixture: dict, scratch: Path) -> dict[str, list[str]]:
    """The focus line the real adapter prints for every state and compositor."""
    bindir = scratch / "bin"
    bindir.mkdir()
    for name, body in (
        ("swaymsg", '#!/bin/bash\ncase "$*" in *get_tree*) cat "$FAKE_FOCUS" ;; *) exit 1 ;; esac\n'),
        ("hyprctl", '#!/bin/bash\n[[ $1 == activewindow ]] && cat "$FAKE_FOCUS" || exit 1\n'),
    ):
        (bindir / name).write_text(body, encoding="utf-8")
        (bindir / name).chmod(0o755)
    environment = {key: value for key, value in os.environ.items()
                   if key not in ("HYPRLAND_INSTANCE_SIGNATURE", "SWAYSOCK")}
    environment["PATH"] = str(bindir) + os.pathsep + environment.get("PATH", "")
    lines: dict[str, list[str]] = {}
    for compositor in COMPOSITORS:
        lines[compositor] = []
        for state in focus_states(fixture):
            node = dict(state[compositor])
            if compositor == "sway":
                node["focused"] = True
                node = {"id": 1, "nodes": [{"id": 2, "nodes": [node], "floating_nodes": []}],
                        "floating_nodes": []}
            payload = scratch / f"{compositor}-{state['name']}.json"
            payload.write_text(json.dumps(node), encoding="utf-8")
            result = subprocess.run(
                ["bash", str(ADAPTER), "focused-window-json"], capture_output=True, text=True,
                timeout=30, check=False,
                env=dict(environment, HYPERLAB_COMPOSITOR_BACKEND=compositor,
                         FAKE_FOCUS=str(payload)),
            )
            require(result.returncode == 0 and result.stdout.count("\n") == 1,
                    f"{compositor}: the adapter did not print one focus line: {result.stderr.strip()}")
            lines[compositor].append(result.stdout.strip())
    return lines


# --------------------------------------------------------------- resolver

def load_resolver():
    spec = importlib.util.spec_from_file_location("bar_core_focus_resolver", RESOLVER)
    require(spec is not None and spec.loader is not None, "the resolver cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolver_context(fixture: dict, scratch: Path):
    """The real resolver bound to fixture specs, transports and /proc."""
    resolver = load_resolver()
    repo = scratch / "repo"
    (repo / "vm-specs").mkdir(parents=True)
    entries = []
    for machine in fixture["machines"]:
        spec = {"name": machine["name"], "network_profile": machine["network_profile"]}
        if machine["surface_kind"] == "looking-glass":
            spec.update(device_profile="vfio", looking_glass=True)
        spec_path = repo / "vm-specs" / f"{machine['name']}.yml"
        spec_path.write_text(yaml.safe_dump(spec), encoding="utf-8")
        transport = scratch / f"transport-{machine['surface_kind']}"
        transport.write_text("#!/bin/sh\n", encoding="utf-8")
        resolver.EXPECTED_EXECUTABLES[machine["surface_kind"]] = str(transport.resolve())
        proc = scratch / "proc" / str(machine["pid"])
        proc.mkdir(parents=True)
        (proc / "stat").write_text(
            f"{machine['pid']} (viewer) S " + "0 " * 18 + f"{machine['start_ticks']} 0 0\n",
            encoding="utf-8")
        (proc / "exe").symlink_to(transport)
        entries.append({
            "pid": machine["pid"], "process_start_ticks": machine["start_ticks"],
            "executable": str(transport.resolve()), "surface_kind": machine["surface_kind"],
            "domain": machine["name"],
            "spec_sha256": hashlib.sha256(spec_path.read_bytes()).hexdigest(),
            "registered_by": "hyperlabctl",
        })
    registry = {"version": 1, "entries": entries}

    def resolve(surface: dict) -> dict:
        return resolver.resolve(repo=repo, surface=surface, registry=registry,
                                proc_root=scratch / "proc")

    return resolve


def title_independence(fixture: dict, lines: dict[str, list[str]], resolve) -> None:
    """The resolver's answer is the same whatever the window says it is."""
    names = [machine["name"] for machine in fixture["machines"]] + ["host", "", "CLEAN trusted"]
    for compositor in COMPOSITORS:
        for state, line in zip(focus_states(fixture), lines[compositor], strict=True):
            surface = json.loads(line)
            surface.pop("fullscreen", None)
            plain = dict(surface, title="")
            expected = resolve(plain)
            for title in names:
                require(resolve(dict(surface, title=title)) == expected,
                        f"{compositor}/{state['name']}: the resolver answer follows the title {title!r}")

    tree = ast.parse(RESOLVER.read_text(encoding="utf-8"))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "resolve"]
    require(len(functions) == 1, "the resolver has no single resolve()")
    read = {node.value for node in ast.walk(functions[0])
            if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    require("title" not in read, "resolve() reads the window title")


# ------------------------------------------------------------ shell source

def function_body(source: str, name: str) -> str:
    match = re.search(r"(?m)^    function " + name + r"\(([^)]*)\) \{", source)
    require(match is not None, f"ShellState has no {name}()")
    index, depth = match.end(), 1
    while index < len(source) and depth:
        depth += {"{": 1, "}": -1}.get(source[index], 0)
        index += 1
    return match.group(1) + "\n" + source[match.end():index - 1]


def mapping_contract() -> None:
    """The mapping reads host provenance and the inventory, nothing else."""
    source = (QML / "ShellState.qml").read_text(encoding="utf-8")
    body = function_body(source, "focusedMachineFor")
    code = re.sub(r"//[^\n]*", "", body)
    code = re.sub(r'"(?:[^"\\]|\\.)*"', '""', code)
    parameters = [part.strip() for part in code.split("\n", 1)[0].split(",")]
    require(parameters == ["provenance", "inventory"],
            f"focusedMachineFor() takes {parameters}, not (provenance, inventory)")
    for owner, member in re.findall(r"\b(\w+)\s*\.\s*(\w+)", code):
        if owner in MAPPING_READS:
            require(member in MAPPING_READS[owner],
                    f"the focus mapping reads {owner}.{member}")
    require(not re.search(r"\b(?:title|clipboard|agent|focusPayload|focusedSurface)\b", code),
            "the focus mapping reads a window or guest field")
    binding = re.search(r"readonly property var focusedMachine:\s*state\.focusedMachineFor\(\s*"
                        r"state\.focusedProvenance\s*,", source)
    require(binding is not None, "focusedMachine is not derived from focusedProvenance")


# ------------------------------------------------------------------ scene

def inventory(fixture: dict) -> list[dict]:
    rows = []
    for machine in fixture["machines"]:
        row = dict(runtime.MACHINE_TEMPLATE)
        row.update(name=machine["name"], provenance=machine["network_profile"],
                   state=machine["state"], network=machine["network_profile"],
                   networks=[machine["network_profile"]], gpu_relation="configured",
                   gpu="Passthrough configured")
        rows.append(row)
    return rows


def scene(fixture: dict, lines: list[str], resolve, out: Path) -> tuple[str, list[str]]:
    def payload(machines: list[dict]) -> dict:
        return {"text": f"{len(machines)}/{len(machines)}", "class": "ok",
                "machines_available": True, "machines": machines}

    rows = inventory(fixture)
    states = []
    for state, line in zip(focus_states(fixture), lines, strict=True):
        surface = json.loads(line)
        request = {"pid": surface["pid"], "app_id": surface["app_id"],
                   "window_id": surface["window_id"]}
        answer = resolve(request)
        machines = [dict(row, state=state["machine_state"])
                    if "machine_state" in state and row["name"] == answer["domain"] else row
                    for row in rows]
        states.append({"name": state["name"], "expect": state["expect"],
                       "words": state["words"], "stale_seconds": state.get("stale_seconds", 0),
                       "line": line, "request": request, "answer": answer,
                       "machineState": state.get("machine_state", ""), "inventory": payload(machines)})
    contradiction = [dict(row, provenance="clean") if row["name"] == "dev-01" else row for row in rows]
    unlisted = [row for row in rows if row["name"] != "dev-01"]

    body = (SCENARIO
            .replace("@@STATES@@", json.dumps(states))
            .replace("@@EXTRA@@", json.dumps({"contradiction": payload(contradiction),
                                              "unlisted": payload(unlisted)}))
            .replace("@@OUT@@", json.dumps(str(out)))
            .replace("@@BASE@@", str(runtime.FAILURE_BASE)))
    harness = runtime.HARNESS
    require(harness.count("@@GRAB@@") == 1, "the runtime harness changed shape")
    runtime.HARNESS = harness.replace("@@GRAB@@", "")
    try:
        return runtime.scenario_source(WIDTH, HEIGHT, rows, body)
    finally:
        runtime.HARNESS = harness


def run_scene(directory: Path, source: str, messages: list[str], compositor: str) -> list[dict]:
    runner = shutil.which("qmlscene", path="/usr/lib/qt6/bin") or shutil.which("qmlscene6")
    require(bool(runner), "Qt 6 qmlscene is required")
    path = directory / "bar-core.qml"
    path.write_text(source, encoding="utf-8")
    try:
        result = subprocess.run(
            [str(runner), str(path)], capture_output=True, text=True, timeout=120, check=False,
            env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software",
                 "QT_FORCE_STDERR_LOGGING": "1", "QML_DISABLE_DISK_CACHE": "1",
                 "XDG_CACHE_HOME": str(directory / "cache")},
        )
    except subprocess.TimeoutExpired:
        raise SystemExit(f"Bar core focus contract: {compositor}: the scene never completed") from None
    lines = (result.stdout + result.stderr).splitlines()
    records = [json.loads(line.split("BARCORE ", 1)[1]) for line in lines if "BARCORE " in line]
    noise = [line for line in lines if line.strip() and "BARCORE " not in line
             and "Could not find the Qt platform plugin" not in line
             and "QStandardPaths" not in line
             and not line.startswith("qt.tools.qmlscene.deprecated:")]
    code = result.returncode
    if code >= runtime.FAILURE_BASE and code - runtime.FAILURE_BASE < len(messages):
        raise SystemExit(f"Bar core focus contract: {compositor}: "
                         f"{messages[code - runtime.FAILURE_BASE]}")
    require(code == 0 and not noise, f"{compositor}: Qt execution failed ({code}): {noise[:6]}")
    return records


# ----------------------------------------------------------------- pixels

def rgb(colour: str) -> tuple[int, int, int]:
    require(re.fullmatch(r"#[0-9a-fA-F]{6}", colour) is not None, f"colour {colour!r}")
    return int(colour[1:3], 16), int(colour[3:5], 16), int(colour[5:7], 16)


def distance(first: tuple[int, ...], second: tuple[int, ...]) -> int:
    return max(abs(a - b) for a, b in zip(first, second, strict=True))


def pixel(image: bytes, width: int, x: float, y: float) -> tuple[int, int, int]:
    offset = (int(y) * width + int(x)) * 3
    red, green, blue = image[offset:offset + 3]
    return red, green, blue


def hue_nearest(colour: tuple[int, int, int], palette: dict) -> str:
    """The domain whose colour points the same way in RGB."""
    def unit(value: tuple[int, ...]) -> tuple[float, ...]:
        norm = sum(channel * channel for channel in value) ** 0.5 or 1.0
        return tuple(channel / norm for channel in value)

    here = unit(colour)
    return max(DOMAINS, key=lambda domain: sum(
        a * b for a, b in zip(here, unit(rgb(palette["dom_" + domain])), strict=True)))


def check_render(compositor: str, state: dict, record: dict, image: bytes, palette: dict) -> None:
    where = f"{compositor}/{state['name']}"
    width = int(record["width"])
    ground = rgb(record["rail"])
    text = rgb(record["text"])
    identities = {domain: rgb(palette["dom_" + domain]) for domain in DOMAINS}
    cx, cy = record["core"]
    centre = pixel(image, width, cx, cy)
    expect = state["expect"]

    require(record["kind"] == ("unknown" if expect == "unknown"
                               else "host" if expect == "host" else "machine"),
            f"{where}: the bar placed focus on {record['kind']}")
    require(record["words"] == state["words"] and record["wordsVisible"],
            f"{where}: the focus item says {record['words']!r}")
    require(rgb(record["wordsColour"]) == text,
            f"{where}: the focus words carry a colour; the sphere and the core do")

    if expect == "unknown":
        require(record["hollow"], f"{where}: Unknown is not drawn hollow")
        # The mark sits on its own control fill. Its ground is read in the
        # gap above the core, where geometry B draws nothing.
        mark = pixel(image, width, cx, cy - (record["coreRadius"] + record["outerRadius"]) / 2)
        require(distance(centre, mark) <= 6, f"{where}: the Unknown core is filled: {centre}")
        reach = record["coreRadius"]
        ring = [pixel(image, width, cx + dx, cy + dy)
                for dy in range(-int(reach) - 1, int(reach) + 2)
                for dx in range(-int(reach) - 1, int(reach) + 2)
                if (dx + 0.5) ** 2 + (dy + 0.5) ** 2 <= (reach + 1) ** 2]
        brightest = max(ring, key=sum)
        require(distance(brightest, mark) > NEUTRAL_DISTANCE,
                f"{where}: the Unknown core has no visible outline")
        for domain, colour in identities.items():
            require(distance(brightest, colour) >= NEUTRAL_DISTANCE,
                    f"{where}: Unknown is drawn in the {domain} colour: {brightest}")
        require(not record["classified"], f"{where}: the Unknown sphere is coloured")
        sphere = pixel(image, width, *record["sphere"])
        require(distance(sphere, ground) <= 6, f"{where}: the Unknown sphere is filled: {sphere}")
        require(record["accessible"].startswith("Focus unknown"),
                f"{where}: accessible name {record['accessible']!r}")
        return

    domain = "host" if expect == "host" else expect
    require(not record["hollow"] and record["level"] == 1, f"{where}: the core is not filled")
    require(distance(centre, identities[domain]) <= 6,
            f"{where}: the core is {centre}, not the {domain} colour {identities[domain]}")
    require(record["sphereDomain"] == domain and record["isHost"] == (domain == "host"),
            f"{where}: the focus sphere is not the {domain} sphere")
    sphere = pixel(image, width, *record["sphere"])
    identity_words = record["words"]
    if "machine_state" in state:
        require(not record["classified"] and record["sphereState"] == state["machine_state"],
                f"{where}: an unsupported Machine state was normalized or drawn as supported")
        require(distance(sphere, ground) <= 6,
                f"{where}: the unsupported-state sphere is filled: {sphere}")
        sx, sy = record["sphere"]
        reach = record["sphereSize"] / 2
        ring = [pixel(image, width, sx + dx, sy + dy)
                for dy in range(-int(reach), int(reach) + 1)
                for dx in range(-int(reach), int(reach) + 1)
                if (dx + 0.5) ** 2 + (dy + 0.5) ** 2 <= reach ** 2]
        brightest = max(ring, key=sum)
        require(rgb(record["sphereTone"]) == text,
                f"{where}: the unsupported-state sphere tone is not neutral")
        # The one-pixel rim is antialiased at bar size. Its pixels must be
        # the text tone composited over the rail, with a visible coverage.
        coverage = (sum(brightest) - sum(ground)) / (sum(text) - sum(ground))
        composite = tuple(round(back + coverage * (front - back))
                          for back, front in zip(ground, text, strict=True))
        require(0.75 <= coverage <= 1 and distance(brightest, composite) <= 6,
                f"{where}: the unsupported-state sphere has no neutral outline: {brightest}")
        for identity, colour in identities.items():
            require(distance(brightest, colour) >= NEUTRAL_DISTANCE,
                    f"{where}: the unsupported-state outline uses the {identity} colour")
        require(state["machine_state"] in record["words"].split(" · ")
                and record["accessible"].endswith(", " + state["machine_state"]),
                f"{where}: the unsupported Machine state is not visible and accessible")
        identity_words = identity_words.removesuffix(" · " + state["machine_state"])
    else:
        require(record["classified"] and hue_nearest(sphere, palette) == domain,
                f"{where}: the focus sphere is drawn {sphere}, not in the {domain} colour")
    # Colour never stands alone: a coloured sphere has its domain as a word.
    require(identity_words == "Host" if domain == "host"
            else identity_words.endswith(" · " + domain),
            f"{where}: the focus item shows a colour without the domain word")
    require(domain in record["accessible"].lower(),
            f"{where}: accessible name {record['accessible']!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--renders", type=Path, help="keep the bar captures in this directory")
    args = parser.parse_args()

    fixture = load_fixture()
    mapping_contract()
    palette = json.loads(PALETTE.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory(prefix="bar-core-focus-") as temporary:
        scratch = Path(temporary)
        lines = adapter_lines(fixture, scratch)
        resolve = resolver_context(fixture, scratch)
        title_independence(fixture, lines, resolve)

        staged = runtime.stage()
        try:
            for compositor in COMPOSITORS:
                out = scratch / compositor
                source, messages = scene(fixture, lines[compositor], resolve, out)
                records = run_scene(staged, source, messages, compositor)
                require([record["name"] for record in records]
                         == [state["name"] for state in focus_states(fixture)],
                         f"{compositor}: not every state was captured")
                images = []
                for state, record in zip(focus_states(fixture), records, strict=True):
                    capture = Path(f"{out}-{state['name']}.png")
                    image = png_pixels(capture, (int(record["width"]), int(record["height"])))
                    if args.renders:
                        args.renders.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(capture, args.renders / capture.name)
                    check_render(compositor, state, record, image, palette)
                    images.append(image)
                require(len(set(images[:4])) == 4,
                        f"{compositor}: two focus states share one bar drawing")
        finally:
            shutil.rmtree(staged, ignore_errors=True)

    print("Bar core focus contract: OK (Sway and Hyprland: host, dev, dirty, unmapped and "
          "stale focus; title-independent mapping; hollow Unknown; one answer for core and item; "
          "visible unsupported inventory states; fade and reduced motion)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
