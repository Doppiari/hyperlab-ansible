#!/usr/bin/env python3
"""Execute the Sfere map with existing shell sources and inert transports."""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import re
import shutil
from types import SimpleNamespace
from unittest.mock import patch

import yaml

import host_quickshell_runtime_contract as runtime
from host_quickshell_qml_wiring_contract import blocks, strip_noise
from machine_sphere_contract import string_literals
from recovery_gpu_ladder_contract import cli_ladder
from trust_pool_v3_generated_contract import png_pixels
from hyperlabctl.commands.net import NetCommand

ROOT = runtime.ROOT
FIXTURE = ROOT / "tests/fixtures/sfere-view.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("Sfere view contract: " + message)


def network_rows() -> list[dict]:
    """The real net list formatter, with a declared and active network fixture."""
    config = yaml.safe_load((ROOT / "group_vars/all/networks.yml").read_text())
    ctx = SimpleNamespace(config=SimpleNamespace(var=lambda key, default: config.get(key, default)))
    with patch("hyperlabctl.commands.net.doc.build", return_value={
        "networks": {"missing": [], "inactive": []}
    }), redirect_stdout(io.StringIO()) as out:
        require(NetCommand().run(SimpleNamespace(net_action="list", json=True), ctx) == 0,
                "net list fixture failed")
    return json.loads(out.getvalue())


