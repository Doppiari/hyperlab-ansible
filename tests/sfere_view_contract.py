#!/usr/bin/env python3
"""Execute the Sfere seal with existing shell sources and inert transports.

The view is the seal of ADR 0069: the host keystone (geometry B, ADR 0056)
at the centre, one glass sphere per network of `hyperlabctl --json net list`
on an engraved floor, one port and one spoke per network, sealed and broken
exactly for an isolated network, Machines still on their rings and a panel
with the selected network's facts and cards. The checks run the real QML
over the real net list formatter (each network's live definition rendered by
the role's own libvirt template) and the repository's palette.

Source checks: the deployed files, no colour literal or constructor, one
33 ms timer and no other clock or animation, the palette and character
tables with the same keys, the atmosphere fed only by geometry and a clock,
and no retyped geometry B number.

`--renders DIR` keeps the five 1920x1080 fixture captures.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import re
import shutil
import sys
from types import SimpleNamespace
from unittest.mock import patch

import jinja2
import yaml

import host_quickshell_runtime_contract as runtime
from host_quickshell_qml_wiring_contract import blocks, strip_noise
from machine_sphere_contract import string_literals
from product_symbol_geometry_contract import EXPECTED as GEOMETRY_B
from trust_pool_v3_generated_contract import png_pixels

ROOT = runtime.ROOT
sys.path.insert(0, str(ROOT / "tools/hyperlabctl"))
from hyperlabctl.commands.net import NetCommand  # noqa: E402

FIXTURE = ROOT / "tests/fixtures/sfere-view.json"
VIEW_FILES = ("SfereView.qml", "SealFloor.qml", "SealAmbient.qml", "HostKeystone.qml",
              "SealSpoke.qml", "SealNetwork.qml", "SealPanel.qml")
# The atmosphere's whole interface: the seal's geometry and one clock.
AMBIENT_INPUTS = {"tokens", "theme", "active", "time", "centreX", "floorY", "radius", "tilt",
                  "hostX", "hostY", "hostRadius"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("Sfere view contract: " + message)


def definitions() -> dict[str, str]:
    """Each declared network rendered by the role's own libvirt template."""
    config = yaml.safe_load((ROOT / "group_vars/all/networks.yml").read_text())
    leases = yaml.safe_load((ROOT / "group_vars/all/services.yml").read_text())["service_dhcp_leases"]
    environment = jinja2.Environment(undefined=jinja2.StrictUndefined)
    environment.filters["regex_replace"] = lambda value, pattern, replacement: re.sub(pattern, replacement, value)
    template = environment.from_string((ROOT / "roles/network_domains/templates/net.xml.j2").read_text())
    return {entry["name"]: template.render(item=entry, service_dhcp_leases=leases)
            for entry in config["network_domains"]}


def network_rows() -> list[dict]:
    """The real net list formatter, with a declared and active network fixture."""
    config = yaml.safe_load((ROOT / "group_vars/all/networks.yml").read_text())
    xml = definitions()
    ctx = SimpleNamespace(config=SimpleNamespace(var=lambda key, default: config.get(key, default)),
                          virsh=lambda verb, name: SimpleNamespace(ok=verb == "net-dumpxml" and name in xml,
                                                                    stdout=xml.get(name, "")))
    with patch("hyperlabctl.commands.net.doc.build", return_value={
        "networks": {"missing": [], "inactive": []}
    }), redirect_stdout(io.StringIO()) as out:
        require(NetCommand().run(SimpleNamespace(net_action="list", json=True), ctx) == 0,
                "net list fixture failed")
    return json.loads(out.getvalue())


def object_literal(source: str, name: str) -> dict:
    match = re.search(r"readonly property var " + name + r":\s*\(\{(.*?)\}\)", source, re.S)
    require(match is not None, f"SfereView.qml has no {name} table")
    return json.loads("{" + match[1] + "}")