def source_contract() -> None:
    import gi
    gi.require_version("Gdk", "4.0")
    from gi.repository import Gdk

    coordinator = (runtime.QML / "ShellSurfaces.qml").read_text()
    destinations = re.search(r"readonly property var destinations:\s*(\[[^]]*\])", coordinator)
    require(destinations is not None and json.loads(destinations[1])[0] == "sfere",
            "Sfere is not the first workspace destination")
    deploy = yaml.safe_load((ROOT / "group_vars/all/host-desktop.yml").read_text())
    require("SfereView.qml" in deploy["host_desktop_common_shell_stage"]["surface_files"],
            "SfereView is absent from the installed shell")
    source = (runtime.QML / "SfereView.qml").read_text()
    colour = Gdk.RGBA()
    literals = string_literals(source)
    require(not any(colour.parse(word) or re.search(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgb|hsl|hsv)a?\(", word)
                    for word in literals), "colour literal in SfereView.qml")
    clean = strip_noise(source)
    require(not re.search(r"\bQt\.(?:rgba?|hsla?|hsva?|color)\s*\(", clean),
            "colour constructor in SfereView.qml")
    require(not re.search(r"\b(?:\w*Animation|Transition|Timer|Process|FileView)\s*\{", clean),
            "the static map gained an animation or a data transport")
    require(len(list(blocks(clean, "MachineSphere", False))) == 1,
            "the map must reuse MachineSphere for every Machine")
    require(len(list(blocks(clean, "IsolationGlyph", False))) == 1,
            "the map must reuse geometry B for the host")
    root = (runtime.QML / "shell.qml").read_text()
    require("networksMapVisible:" in root, "the root does not expose map visibility to the shared network source")


def declared_links(case: dict, networks: list[dict]) -> list[list[str]]:
    """Host links from each row's own attachment, never from its domain."""
    paths = {row["name"] for row in networks if row["forward"] == "nat" and row["state"] == "active"}
    out = []
    for row in case["machines"]:
        require("networks" in row, f"{row['name']} has no declared attachment")
        path = next((name for name in row["networks"] or [] if name in paths), None)
        if path is not None:
            out.append(["host", row["name"], path])
    return out


def rows_for(case: dict) -> list[dict]:
    return [dict(runtime.MACHINE_TEMPLATE, name=row["name"], provenance=row["domain"],
                 state=row["state"], networks=row["networks"], network=(row["networks"] or [None])[0],
                 lifecycle="disposable" if row["disposable"] else "permanent",
                 gpu_relation="none", gpu="", vfio=False)
            for row in case["machines"] if row["domain"] != "external"]


SETUP = r'''
            sharedTokens.reducedMotion = true;
            const fixture = @@CASE@@;
            const networks = @@NETWORKS@@;
            const ladder = @@LADDER@@;
            sharedState.applyOutsideDomainsPayload(JSON.stringify({machines_available: true,
                machines: fixture.machines.map(row => ({name: row.name, state: row.state, networks: row.networks,
                                                       managed: row.domain !== "external"}))}));
            sharedState.applyFeatures('{"networks_view_enabled":true}');
            sharedSurfaces.openWorkspace("sfere");
            const map = find(workspaceSurface, "sfere-view");
            check(map !== null && map.visible, "Sfere view did not open");
            if (!map) { Qt.exit(1); return; }
            function nodes(root, predicate) {
                let out = predicate(root) ? [root] : [];
                for (const child of root.children || []) out = out.concat(nodes(child, predicate));
                return out;
            }
            function slots() { return nodes(map, item => item.objectName.indexOf("sfere-slot-") === 0); }
            function balls() { return nodes(map, item => item.objectName.indexOf("sfere-sphere-") === 0); }
            function lines() { return nodes(map, item => item.objectName.indexOf("sfere-link-") === 0 && item.visible); }
            // Distance from a point to a segment, and from a box to a segment.
            function reach(px, py, ax, ay, bx, by) {
                const dx = bx - ax, dy = by - ay;
                const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy || 1)));
                return Math.hypot(px - ax - t * dx, py - ay - t * dy);
            }
            function boxReach(x, y, w, h, ax, ay, bx, by) {
                for (let step = 0; step <= 64; step++) {
                    const px = ax + (bx - ax) * step / 64, py = ay + (by - ay) * step / 64;
                    if (px >= x && px <= x + w && py >= y && py <= y + h) return 0;
                }
                return Math.min(reach(x, y, ax, ay, bx, by), reach(x + w, y, ax, ay, bx, by),
                                reach(x, y + h, ax, ay, bx, by), reach(x + w, y + h, ax, ay, bx, by),
                                ...[[ax, ay], [bx, by]].map(([px, py]) =>
                                    Math.hypot(Math.max(x - px, 0, px - x - w), Math.max(y - py, 0, py - y - h))));
            }
            function overlaps(a, b) {
                return a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;
            }
            function answerNetworks(rows) {
                if (!sharedState.networksInFlight) sharedState.requestNetworks();
                sharedState.finishNetworks(sharedState.networksFlightGeneration, JSON.stringify(rows), 0);
                keyEvents.wait(30);
            }
            keyEvents.wait(30);
            check(sharedState.networksReadable && sharedState.networksInFlight,
                  "opening Sfere did not reuse the enabled Networks reader");
            answerNetworks(networks);
            const host = find(map, "sfere-host");
'''

CHECKS = r'''
            check(workspaceSurface.destinations[0].id === "sfere",
                  "Sfere is not the first visible tab");
            check(Qt.colorEqual(host.core, sharedTheme.provenanceColor("host"))
                  && Qt.colorEqual(host.stroke, sharedTheme.provenanceColor("host")),
                  "the centre is tinted");
            const plot = nodes(map, item => item.contentX !== undefined)[0];
            if (map.width >= 1600)
                check(plot.contentHeight <= plot.height && plot.contentWidth <= plot.width,
                      "full-size fixture clipped the scene behind the readout");
            const originalFocus = sharedState.provenanceObservation;
            sharedState.focusSourceState = "ok";
            sharedState.focusObservedAt = Date.now();
            for (const row of fixture.machines.filter(row => row.domain !== "external")) {
                sharedState.provenanceObservation = sharedState.provenanceResult(
                    "resolved", row.domain, "host-owned-vm-spec", row.name, "managed-surface-resolved", "Fixture focus");
                check(Qt.colorEqual(host.core, sharedTheme.provenanceColor("host"))
                      && Qt.colorEqual(host.stroke, sharedTheme.provenanceColor("host")),
                      "Machine focus tinted the centre");
            }
            sharedState.provenanceObservation = originalFocus;
            check(new Set(slots().map(slot => slot.objectName)).size === slots().length,
                  "count sphere key collided with a Machine name");
            check(map.members.length === fixture.machines.length, "map lost or duplicated a Machine");
            check(slots().length <= 24 && slots().reduce((n, item) => n + item.entry.count, 0) === fixture.machines.length,
                  "collapse lost Machines or drew more than 24 spheres");
            if (fixture.machines.length <= 24)
                check(slots().length === fixture.machines.length, "map collapsed a legible inventory");
            for (const slot of slots()) {
                const inner = slot.entry.observed === "running";
                const radius = inner ? map.orbitInner : map.orbitOuter;
                check(Math.abs(slot.orbit - radius) < 0.01,
                      "orbit radius depends on the domain");
                check(Math.abs(Math.hypot(slot.centreX - map.centreX,
                      (slot.centreY - map.centreY) / map.tilt) - radius) < 0.01,
                      "drawn orbit radius depends on the domain");
                check(slot.z === (Math.sin(slot.angle) < 0 ? 1 : 3), "sphere depth order is wrong");
                check(slot.width >= 32 && slot.x >= 0 && slot.y >= 0
                      && slot.x + slot.width <= map.sceneWidth && slot.y + slot.height <= map.sceneHeight,
                      "sphere is too small or escapes the scene");
                for (const other of slots()) {
                    if (other === slot) continue;
                    check(Math.hypot(slot.centreX - other.centreX, slot.centreY - other.centreY)
                          >= (slot.width + other.width) / 2, "spheres overlap");
                }
                const sphere = find(map, "sfere-sphere-" + slot.entry.key);
                check(sphere && sphere.domain === slot.entry.domain && sphere.state === slot.entry.sphereState,
                      "map does not render the confirmed sphere inputs");
                if (slot.entry.kind === "external")
                    check(!sphere.classified && slot.entry.sector === "external",
                          "external Machine borrowed a domain colour");
                if (slot.entry.kind === "machine")
                    check(sphere.disposable === fixture.machines.find(row => row.name === slot.entry.id).disposable,
                          "map lost disposable marks");
                check(slot.activeFocusOnTab && slot.Accessible.name.indexOf(slot.entry.name) >= 0,
                      "sphere lost keyboard focus or its accessible name");
            }
            const declared = fixture.links.map(pair => pair[1]);
            for (const line of lines()) {
                const slot = slots().find(item => item.entry.key === line.machine);
                const members = slot.entry.members || [{name: slot.entry.id}];
                check(members.every(row => fixture.links.some(pair => pair[1] === row.name && pair[2] === line.network)),
                      "a link is drawn for a pair the network source does not declare");
                check(networks.some(row => row.name === line.network && row.forward === "nat" && row.state === "active"),
                      "a link does not name an active declared NAT network");
            }
            const stroke = sharedTokens.focusOutline / 2;
            for (const line of lines()) {
                const own = slots().find(item => item.entry.key === line.machine);
                check(line.span >= sharedTokens.spaceLg, "a declared link is too short to be seen");
                for (const slot of slots()) {
                    const name = find(map, "sfere-name-" + slot.entry.key);
                    const corner = name.mapToItem(slot.parent, 0, 0);
                    const clear = boxReach(corner.x, corner.y, name.width, name.height,
                                           line.fromX, line.fromY, line.toX, line.toY);
                    if (slot === own) {
                        check(!name.visible || clear > stroke, "a link strikes through its own Machine's name");
                        continue;
                    }
                    check(reach(slot.centreX, slot.centreY, line.fromX, line.fromY, line.toX, line.toY)
                          > slot.width / 2 + sharedTokens.spaceSm,
                          "a link passes through another sphere");
                    check(!name.visible || clear > sharedTokens.spaceXs, "a link crosses another sphere's name");
                }
                for (const word of [find(map, "sfere-host-word"), find(map, "sfere-host-gpu")]) {
                    const box = word.mapToItem(own.parent, word.childrenRect.x, word.childrenRect.y);
                    check(!word.visible || boxReach(box.x, box.y, Math.max(word.width, word.childrenRect.width),
                                                    Math.max(word.height, word.childrenRect.height),
                                                    line.fromX, line.fromY, line.toX, line.toY) > stroke,
                          "a link strikes through the host's words");
                }
            }
            const names = slots().map(slot => {
                const name = find(map, "sfere-name-" + slot.entry.key);
                const corner = name.mapToItem(slot.parent, 0, 0);
                return {slot: slot, visible: name.visible, x: corner.x, y: corner.y, width: name.width, height: name.height};
            }).filter(name => name.visible);
            for (const name of names) {
                for (const slot of slots())
                    check(slot === name.slot || !overlaps(name, slot), "a Machine name covers another sphere");
                for (const other of names)
                    check(other === name || !overlaps(name, other), "two Machine names overlap");
            }
            for (const sector of map.sectors) {
                const heading = find(map, "sfere-sector-" + sector.id);
                const corner = heading.mapToItem(plot, 0, 0);
                if (map.width >= 1600)
                    check(corner.x >= 0 && corner.y >= 0 && corner.x + heading.width <= plot.width
                          && corner.y + heading.height <= plot.height,
                          "a sector heading leaves the view");
                for (const slot of slots())
                    check(!overlaps(heading, slot), "a sector heading covers a sphere");
                for (const name of names)
                    check(!overlaps(heading, name), "a sector heading covers a Machine name");
            }
            for (const slot of slots().filter(item => item.entry.kind === "group"))
                check(slot.entry.members.every(row => (row.observed === "running") === (slot.orbitName === "inner")),
                      "a count sits on an orbit some of its Machines are not on");
            if (fixture.machines.length <= 24)
                check(lines().map(line => slots().find(slot => slot.entry.key === line.machine).entry.id).sort().join(",") === declared.sort().join(","),
                      "map links differ from declared attachments");
            const owners = balls().filter(ball => ball.gpuOwner);
            check(owners.length === (fixture.gpu_owner.length ? 1 : 0)
                  && (!owners.length || owners[0].machineName === fixture.gpu_owner)
                  && find(map, "sfere-host-gpu").visible === (fixture.gpu_owner.length === 0),
                  "GPU token differs from the ownership source");
            for (const sector of map.sectors) {
                const mark = find(map, "sfere-sector-reboot-" + sector.id);
                const rung = ladder.find(row => row.name === sector.id);
                check(mark !== null && mark.visible === (rung !== undefined && !rung.reachable),
                      "ladder mark differs from hyperlabctl trust");
            }
            const list = find(map, "sfere-list");
            const spoken = nodes(list, item => item.Accessible.role === Accessible.ListItem).map(item => item.Accessible.name);
            check(spoken.length === fixture.machines.length + 1 && spoken[0].indexOf("Host") === 0
                  && fixture.machines.every(row => spoken.filter(word => word.indexOf(row.name + ",") === 0).length === 1),
                  "the screen reader list lost an underlying Machine");
            const beforeSlots = slots();
            sharedState.applyMachinePayload(JSON.stringify({machines_available: true, machines: sharedState.machines}));
            keyEvents.wait(30);
            check(slots().every((slot, i) => slot === beforeSlots[i]), "identical poll rebuilt the spheres");
            // Rebuilt spheres leave later steps holding destroyed items: stop
            // on the recorded failure instead of hanging on a TypeError.
            if (window.firstFailure >= 0) { Qt.exit(40 + window.firstFailure); return; }
            const phases = balls().map(ball => ball.phase);
            keyEvents.wait(180);
            check(balls().every((ball, i) => ball.phase === phases[i]), "reduced motion animated a sphere");
            check(find(map, "sfere-orbits").visible === (fixture.machines.length > 0),
                  "host alone still drew orbits");
            check(find(map, "sfere-create").visible === (fixture.machines.length === 0),
                  "host alone must offer one Create action");
'''

INTERACTION = r'''
            const order = map.slots.map(slot => slot.entry.key);
            const first = find(map, "sfere-slot-" + order[0]);
            find(workspaceSurface, "machine-stage").creating = true;
            first.forceActiveFocus();
            for (let index = 0; index < order.length; index++) {
                const current = find(map, "sfere-slot-" + order[index]);
                check(current.activeFocus, "arrows did not follow sector order");
                check(find(map, "sfere-readout").text.indexOf(current.entry.name) >= 0
                      && find(map, "sfere-readout").text.indexOf(current.entry.observed) >= 0
                      && find(map, "sfere-readout").text.indexOf(current.entry.domain) >= 0,
                      "keyboard focus lost Machine name, domain or state");
                keyEvents.keyClick(Qt.Key_Right);
            }
            check(first.activeFocus, "arrows did not wrap in sector order");
            keyEvents.keyClick(Qt.Key_Return);
            check(sharedSurfaces.workspaceView === "machines" && sharedSurfaces.selectedMachineId === first.entry.id
                  && !find(workspaceSurface, "machine-stage").creating
                  && find(workspaceSurface, "machine-context-sphere").visible,
                  "Enter did not open the existing Machine pane");
            sharedSurfaces.openWorkspace("sfere");
            keyEvents.wait(30);
            const target = find(map, "sfere-slot-machine:dev-desk");
            keyEvents.mouseMove(target, target.width / 2, target.height / 2);
            keyEvents.wait(30);
            check(target.hovered && find(map, "sfere-readout").text.indexOf("dev-desk") >= 0,
                  "hover did not show the Machine readout");
            target.forceActiveFocus();
            keyEvents.keyClick(Qt.Key_Left);
            check(find(map, "sfere-slot-machine:clean-desk").activeFocus
                  && find(map, "sfere-readout").text.indexOf("clean-desk") >= 0,
                  "keyboard focus retained another sphere's hover readout");
            keyEvents.mouseMove(window.contentItem, 0, 0);
            keyEvents.mouseMove(target, target.width / 2, target.height / 2);
            keyEvents.wait(10);
            check(find(map, "sfere-readout").text.indexOf("dev-desk") >= 0,
                  "new hover retained another sphere's focused readout");
            sharedState.applyMachinePayload(JSON.stringify({machines_available: true, machines: sharedState.machines}));
            keyEvents.wait(30);
            check(find(map, "sfere-slot-machine:clean-desk").activeFocus
                  && find(map, "sfere-readout").text.indexOf("dev-desk") >= 0,
                  "identical poll moved the readout or the focus");
            keyEvents.mouseClick(target, target.width / 2, target.height / 2);
            check(sharedSurfaces.workspaceView === "machines" && sharedSurfaces.selectedMachineId === "dev-desk",
                  "click did not open the existing Machine pane");
            sharedSurfaces.closeWorkspace();
            const identity = find(rail, "rail-identity");
            identity.forceActiveFocus();
            keyEvents.keyClick(Qt.Key_Return);
            check(sharedSurfaces.workspaceOpen && sharedSurfaces.workspaceView === "sfere" && !sharedSurfaces.launcherOpen,
                  "the glyph did not open Sfere");
            sharedSurfaces.closeWorkspace();
            keyEvents.mouseClick(identity, identity.width / 2, identity.height / 2);
            check(sharedSurfaces.workspaceOpen && sharedSurfaces.workspaceView === "sfere",
                  "clicking the glyph did not open Sfere");
            keyEvents.wait(30);
            sharedState.gpuSourceState = "unavailable";
            check(!balls().some(ball => ball.gpuOwner) && !find(map, "sfere-host-gpu").visible,
                  "unknown GPU ownership retained a token");
            sharedState.applyGpuPayload(JSON.stringify({known: true, owner: "dev-desk", bound: true}));
            sharedState.gpuObservedAt = Date.now() - 600000;
            check(!balls().some(ball => ball.gpuOwner) && !find(map, "sfere-host-gpu").visible,
                  "stale GPU ownership retained a token");
            sharedState.machinesObservedAt = Date.now() - 600000;
            target.forceActiveFocus();
            check(find(map, "sfere-readout").text.indexOf("last observed") >= 0,
                  "stale Machine state reads as current");
            answerNetworks(networks.map(row => Object.assign({}, row, {state: "inactive"})));
            check(lines().length === 0, "inactive networks drew links");
            answerNetworks(networks);
            sharedState.networksObservedAt = Date.now() - 600000;
            check(lines().length === 0, "stale networks drew links");
            answerNetworks(networks);
            sharedState.applyFeatures('{"networks_view_enabled":false}');
            check(!sharedState.networksReadable && lines().length === 0, "disabled Networks drew links");
            sharedState.applyTrustPayload("unreadable");
            check(map.claimLine.indexOf("last seen") >= 0 && map.needsReboot("clean"),
                  "failed claim erased a boot restriction");
            sharedState.applyMachinePayload("unreadable");
            check(!find(map, "sfere-create").visible && find(map, "sfere-unavailable").visible,
                  "unavailable inventory offered Create");
            check(sharedMachineActions.operations.length === 0, "map activation performed a Machine operation");
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--renders", type=Path)
    args = parser.parse_args()
    source_contract()
    networks = network_rows()
    cases = json.loads(FIXTURE.read_text())["cases"]
    for case in cases:
        require(case["links"] == declared_links(case, networks),
                "fixture contains a pair the network source does not declare")
    levels = yaml.safe_load((ROOT / "group_vars/all/networks.yml").read_text())["gpu_trust_levels"]
    ladder = cli_ladder(levels)["cli"]
    runner = shutil.which("qmlscene6") or shutil.which("qmlscene")
    require(runner is not None, "Qt QML runner is required")
    if args.renders:
        args.renders.mkdir(parents=True, exist_ok=True)
    # Additional capacities and state vocabulary exercise the same real scene.
    stress = dict(cases[-1], id="twenty-four", machines=cases[-1]["machines"][:24])
    stress["links"] = [pair for pair in stress["links"] if pair[1] in {row["name"] for row in stress["machines"]}]
    transitions = dict(cases[1], id="transitions", machines=[dict(row, state="starting") for row in cases[1]["machines"]])
    # A Machine named like the clean sector's outer count.
    collision = dict(cases[-1], id="key-collision", gpu_owner="group-clean-outer",
                     machines=[dict(row, name="group-clean-outer") if row["name"] == "dev-01" else dict(row)
                               for row in cases[-1]["machines"]],
                     links=[[a, "group-clean-outer" if b == "dev-01" else b, c] for a, b, c in cases[-1]["links"]])
    # An external domain on a declared NAT network gets its line too.
    outside = dict(cases[2], id="external-link", machines=cases[2]["machines"] + [
        {"name": "outside-nat", "domain": "external", "state": "shut off", "disposable": False,
         "networks": ["clean"]}])
    outside["links"] = declared_links(outside, networks)
    require(["host", "outside-nat", "clean"] in outside["links"]
            and not any(pair[1] == "hl-lab-host" for pair in outside["links"]),
            "external link fixture lost its declared and undeclared rows")
    cases.extend([stress, transitions, collision, outside])
    root = (runtime.QML / "shell.qml").read_text()
    binding = re.search(r"networksMapVisible:\s*(.*?)\n\s*networksPageVisible:", root, re.S)
    require(binding is not None, "missing map visibility binding")
    directory = runtime.stage()
    try:
        for case in cases:
            setup = SETUP.replace("@@CASE@@", json.dumps(case)).replace("@@NETWORKS@@", json.dumps(networks))
            setup = setup.replace("@@LADDER@@", json.dumps(ladder))
            body = setup + CHECKS + (INTERACTION if case["id"] == "five-domains" else "")
            if case["id"] == "twelve-external":
                body += '''
                    find(map, "sfere-slot-external:hl-lab-host").activate();
                    check(sharedSurfaces.workspaceView === "machines" && sharedSurfaces.selectedMachineId === "",
                          "external Machine gained an operational pane");
                '''
            if case["id"] == "thirty":
                body += '''
                    const count = slots().find(slot => slot.entry.kind === "group");
                    check(count !== undefined, "large inventory lost its count sphere");
                    if (count) count.activate();
                    check(sharedSurfaces.workspaceView === "machines" && sharedSurfaces.selectedMachineId === "",
                          "count sphere did not open the existing inventory");
                '''
            if case["id"] == "key-collision":
                body += '''
                    for (const slot of slots()) {
                        slot.forceActiveFocus();
                        check(map.readoutText === map.partsFor(slot.entry).join(" · "),
                              "a count shadowed a named Machine's readout");
                    }
                '''
            if case["id"] == "twenty-four":
                body += '''
                    const scroll = nodes(map, item => item.contentX !== undefined)[0];
                    check(scroll !== undefined && scroll.contentWidth > scroll.width,
                          "small-window fixture did not exercise scrolling");
                    scroll.contentX = scroll.contentWidth - scroll.width;
                    for (const slot of slots()) {
                        slot.forceActiveFocus();
                        keyEvents.wait(10);
                        const words = find(map, "sfere-readout");
                        const place = words.mapToItem(map, 0, 0);
                        check(place.x >= 0 && place.y >= 0 && place.x + words.width <= map.width
                              && place.y + words.height <= map.height,
                              "scrolling hid the focused Machine readout");
                    }
                '''
            if case["id"] == "host-alone":
                body += '''
                    find(map, "sfere-create").activate();
                    check(sharedSurfaces.workspaceView === "machines" && find(workspaceSurface, "machine-stage").creating,
                          "Create did not open the existing Create flow");
                    sharedSurfaces.openWorkspace("sfere");
                    sharedState.applyOutsideDomainsPayload("unreadable");
                    check(!find(map, "sfere-create").visible
                          && find(map, "sfere-readout").text.indexOf("unavailable") >= 0,
                          "unreadable raw inventory looks empty");
                '''
            capture = setup + CHECKS
            for label, scenario, destination in (("checks", body, ""), ("render", capture,
                    str(args.renders.resolve() / f"{case['id']}-1920x1080.png") if args.renders else "")):
                if label == "render" and (not args.renders or case["id"] in {"twenty-four", "transitions", "key-collision", "external-link"}):
                    continue
                width, height = (800, 600) if case["id"] == "twenty-four" else (1920, 1080)
                source, messages = runtime.scenario_source(width, height, rows_for(case), scenario,
                    gpu={"known": True, "owner": case["gpu_owner"], "bound": bool(case["gpu_owner"])},
                    trust={"known": True, "claimed": True, "identity": "dev", "level": 2}, out=destination)
                source = source.replace("import QtQuick.Window", "import QtQuick.Window\nimport QtTest")
                source = source.replace("ShellState { id: sharedState }", "ShellState { id: sharedState\n"
                    "networksMapVisible: " + binding[1] + "\n}"
                    "\nTestCase { id: keyEvents; when: false }")
                runtime.run(runner, directory, case["id"] + " " + label, source, messages)
                if destination:
                    require(len(set(png_pixels(Path(destination), (1920, 1080)))) > 32, "render is blank")
    finally:
        shutil.rmtree(directory)
    print("Sfere view contract: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