def source_contract() -> None:
    import gi
    gi.require_version("Gdk", "4.0")
    from gi.repository import Gdk

    coordinator = (runtime.QML / "ShellSurfaces.qml").read_text()
    destinations = re.search(r"readonly property var destinations:\s*(\[[^]]*\])", coordinator)
    require(destinations is not None and json.loads(destinations[1])[0] == "sfere",
            "Sfere is not the first workspace destination")
    deploy = yaml.safe_load((ROOT / "group_vars/all/host-desktop.yml").read_text())
    installed = deploy["host_desktop_common_shell_stage"]["surface_files"]
    colour = Gdk.RGBA()
    timers = 0
    for name in VIEW_FILES:
        require(name in installed, f"{name} is absent from the installed shell")
        source = (runtime.QML / name).read_text()
        literals = string_literals(source)
        require(not any(colour.parse(word) or re.search(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgb|hsl|hsv)a?\(", word)
                        for word in literals), f"colour literal in {name}")
        clean = strip_noise(source)
        require(not re.search(r"\bQt\.(?:rgba?|hsla?|hsva?|color|darker|lighter|tint)\s*\(", clean),
                f"colour constructor in {name}")
        require(not re.search(r"\b(?:\w*Animation|Transition|Behavior|Process|FileView|FrameAnimation)\s*\{",
                              clean), f"{name} gained an animation or a data transport")
        timers += len(re.findall(r"\bTimer\s*\{", clean))
        for number in ("0.685", "0.41", "0.555", "0.057", "0.413", "0.46"):
            require(not re.search(r"(?<![\d.])" + re.escape(number) + r"(?!\d)", clean),
                    f"{name} retypes the geometry B number {number}")
    view = strip_noise((runtime.QML / "SfereView.qml").read_text())
    clocks = re.findall(r"\bTimer\s*\{(.*?)\n    \}", view, re.S)
    require(timers == 1 and len(clocks) == 1 and re.search(r"\binterval:\s*33\b", clocks[0]),
            "the seal must have exactly one timer, at 33 ms")
    written = (runtime.QML / "SfereView.qml").read_text()
    palette = object_literal(written, "networkPalette")
    characters = object_literal(written, "networkCharacters")
    require(set(palette) == set(characters), "the palette and character tables have different keys")
    require(all(value == "dom_" + key for key, value in palette.items()),
            "a network colour is not its dom_ palette entry")
    keystone = strip_noise((runtime.QML / "HostKeystone.qml").read_text())
    require(len(list(blocks(keystone, "IsolationGlyph", False))) == 1
            and len(list(blocks(keystone, "NetworkSphere", False))) == 1,
            "the host keystone must reuse geometry B and the host sphere")
    require(len(list(blocks(strip_noise((runtime.QML / "SealNetwork.qml").read_text()),
                            "NetworkSphere", False))) == 1, "a network must be a NetworkSphere")
    ambient = strip_noise((runtime.QML / "SealAmbient.qml").read_text())
    declared = set(re.findall(r"(?m)^    (?:required )?property \w+ (\w+)", ambient))
    inputs = set(re.findall(r"(?m)^    required property \w+ (\w+)", ambient))
    require(inputs == AMBIENT_INPUTS and not (declared - inputs) - {
        "ringTurnSeconds", "rayTurnSeconds", "ringAngle", "rayAngle", "moteCount", "tickCount",
        "rayCount", "tone", "clear"}, f"the atmosphere gained an input: {sorted(declared)}")
    instance = list(blocks(view, "SealAmbient", True))
    require(len(instance) == 1, "the view must draw one atmosphere")
    bound = set(re.findall(r"(?m)^\s{16}(\w+):", instance[0]))
    require(bound <= AMBIENT_INPUTS | {"objectName", "anchors"},
            f"the view passes the atmosphere more than geometry and a clock: {sorted(bound)}")
    require(not re.search(r"\b(?:network|machine|lit|place|port)", ambient, re.I),
            "the atmosphere reads a network or a Machine")
    root = (runtime.QML / "shell.qml").read_text()
    require("networksMapVisible:" in root, "the root does not expose map visibility to the shared network source")


SETUP = r'''
            sharedTokens.reducedMotion = true;
            const fixture = @@CASE@@;
            const networks = @@NETWORKS@@;
            const palette = @@PALETTE@@;
            const ladder = @@LADDER@@;
            const geometry = @@GEOMETRY@@;
            sharedState.applyOutsideDomainsPayload(JSON.stringify({machines_available: true,
                machines: fixture.machines.map(row => ({name: row.name, state: row.state, networks: row.networks,
                                                       managed: true}))
                    .concat(fixture.external.map(row => Object.assign({managed: false}, row)))}));
            sharedState.applyFeatures('{"networks_view_enabled":true}');
            sharedSurfaces.openWorkspace("sfere");
            const view = find(workspaceSurface, "sfere-view");
            check(view !== null && view.visible, "Sfere view did not open");
            if (!view) { Qt.exit(1); return; }
            function nodes(root, predicate) {
                let out = predicate(root) ? [root] : [];
                for (const child of root.children || []) out = out.concat(nodes(child, predicate));
                return out;
            }
            function named(prefix) { return nodes(view, item => item.objectName.indexOf(prefix) === 0); }
            function shown(item) {
                for (let node = item; node; node = node.parent) if (!node.visible || node.opacity === 0) return false;
                return true;
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
            const keystone = find(view, "sfere-host");
            const managed = fixture.machines;
            function inNetwork(name) { return managed.filter(row => (row.networks || []).indexOf(name) >= 0); }
            if (fixture.stale === "machines") {
                sharedState.machinesObservedAt = Date.now() - 600000;
                sharedState.observationNow = Date.now();
                keyEvents.wait(30);
            }
'''

CHECKS = r'''
            check(workspaceSurface.destinations[0].id === "sfere", "Sfere is not the first visible tab");
            const machinesCurrent = fixture.stale !== "machines";
            // One port per listed network, in the source's order, and nothing else.
            const ports = named("sfere-port-");
            check(ports.length === networks.length
                  && networks.every((row, i) => ports[i] && ports[i].network === row.name),
                  "port set differs from the network source");
            const spokes = named("sfere-spoke-");
            check(spokes.length === networks.length
                  && networks.every((row, i) => spokes[i] && spokes[i].network === row.name),
                  "spoke set differs from the network source");
            for (let i = 0; i < networks.length; i++) {
                const row = networks[i], isolated = row.forward === "isolated";
                check(ports[i].sealed === isolated && spokes[i].broken === isolated,
                      "sealed port or broken spoke differs from forward isolated");
                // The spoke leaves from its own port.
                const port = ports[i].mapToItem(spokes[i], ports[i].width / 2, ports[i].height / 2);
                check(Math.hypot(port.x - spokes[i].fromX, port.y - spokes[i].fromY) < 1.5,
                      "a spoke does not leave from its network's port");
                const sphere = find(view, "sfere-sphere-" + row.name);
                const known = Object.prototype.hasOwnProperty.call(palette, "dom_" + row.name)
                    && view.knownNetwork(row.name);
                check(sphere !== null && Qt.colorEqual(sphere.colour,
                          known ? palette["dom_" + row.name] : sharedTheme.textSecondary),
                      "a network sphere is not in its palette colour");
                check(sphere.character === (known ? view.networkCharacters[row.name] : 1),
                      "a network sphere has the wrong character");
                const running = inNetwork(row.name).filter(m => m.state === "running").length;
                check((sphere.lit > 0) === (machinesCurrent && running > 0),
                      "a core is lit where no managed Machine runs, or dark where one does");
                const words = find(view, "sfere-state-" + row.name).text;
                const count = inNetwork(row.name).length;
                if (count === 0)
                    check(words.indexOf(isolated ? "isolated · sealed" : "empty") === 0,
                          "an empty network does not say so");
                else
                    check(words.indexOf(count + (count === 1 ? " machine · " : " machines · ")
                              + (machinesCurrent && running > 0 ? "lit: " : "") + running + " running") === 0
                          && (words.indexOf("isolated · sealed") >= 0) === isolated,
                          "a network's words differ from its Machines");
                // Electrons: one per managed Machine up to eight, then +N.
                const rings = nodes(sphere.parent, item => item.objectName.indexOf("sfere-ring-" + row.name + "-") === 0);
                check(rings.length === Math.min(count, 8), "a network draws the wrong number of rings");
                const more = find(sphere.parent, "sfere-more-" + row.name);
                check(count > 8 ? (more.visible && more.text === "+" + (count - 7)) : true,
                      "a crowded network lost its +N");
                for (const machine of inNetwork(row.name).slice(0, count > 8 ? 0 : 8)) {
                    const dots = nodes(sphere.parent, item => item.objectName === "sfere-electron-" + machine.name
                                                            && item.visible);
                    check(dots.length === 1, "a Machine is not exactly one electron");
                    if (dots.length === 1)
                        check((dots[0].border.width === 0) === (machine.state === "running"),
                              "an electron is not bright exactly while its Machine runs");
                }
            }
            for (const row of fixture.external)
                check(named("sfere-electron-" + row.name).length === 0, "an external Machine sits on a ring");
            const outside = find(view, "sfere-outside");
            for (const row of fixture.external)
                check(visibleText(outside, row.name + " · not managed · outside the seal"),
                      "an external Machine is not listed outside the seal");
            for (const row of managed.filter(row => !row.networks))
                check(visibleText(outside, row.name + " · managed · on no listed network"),
                      "a Machine with unread attachments vanished");
            // Geometry B, from IsolationGlyph and the ADR 0056 table.
            const outer = keystone.outerRadius;
            check(Math.abs(keystone.innerRadius / outer - geometry.arcInnerRatio) < 0.002
                  && Math.abs(keystone.cutOffset / outer - geometry.cutRatio) < 0.002
                  && Math.abs(keystone.ringRadius / outer - geometry.ringRadiusRatio) < 0.002
                  && Math.abs(keystone.ringStroke - Math.max(1, outer * geometry.ringStrokeRatio)) < 0.01
                  && Math.abs(keystone.coreRadius / outer - geometry.coreRadiusRatio) < 0.002,
                  "keystone geometry differs from ADR 0056");
            const core = find(keystone, "sfere-host-core");
            check(core.character === 0 && Math.abs(core.width * core.radiusShare / 2 - keystone.coreRadius) < 0.01
                  && Qt.colorEqual(core.colour, sharedTheme.provenanceColor("host")),
                  "the host core is not the silver sphere in the glyph's core");
            // The engraving stays on the blades, never in the cut between them.
            const letters = nodes(keystone, item => item.modelData !== undefined && item.modelData !== null
                                                  && item.modelData.letter !== undefined);
            check(letters.length === keystone.engravings.join("").length
                  && letters.every(item => Math.abs(item.x + item.width / 2 - keystone.width / 2)
                                           > keystone.cutOffset + item.width / 2),
                  "an engraved letter sits in the cut between the blades");
            for (const port of ports) {
                const centre = port.mapToItem(keystone, port.width / 2, port.height / 2);
                check(Math.abs(Math.hypot(centre.x - keystone.width / 2, centre.y - keystone.height / 2)
                               - keystone.ringRadius) < 0.75, "a port is not on the host ring");
            }
            // Freshness, in words and in the host's light.
            const words = find(view, "sfere-freshness").text;
            if (fixture.stale === "machines")
                check(words.indexOf("data from ") === 0 && words.indexOf("Machine inventory not answering") > 0
                      && !view.fresh && view.hostLight < 0.2 && view.beat === 0,
                      "a stale source keeps the heartbeat or does not say so");
            else
                check(words === "data current" && view.fresh, "fresh sources do not read as current");
            // The panel: the selected network's facts, from the source.
            const selected = networks[view.selectedIndex];
            check(find(view, "sfere-panel-title").text === view.title(selected.name)
                  && find(view, "sfere-panel-subnet").text === selected.subnet,
                  "the panel does not show the selected network");
            const gateway = selected.gateway === false ? "none" : (selected.gateway === null ? "unknown" : selected.gateway);
            const dhcp = selected.dhcp === false ? "off" : (selected.dhcp === null ? "unknown"
                : selected.dhcp.start + " – " + selected.dhcp.end);
            const rung = ladder.find(row => row.name === selected.name);
            check(find(view, "sfere-fact-Gateway").text === gateway && find(view, "sfere-fact-DHCP").text === dhcp
                  && find(view, "sfere-fact-GPU level").text === (selected.trust === null ? "none" : String(selected.trust))
                  && (rung === undefined) === (selected.trust === null),
                  "the panel's gateway, DHCP or GPU level differ from net list");
            const cards = nodes(find(view, "sfere-panel-cards"), item => item.machine !== undefined && item.visible);
            check(cards.length === inNetwork(selected.name).length
                  && cards.every(card => !find(card, "machine-sphere-" + card.machine.name)
                                         || !find(card, "machine-sphere-" + card.machine.name).visible),
                  "the panel's cards differ from the network's Machines or show spheres");
            // The screen reader list.
            const spoken = nodes(find(view, "sfere-list"), item => item.Accessible.role === Accessible.ListItem)
                .map(item => item.Accessible.name);
            check(spoken[0] === "Host, every path passes here, " + words
                  && networks.every(row => spoken.some(line => line.indexOf(view.title(row.name) + ", ") === 0))
                  && managed.every(row => !row.networks || spoken.some(line => line.indexOf(row.name + ", ") === 0)),
                  "the screen reader list lost a network, a Machine or the freshness line");
            // Every sphere and its words stay on the stage.
            const stage = find(view, "sfere-stage");
            for (const row of networks) {
                const sphere = find(view, "sfere-sphere-" + row.name), label = find(view, "sfere-words-" + row.name);
                for (const item of [sphere, label]) {
                    const corner = item.mapToItem(stage, 0, 0), far = item.mapToItem(stage, item.width, item.height);
                    check(view.zoomed || (corner.x >= 0 && corner.y >= 0 && far.x <= stage.width && far.y <= stage.height),
                          "a network or its words leave the stage");
                }
            }
            check(sharedMachineActions.operations.length === 0, "the seal performed a Machine operation");
'''

INTERACTION = r'''
            const order = networks.map(row => row.name);
            const first = find(view, "sfere-network-" + order[0]);
            check(first.activeFocusOnTab && nodes(view, item => item.objectName.indexOf("sfere-network-") === 0
                                                       && item.activeFocusOnTab).length === 1,
                  "Tab does not enter the stage at one network");
            first.forceActiveFocus();
            for (let index = 0; index < order.length; index++) {
                check(find(view, "sfere-network-" + order[index]).activeFocus, "arrows did not follow seal order");
                keyEvents.keyClick(Qt.Key_Right);
            }
            check(first.activeFocus, "arrows did not wrap in seal order");
            const dev = order.indexOf("dev");
            for (let index = 0; index < dev; index++) keyEvents.keyClick(Qt.Key_Right);
            keyEvents.keyClick(Qt.Key_Return);
            check(view.selected.name === "dev" && !view.zoomed && find(view, "sfere-panel-title").text === "Dev",
                  "Enter did not select the network");
            keyEvents.keyClick(Qt.Key_Return);
            check(view.zoomed && view.entered === dev && view.camS === 2.1 && find(view, "sfere-title").text === "Dev",
                  "Enter again did not enter the network at once with reduced motion");
            keyEvents.keyClick(Qt.Key_Right);
            const devMachines = inNetwork("dev").map(row => row.name);
            check(devMachines.indexOf(view.machineCursor) >= 0, "arrows inside a network did not reach its Machines");
            const cursor = view.machineCursor;
            keyEvents.keyClick(Qt.Key_Return);
            check(find(view, "sfere-panel-cards") && nodes(find(view, "sfere-panel-cards"),
                      item => item.machine !== undefined && item.selected).map(card => card.machine.name).join() === cursor,
                  "Enter on a Machine did not select its card");
            keyEvents.keyClick(Qt.Key_Escape);
            check(!view.zoomed && view.camS === 1 && sharedSurfaces.workspaceOpen,
                  "Esc did not return to the whole seal");
            keyEvents.keyClick(Qt.Key_Plus);
            check(view.zoomed && view.entered === dev, "+ did not enter the network");
            find(view, "sfere-leave").activate();
            check(!view.zoomed, "the whole-seal button did not return");
            find(view, "sfere-enter").activate();
            check(view.zoomed && view.entered === dev, "the Enter button did not enter the selected network");
            find(view, "sfere-leave").activate();
            const lab = find(view, "sfere-network-lab");
            keyEvents.mouseClick(lab, lab.width / 2, lab.height / 2);
            check(view.selected.name === "lab" && !view.zoomed, "a click did not select the network");
            keyEvents.mouseClick(lab, lab.width / 2, lab.height / 2);
            check(view.zoomed && view.networks[view.entered].name === "lab", "a second click did not enter");
            find(view, "sfere-leave").activate();
            view.select(dev);
            const card = nodes(find(view, "sfere-panel-cards"), item => item.machine !== undefined
                               && item.machine.name === "dev-desk")[0];
            check(card !== undefined, "the dev card is missing");
            if (card) card.activated();
            check(sharedSurfaces.workspaceView === "machines" && sharedSurfaces.selectedMachineId === "dev-desk",
                  "a card did not open the existing Machine pane");
            sharedSurfaces.closeWorkspace();
            const identity = find(rail, "rail-identity");
            identity.forceActiveFocus();
            keyEvents.keyClick(Qt.Key_Return);
            check(sharedSurfaces.workspaceOpen && sharedSurfaces.workspaceView === "sfere" && !sharedSurfaces.launcherOpen,
                  "the glyph did not open Sfere");
            keyEvents.wait(30);
            // Sources that fail never look like an empty seal.
            sharedState.applyFeatures('{"networks_view_enabled":false}');
            keyEvents.wait(30);
            check(named("sfere-port-").length === 0 && find(view, "sfere-absence").visible
                  && find(view, "sfere-freshness").text.indexOf("Network inventory is off on this host") >= 0,
                  "a disabled network read drew networks or kept the data current");
            check(nodes(find(view, "sfere-panel-cards"), item => item.machine !== undefined && item.visible).length
                  === sharedState.machines.length,
                  "with no network shown, a managed Machine is no longer one card away");
            sharedState.applyFeatures('{"networks_view_enabled":true}');
            answerNetworks(networks);
            sharedState.applyMachinePayload("unreadable");
            keyEvents.wait(30);
            check(find(view, "sfere-unavailable").visible && !find(view, "sfere-create").visible
                  && view.networks.every(network => !network.lit)
                  && find(view, "sfere-freshness").text.indexOf("Machine inventory not answering") >= 0,
                  "an unreadable Machine inventory lit a core, offered Create or read as current");
            check(sharedMachineActions.operations.length === 0, "the seal performed a Machine operation");
'''

MOTION = r'''
            // What moves, and only then.
            sharedTokens.reducedMotion = false;
            sharedState.applyAmbientMotion(null);
            keyEvents.wait(250);
            const ambient = find(view, "sfere-ambient");
            check(view.ambientActive && view.coresMoving && ambient.active,
                  "ambient motion or a lit core does not move on a shown seal");
            let times = [view.ambientTime, view.coreTime];
            keyEvents.wait(300);
            check(view.ambientTime > times[0] && view.coreTime > times[1], "the clock did not advance");
            check(named("sfere-ambient-motes").length === 1 && nodes(ambient, item => item.mote !== undefined).length > 0,
                  "the dust is not drawn while ambient motion is on");
            // The atmosphere is the same for every network: lighting every
            // core changes nothing in it.
            ambient.time = 42;
            const before = JSON.stringify(Array.from({length: ambient.moteCount}, (_, i) => ambient.moteAt(i, 42)))
                + ambient.ringAngle + ambient.rayAngle;
            sharedState.applyMachinePayload(JSON.stringify({machines_available: true, machines:
                sharedState.machines.map(row => Object.assign({}, row, {state: "running"}))}));
            keyEvents.wait(30);
            check(view.networks.filter(n => n.lit).length >= 2, "lighting every core failed");
            check(JSON.stringify(Array.from({length: ambient.moteCount}, (_, i) => ambient.moteAt(i, 42)))
                  + ambient.ringAngle + ambient.rayAngle === before,
                  "the atmosphere changed with the networks' state");
            const speeds = Array.from({length: ambient.moteCount}, (_, i) => {
                const a = ambient.moteAt(i, 10), b = ambient.moteAt(i, 10.5);
                return Math.hypot(b.x - a.x, b.y - a.y);
            });
            for (const place of view.places) {
                const near = speeds.filter((_, i) => Math.hypot(ambient.moteAt(i, 10).x - place.x,
                                                                 ambient.moteAt(i, 10).y - place.y) < place.radius * 3);
                check(near.every(speed => speed <= Math.max.apply(null, speeds)),
                      "the atmosphere moves faster near a network");
            }
            ambient.time = Qt.binding(() => view.ambientTime);
            // The setting off: only lit cores keep moving.
            sharedState.applyAmbientMotion("0");
            keyEvents.wait(60);
            times = [view.ambientTime, view.coreTime];
            keyEvents.wait(300);
            check(!view.ambientActive && view.ambientTime === times[0] && view.coreTime > times[1]
                  && nodes(ambient, item => item.mote !== undefined).length === 0,
                  "Ambient motion off did not leave only lit cores moving");
            // Reduced motion: nothing moves, the clock stops.
            sharedState.applyAmbientMotion(null);
            sharedTokens.reducedMotion = true;
            keyEvents.wait(60);
            times = [view.ambientTime, view.coreTime];
            keyEvents.wait(300);
            check(!view.clockNeeded && view.ambientTime === times[0] && view.coreTime === times[1] && view.beat === 0,
                  "reduced motion left something moving");
            sharedTokens.reducedMotion = false;
            // The heartbeat: one beat per successful refresh.
            sharedState.applyMachinePayload(JSON.stringify({machines_available: true, machines: sharedState.machines}));
            keyEvents.wait(1500);
            check(view.beat === 0 && !view.beatPending, "the heart kept beating after its beat");
            sharedState.applyGpuPayload(JSON.stringify({known: true, owner: "", bound: false}));
            keyEvents.wait(400);
            check(view.beat > 0 && view.hostLight > 0.55, "a successful refresh did not beat");
            keyEvents.wait(1300);
            check(view.beat === 0, "one refresh beat more than once");
            // A stale source: the core stops and dims, whatever else refreshes.
            sharedState.machinesObservedAt = Date.now() - 600000;
            sharedState.observationNow = Date.now();
            sharedState.applyGpuPayload(JSON.stringify({known: true, owner: "", bound: false}));
            keyEvents.wait(400);
            check(!view.fresh && view.beat === 0 && view.hostLight < 0.2
                  && find(view, "sfere-freshness").text.indexOf("Machine inventory not answering") > 0,
                  "the heart beats with a stale source, or the words do not say so");
            // Half resolution while the GPU is lent.
            check(find(view, "sfere-sphere-dev").textureScale === 1, "the GPU at home drew at half resolution");
            sharedState.applyGpuPayload(JSON.stringify({known: true, owner: "dev-desk", bound: true}));
            check(find(view, "sfere-sphere-dev").textureScale === 0.5 && find(view, "sfere-host-core").textureScale === 0.5,
                  "a lent GPU kept full-resolution sphere effects");
            // A hidden view stops the clock.
            sharedSurfaces.switchWorkspace("machines");
            keyEvents.wait(60);
            check(!view.shown && !view.clockNeeded, "a hidden seal kept its clock running");
            sharedSurfaces.switchWorkspace("sfere");
            keyEvents.wait(60);
            check(view.shown && view.clockNeeded, "the shown seal did not restart its clock");
            // A hidden seal dropped its network rows; shown again, it reads them anew.
            check(view.networks.length === 0, "a hidden seal kept old network rows");
            answerNetworks(networks);
            sharedTokens.reducedMotion = true;
'''


def rows_for(case: dict) -> list[dict]:
    return [dict(runtime.MACHINE_TEMPLATE, name=row["name"], provenance=row["domain"],
                 state=row["state"], networks=row["networks"], network=(row["networks"] or [None])[0],
                 lifecycle="disposable" if row["disposable"] else "permanent",
                 gpu_relation="held" if row["name"] == case["gpu_owner"] else "none",
                 gpu="", vfio=False)
            for row in case["machines"]]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--renders", type=Path)
    args = parser.parse_args()
    source_contract()
    networks = network_rows()
    lab = next(row for row in networks if row["name"] == "lab")
    require(lab["forward"] == "isolated" and lab["gateway"] == "10.10.4.1" and lab["dhcp"],
            "the fixture lost lab's gateway or DHCP: it has both and no route out")
    palette = json.loads(runtime.PALETTE.read_text())
    levels = yaml.safe_load((ROOT / "group_vars/all/networks.yml").read_text())["gpu_trust_levels"]
    ladder = [{"name": name, "level": level} for name, level in levels.items()]
    cases = json.loads(FIXTURE.read_text())["cases"]
    # A network the palette does not know: neutral, calm, still one port.
    unknown = dict(cases[1], id="unknown-network")
    unknown_rows = networks + [{"name": "staging", "state": "active", "subnet": "10.10.8.0/24",
                                "forward": "nat", "trust": None, "gateway": "10.10.8.1", "dhcp": False}]
    runner = shutil.which("qmlscene6") or shutil.which("qmlscene")
    require(runner is not None, "Qt QML runner is required")
    if args.renders:
        args.renders.mkdir(parents=True, exist_ok=True)
    root = (runtime.QML / "shell.qml").read_text()
    binding = re.search(r"networksMapVisible:\s*(.*?)\n\s*networksPageVisible:", root, re.S)
    require(binding is not None, "missing map visibility binding")
    directory = runtime.stage()
    try:
        for case, rows in [(case, networks) for case in cases] + [(unknown, unknown_rows)]:
            setup = (SETUP.replace("@@CASE@@", json.dumps(case)).replace("@@NETWORKS@@", json.dumps(rows))
                     .replace("@@PALETTE@@", json.dumps(palette)).replace("@@LADDER@@", json.dumps(ladder))
                     .replace("@@GEOMETRY@@", json.dumps(GEOMETRY_B)))
            enter = ""
            if case.get("enter"):
                enter = f'''
            view.enter(view.networks.findIndex(network => network.name === "{case["enter"]}"));
            keyEvents.wait(30);
            check(view.zoomed && view.camS === 2.1, "the isolated fixture did not enter its network");
'''
            body = setup + enter + CHECKS
            if case["id"] == "five-networks":
                body += MOTION + INTERACTION
            if case["id"] == "no-machines":
                body += '''
            check(find(view, "sfere-create").visible, "no Machines must offer one Create action");
            find(view, "sfere-create").activate();
            check(sharedSurfaces.workspaceView === "machines" && find(workspaceSurface, "machine-stage").creating,
                  "Create did not open the existing Create flow");
'''
            capture = setup + enter + CHECKS
            for label, scenario, destination in (("checks", body, ""), ("render", capture,
                    str(args.renders.resolve() / f"{case['id']}-1920x1080.png") if args.renders else "")):
                if label == "render" and (not args.renders or case["id"] == "unknown-network"):
                    continue
                source, messages = runtime.scenario_source(1920, 1080, rows_for(case), scenario,
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
