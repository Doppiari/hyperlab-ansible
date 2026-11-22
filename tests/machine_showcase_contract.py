#!/usr/bin/env python3
"""Execute the native Machines showcase and render its GTK comparison.

Only host transports are substituted by the shared offscreen Qt harness.
The network definitions are rendered from the role and read by the CLI formatter;
no host inventory, service, compositor or Machine action is accessed.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys

import host_quickshell_runtime_contract as runtime
import sfere_view_contract as seal
from host_quickshell_qml_wiring_contract import blocks, components, resolve, strip_noise
from machine_sphere_contract import string_literals
from recovery_gpu_ladder_contract import descendants, gtk_display, load_manager, run_gtk_worker
from trust_pool_v3_generated_contract import png_pixels

ROWS = [dict(runtime.MACHINE_TEMPLATE, name=name, provenance=domain, network=domain, trust_profile=domain,
             networks=[domain], state=state, lifecycle=lifecycle, gpu_relation=gpu,
             vfio=gpu in {"held", "configured"})
        for name, domain, state, lifecycle, gpu in (
            ("clean-desk", "clean", "shut off", "permanent", "none"),
            ("dev-desk", "dev", "running", "permanent", "held"),
            ("dev-build", "dev", "shut off", "permanent", "configured"),
            ("service-desk", "services", "paused", "permanent", "none"),
            ("lab-test", "lab", "shut off", "disposable", "none"),
            ("lab-desk", "lab", "shut off", "permanent", "none"),
        )]
EXTERNAL = dict(runtime.MACHINE_TEMPLATE, name="outside-desk", provenance="dev", state="running",
                managed=False, lifecycle="external", gpu_relation="none", vfio=False)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("Machine showcase contract: " + message)


def source_contract() -> None:
    import gi
    gi.require_version("Gdk", "4.0")
    from gi.repository import Gdk
    colour = Gdk.RGBA()
    catalogue = components()
    require("state" in resolve("MachineSphere", catalogue, "declared"),
            "QML wiring lost the inherited Item.state property")
    require(catalogue["Icons"]["base"] == "QtObject", "the negative wiring fixture must be a QtObject")
    require("state" not in resolve("Icons", catalogue, "declared")
            and "state" not in resolve("Theme", catalogue, "declared"),
            "QML wiring gave a non-Item the Item.state property")
    paths = [runtime.QML / name for name in (
        "MachineStage.qml", "MachineTile.qml", "MachineListRow.qml", "MachineContextPane.qml", "NetworkBand.qml")]
    for path in paths:
        require(path.is_file(), f"{path.name} is missing")
        source = path.read_text(encoding="utf-8")
        if path.name != "NetworkBand.qml":
            for kind in ("MachineSphere", "NetworkSphere", "SphereStill"):
                require(not list(blocks(strip_noise(source), kind, False)),
                        f"{path.name} draws a {kind} on a Machine")
        literals = string_literals(source)
        require(not any(re.search(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgb|hsl|hsv)a?\(", word)
                        for word in literals), f"colour literal in {path.name}")
        require(not any(colour.parse(word) for word in literals), f"named colour literal in {path.name}")
        # QML colour-valued properties must bind to Theme, never a named colour.
        require(not re.search(r'\b(?:color|[A-Za-z]+Color)\s*:\s*["\']', source),
                f"named colour literal in {path.name}")
        require(not re.search(r"\bQt\.(?:rgba?|hsla?|hsva?|color)\s*\(", source),
                f"colour constructor in {path.name}")


SETUP = r'''
            sharedTokens.reducedMotion = true;
            const networks = @@NETWORKS@@;
            sharedState.applyFeatures('{"networks_view_enabled":true}');
            sharedState.applyOutsideDomainsPayload(JSON.stringify({
                machines_available: true, machines: sharedState.machines.concat([@@EXTERNAL@@]) }));
            sharedSurfaces.openWorkspace("machines");
            check(sharedState.networkFixtureLaunches.length === 1, "Machines must issue one network read");
            check(sharedState.networksInFlight, "Machines did not request the opt-in network inventory");
            sharedState.networkFixtureComplete(JSON.stringify(networks), 0);
            const stage = find(workspaceSurface, "machine-stage");
            function nodes(root, predicate) {
                let out = predicate(root) ? [root] : [];
                for (const child of root.children || []) out = out.concat(nodes(child, predicate));
                return out;
            }
            function sphere(root) {
                return nodes(root, item => item.domainWord !== undefined && item.drawnState !== undefined)[0];
            }
            function tile(name) { return find(stage, "machine-tile-" + name); }
            function viewportFor(item) {
                let view = item.parent;
                while (view && view.contentY === undefined) view = view.parent;
                return view;
            }
            function update(rows) {
                sharedSurfaces.clearMachineSelection();
                sharedState.applyMachinePayload(JSON.stringify({machines_available: true, machines: rows}));
                stage.query = "";
                stage.layoutMode = "grid";
                keyEvents.wait(30);
            }
            keyEvents.wait(40);
            keyEvents.mouseMove(window.contentItem, 0, 0);
            keyEvents.wait(30);
'''.replace("@@EXTERNAL@@", json.dumps(EXTERNAL))

CHECKS = r'''
            check(stage.groups.map(group => group.identity).join(",") === "clean,dev,services,lab",
                  "groups must follow palette order and omit empty domains");
            check(nodes(stage, item => item.objectName.indexOf("machine-group-") === 0
                        && item.visible).map(item => item.objectName).join(",")
                  === "machine-group-clean,machine-group-dev,machine-group-services,machine-group-lab",
                  "drawn groups differ from the nonempty inventory groups");
            const band = find(stage, "network-band");
            function entry(name) { return find(band, "band-entry-" + name); }
            const entries = nodes(band, item => item.objectName.startsWith("band-entry-"));
            check(entries.length === networks.length && networks.every(net => entry(net.name))
                  && entries.map(card => card.modelData.name).join(",") === "clean,dev,services,dirty,lab",
                  "band order or network membership changed");
            if (window.firstFailure >= 0) {
                Qt.exit(40 + window.firstFailure);
                return;
            }
            for (const net of networks) {
                const card = entry(net.name);
                const attached = sharedState.machines.filter(row => row.networks.includes(net.name));
                const running = attached.filter(row => row.state === "running").length;
                const ball = find(card, "network-core");
                const outline = find(card, "network-outline");
                check(ball.visible === (attached.length > 0) && ball.stillForm
                      && ball.lit === (running > 0 ? 1 : 0) && ball.time === 0
                      && Qt.colorEqual(ball.colour, sharedTheme.palette["dom_" + net.name])
                      && Qt.colorEqual(outline.border.color, sharedTheme.palette["dom_" + net.name])
                      && outline.visible === !attached.length && outline.color.a === 0 && outline.border.width > 0,
                      "drawn network sphere disagrees with managed inventory");
                const count = attached.length === 0 ? "no machines" : attached.length
                    + (attached.length === 1 ? " machine · " : " machines · ") + running + " running";
                check(visibleText(card, count), "network count differs from Machine inventory");
                for (const [label, value] of [["Subnet", net.subnet], ["Gateway", net.gateway],
                        ["DHCP", net.dhcp.start + " – " + net.dhcp.end],
                        ["GPU level", net.trust === null ? "none" : String(net.trust)],
                        ["Mode", net.forward === "isolated" ? "Isolated" : "NAT"],
                        ["Outbound", net.forward === "isolated" ? "No route out" : "Internet via NAT"]]) {
                    check(visibleText(card, value) && card.Accessible.name.includes(label + " " + value),
                          "band " + label + " differs from source for " + net.name);
                }
            }
            check(band.Accessible.role === Accessible.List
                  && visibleText(band, "Host name unknown · reaches every network · from a network only DHCP and DNS on its own gateway, nothing else unless a rule says so"),
                  "missing host reachability or keyboard list");
            entry("clean").forceActiveFocus();
            keyEvents.keyClick(Qt.Key_Right);
            check(entry("dev").activeFocus, "arrow did not focus next network");
            keyEvents.keyClick(Qt.Key_Return);
            check(stage.filtered.length === 2 && stage.filteredOutside.length === 0
                  && stage.groups.length === 1 && stage.groups[0].identity === "dev",
                  "band selection did not filter Machine groups");
            keyEvents.keyClick(Qt.Key_Return);
            check(stage.filtered.length === 6, "second activation did not clear network filter");
            keyEvents.mouseClick(entry("lab"));
            check(stage.filtered.length === 2 && stage.groups[0].identity === "lab",
                  "pointer did not filter to isolated network");
            keyEvents.keyClick(Qt.Key_Escape);
            check(stage.filtered.length === 6 && sharedSurfaces.workspaceOpen,
                  "Escape did not clear the network filter");
            for (const row of sharedState.machines) {
                const card = tile(row.name);
                check(card && card.visible, "Machine tile missing");
                if (!card) continue;
                check(!sphere(card), "tile draws a Machine sphere");
                check(card.Accessible.name.includes(row.name) && card.activeFocusOnTab
                      && card.Accessible.name.includes("Memory 8 GiB") && card.Accessible.name.includes("vCPU 4")
                      && card.Accessible.name.includes("Network " + row.networks[0]),
                      "tile lost labelled allocation or keyboard focus");
                const footer = row.gpu_relation === "held" ? "Holds the GPU"
                    : row.lifecycle === "disposable" ? "Disposable · discarded at shutdown"
                    : row.gpu_relation === "configured" ? "Passthrough configured" : "No passthrough";
                check([stage.icons.machineStateWord(row.state), row.name, row.os,
                       "8 GiB", "4", row.networks[0], footer].every(word => visibleText(card, word)),
                      "tile lost state, name, OS, allocation or footer");
                check(card.width >= 300 && card.width <= 420 && card.height >= 150,
                      "tile dimensions escape the reviewed range");
                check(!Qt.colorEqual(card.color, sharedTheme.raised), "tile has no domain wash");
                check(Qt.colorEqual(card.color,
                      sharedTheme.mix(sharedTheme.provenanceColor(row.provenance), sharedTheme.raised, 0.07)),
                      "tile domain wash must remain the subtle seven-percent mix");
            }
            for (const group of stage.groups) {
                const section = find(stage, "machine-group-" + group.identity);
                const net = networks.find(row => row.name === group.identity);
                check(visibleText(section, "Subnet " + net.subnet + " · Mode "
                                  + (net.forward === "nat" ? "NAT" : "Isolated"))
                      && visibleText(section, group.machines.length + (group.machines.length === 1 ? " Machine" : " Machines")),
                      "group lost its subnet, mode or count");
            }
            const cards = sharedState.machines.map(row => tile(row.name));
            for (let left = 0; left < cards.length; left++) {
                const a = cards[left].mapToItem(stage, 0, 0);
                check(a.x >= 0 && a.x + cards[left].width <= stage.width,
                      "tile escapes the workspace horizontally");
                for (let right = left + 1; right < cards.length; right++) {
                    const b = cards[right].mapToItem(stage, 0, 0);
                    check(a.x + cards[left].width <= b.x || b.x + cards[right].width <= a.x
                          || a.y + cards[left].height <= b.y || b.y + cards[right].height <= a.y,
                          "Machine tiles overlap");
                }
            }
            check(visibleText(tile("dev-build"), "Passthrough configured")
                  && visibleText(tile("dev-desk"), "Holds the GPU"),
                  "tile lost passthrough configuration or ownership words");
            const hoverCard = tile("clean-desk");
            const restingFill = Qt.rgba(hoverCard.color.r, hoverCard.color.g, hoverCard.color.b, hoverCard.color.a);
            const feedbackFill = sharedTheme.mix(sharedTheme.textPrimary, restingFill, 0.05);
            keyEvents.mouseMove(hoverCard, hoverCard.width / 2, hoverCard.height / 2);
            keyEvents.wait(30);
            check(hoverCard.hovered === true, "real pointer motion must hover the Machine tile");
            check(Qt.colorEqual(hoverCard.color, feedbackFill)
                  && !Qt.colorEqual(hoverCard.color, restingFill),
                  "hover must lighten the Machine tile wash");
            keyEvents.mousePress(hoverCard, hoverCard.width / 2, hoverCard.height / 2);
            keyEvents.wait(30);
            check(hoverCard.pressed === true && Qt.colorEqual(hoverCard.color, feedbackFill),
                  "press must retain Machine tile wash feedback");
            check(sharedSurfaces.selectedMachineId === "", "press alone must not select a Machine");
            keyEvents.mouseRelease(hoverCard, hoverCard.width / 2, hoverCard.height / 2);
            keyEvents.wait(30);
            check(sharedSurfaces.selectedMachineId === "clean-desk"
                  && Qt.colorEqual(hoverCard.color, sharedTheme.mix(sharedTheme.textPrimary, restingFill, 0.08)),
                  "selected tile feedback must take precedence over hover");
            keyEvents.mouseMove(window.contentItem, 1, 1);
            sharedSurfaces.clearMachineSelection();
            keyEvents.wait(30);
            check(!hoverCard.hovered, "pointer exit must clear tile hover");
            check(!hoverCard.pressed, "pointer release must clear tile press");
            check(Qt.colorEqual(hoverCard.color, restingFill),
                  "leaving a tile must restore its wash");
            hoverCard.enabled = false;
            keyEvents.mouseMove(hoverCard, hoverCard.width / 2, hoverCard.height / 2);
            keyEvents.wait(30);
            check(Qt.colorEqual(hoverCard.color, restingFill), "disabled tile gained hover feedback");
            keyEvents.mouseMove(window.contentItem, 0, 0);
            hoverCard.enabled = true;
            const external = find(stage, "external-machine-outside-desk");
            check(external && external.visible && !sphere(external), "external tile draws a sphere or is missing");
            if (external) {
                check(external.color.a === 0 && Qt.colorEqual(external.border.color, sharedTheme.textPrimary),
                      "external tile borrowed a domain colour or fill");
                check(visibleText(external, "Memory 8192 MiB · vCPU 4")
                      && visibleText(external, "Network clean") && visibleText(external, "Read only · external"),
                      "external allocation, attachment or read-only footer disagrees with projection");
                check(external.Accessible.name.indexOf("outside-desk") >= 0
                      && !external.activeFocusOnTab && external.activated === undefined,
                      "external tile lost accessibility or gained selection");
                check(external.width === tile("clean-desk").width,
                      "external and managed grid tile widths must match");
                const last = tile("lab-desk").mapToItem(stage, 0, 0);
                check(external.mapToItem(stage, 0, 0).y > last.y,
                      "external group must follow every managed group");
            }
            // A GridView cell includes its trailing gap; exercise a full
            // row and the next one so a lost final column cannot hide.
            const inventoryFrame = find(stage, "machine-inventory-summary");
            const columns = Math.floor((inventoryFrame.bodyWidth + stage.tokens.cardGap)
                                      / (tile("clean-desk").width + stage.tokens.cardGap));
            const outsideRows = Array.from({length: columns + 1}, (_, index) =>
                Object.assign({}, @@EXTERNAL@@, {name: "outside-" + index}));
            sharedState.applyOutsideDomainsPayload(JSON.stringify({machines_available: true,
                machines: sharedState.machines.concat(outsideRows)}));
            keyEvents.wait(30);
            const grid = find(stage, "external-machine-list");
            const firstOutside = find(stage, "external-machine-outside-0");
            const lastInRow = find(stage, "external-machine-outside-" + (columns - 1));
            const nextRow = find(stage, "external-machine-outside-" + columns);
            check(firstOutside && lastInRow && nextRow, "external grid row fixture was not drawn");
            if (firstOutside && lastInRow && nextRow) {
                const firstPoint = firstOutside.mapToItem(grid, 0, 0);
                const lastPoint = lastInRow.mapToItem(grid, 0, 0);
                const nextPoint = nextRow.mapToItem(grid, 0, 0);
                check(lastPoint.y === firstPoint.y
                      && lastPoint.x + lastInRow.width <= inventoryFrame.bodyWidth
                      && nextPoint.x === firstPoint.x && nextPoint.y === firstPoint.y + grid.cellHeight,
                      "external grid must fit the same full columns as managed tiles");
            }
            sharedState.applyOutsideDomainsPayload(JSON.stringify({machines_available: true,
                machines: sharedState.machines.concat([@@EXTERNAL@@])}));
            keyEvents.wait(30);
            const unselectedWidth = band.width;
            tile("dev-desk").activated();
            keyEvents.wait(30);
            const selectedBandBottom = band.mapToItem(stage, 0, band.height);
            const header = find(stage, "machine-context-header");
            check(header && visibleText(header, "dev-desk") && !sphere(header),
                  "context header must follow the selected Machine without a sphere");
            check(band.width === unselectedWidth
                  && header.mapToItem(stage, 0, 0).y >= selectedBandBottom.y,
                  "selected Machine pane must sit below the full-width network band");
            tile("lab-test").activated();
            keyEvents.wait(30);
            check(visibleText(header, "lab-test") && !sphere(header),
                  "context header did not follow selection");
            check(sharedMachineActions.operations.length === 0, "selection started a Machine");
            sharedSurfaces.clearMachineSelection();
            keyEvents.wait(30);
            tile("dev-desk").forceActiveFocus();
            keyEvents.keyClick(Qt.Key_Right);
            check(tile("dev-build").activeFocus, "Right did not move to the next tile");
            keyEvents.keyClick(Qt.Key_Left);
            check(tile("dev-desk").activeFocus, "Left did not return to the previous tile");
            keyEvents.keyClick(Qt.Key_Down);
            check(tile("service-desk").activeFocus, "Down did not cross a domain group");
            keyEvents.keyClick(Qt.Key_Up);
            check(tile("dev-desk").activeFocus, "Up did not return to the nearest tile");
            // Give adjacent groups a second column for this key sequence.
            // A single SERVICES tile would reset the current column to zero.
            update(@@ROWS@@.concat([Object.assign({}, @@ROWS@@[3], {name: "service-build"})]));
            tile("dev-build").forceActiveFocus();
            keyEvents.keyClick(Qt.Key_Down);
            check(tile("service-build").activeFocus,
                  "Down must keep the nearest second column across domain groups");
            keyEvents.keyClick(Qt.Key_Down);
            check(tile("lab-desk").activeFocus,
                  "Down must keep the nearest second column across domain groups");
            keyEvents.keyClick(Qt.Key_Up);
            check(tile("service-build").activeFocus,
                  "Up must keep the nearest second column across domain groups");
            keyEvents.keyClick(Qt.Key_Up);
            check(tile("dev-build").activeFocus,
                  "Up must keep the nearest second column across domain groups");
            update(@@ROWS@@);
            tile("dev-desk").forceActiveFocus();
            const viewport = viewportFor(tile("dev-desk"));
            check(viewport !== null, "showcase has no scroll viewport");
            if (viewport) {
                viewport.contentY = 0;
                const target = tile("lab-desk");
                const before = target.mapToItem(viewport, 0, 0);
                check(before.y + target.height > viewport.height,
                      "focus-scroll fixture must start with the LAB tile below the viewport");
                keyEvents.keyClick(Qt.Key_Down);
                keyEvents.keyClick(Qt.Key_Down);
                keyEvents.keyClick(Qt.Key_Right);
                keyEvents.wait(30);
                const after = target.mapToItem(viewport, 0, 0);
                check(target.activeFocus && viewport.contentY > 0
                      && after.y >= 0 && after.y + target.height <= viewport.height
                      && after.x >= 0 && after.x + target.width <= viewport.width,
                      "arrow focus must scroll the complete LAB tile into the viewport");
                tile("dev-desk").forceActiveFocus();
            }
            let activations = 0;
            tile("dev-desk").activated.connect(function() { activations += 1; });
            keyEvents.keyClick(Qt.Key_Return);
            check(activations === 1, "Enter must activate a tile exactly once");
            check(sharedSurfaces.selectedMachineId === "dev-desk", "Enter did not open the pane");
            sharedSurfaces.clearMachineSelection();
            const search = nodes(stage, item => item.Accessible.name === "Filter machines")[0];
            search.text = "lab-test";
            keyEvents.wait(30);
            check(stage.groups.length === 1 && stage.groups[0].identity === "lab"
                  && nodes(stage, item => item.objectName.indexOf("machine-tile-") === 0
                           && item.visible).length === 1 && stage.filteredOutside.length === 0,
                  "filter no longer controls the drawn tiles");
            search.text = "";
            stage.stateFilter = "running";
            check(stage.filtered.length === 1 && stage.filteredOutside.length === 1,
                  "running filter changed semantics");
            stage.stateFilter = "all";
            stage.layoutMode = "list";
            keyEvents.wait(30);
            const dense = nodes(stage, item => item.objectName.startsWith("machine-list-row-") && item.visible);
            check(dense.length === 6 && dense.every(item => !sphere(item)), "dense rows missing or draw spheres");
            for (const row of dense) {
                const facts = "Memory 8 GiB · vCPU 4 · Network " + row.machine.networks.join(", ");
                check(visibleText(row, facts) && row.Accessible.name.includes(facts),
                      "dense row lost its labelled allocation or observed networks");
            }
            update([]);
            check(find(band, "band-host").visible && visibleText(entry("lab"), "no machines"),
                  "empty registry has no host line or empty network");
            const creates = nodes(stage, item => item.visible && item.accessibleName !== undefined
                                  && /^(New Machine|Create a Machine)$/.test(item.accessibleName));
            check(creates.length === 1 && creates[0].accessibleName === "Create a Machine",
                  "empty registry must offer one Create a Machine action");
            check(visibleText(stage, "No Machines yet") && find(stage, "external-machine-outside-desk").visible,
                  "empty registry hid first-Machine guidance or external inventory");
            sharedState.applyOutsideDomainsPayload(JSON.stringify({machines_available: true, machines: []}));
            keyEvents.wait(30);
            check(nodes(stage, item => item.visible && typeof item.activated === "function"
                        && !item.objectName.startsWith("band-entry-")).length === 1
                  && !search.visible, "an empty view must expose only the creation action");
            creates[0].activated();
            check(stage.creating, "empty creation action did not open the existing Create view");
            stage.creating = false;
            sharedState.applyMachinePayload("{}");
            check(!find(stage, "machine-empty-state").visible
                  && visibleText(stage, "Machine inventory cannot be read"),
                  "unavailable inventory was presented as empty");
            update(@@ROWS@@);
            stage.query = "absent-name";
            keyEvents.wait(30);
            check(visibleText(stage, "No machine matches this filter")
                  && !find(stage, "machine-empty-state").visible,
                  "filtered inventory was presented as empty");
            stage.query = "";
            const unknown = Object.assign({}, @@ROWS@@[0], {memory_mb: null, vcpus: null,
                provenance: "unclassified", networks: null, state: "crashed", gpu_relation: "unknown"});
            update([unknown]);
            const unknownTile = tile(unknown.name);
            check(unknownTile.Accessible.name.includes("Memory unknown, vCPU unknown, Network unknown")
                  && visibleText(unknownTile, "Crashed") && visibleText(unknownTile, "Passthrough unknown")
                  && !sphere(unknownTile) && Qt.colorEqual(unknownTile.color, sharedTheme.raised),
                  "missing facts became a classified or plausible default");
            check(visibleText(entry("lab"), "machines unknown")
                  && !find(entry("lab"), "network-outline").visible,
                  "unreadable attachment became an empty network");
            update([Object.assign({}, @@ROWS@@[1], {networks: ["lab", "services"]})]);
            entry("lab").activate();
            check(stage.groups.length === 1 && stage.groups[0].identity === "lab"
                  && tile("dev-desk") && visibleText(entry("services"), "1 machine · 1 running"),
                  "band filter or membership follows provenance instead of attachment");
            entry("lab").activate();
            sharedState.machinesObservedAt -= 180000;
            check(visibleText(entry("lab"), "machines unknown") && !find(entry("lab"), "network-core").visible
                  && !find(entry("lab"), "network-outline").visible, "stale inventory claims a network state");
            update(@@ROWS@@);
            const extra = {name: "fixture-link", subnet: null, gateway: null, dhcp: false, trust: 0,
                           forward: null, state: "inactive"};
            sharedState.requestNetworks();
            sharedState.networkFixtureComplete(JSON.stringify([extra, Object.assign({}, networks[0], {
                gateway: false, dhcp: null, trust: 1
            })]), 0);
            keyEvents.wait(30);
            const changed = entry(networks[0].name);
            check(changed && changed.Accessible.name.includes("GPU level 1")
                  && changed.Accessible.name.includes("DHCP unknown") && visibleText(changed, "none")
                  && entry("fixture-link").Accessible.name.includes("DHCP off")
                  && visibleText(entry("fixture-link"), "unknown")
                  && nodes(band, item => item.objectName.startsWith("band-entry-")).length === 2,
                  "network re-read lost observed values, unknowns or source membership");
            entry("fixture-link").activate();
            sharedState.applyFeatures('{"networks_view_enabled":false}');
            check(!sharedState.networksReadable && !sharedState.requestNetworks()
                  && stage.networkFilter === "" && visibleText(band, "Network inventory off"),
                  "disabling the source left network rows or a hidden filter");
            sharedState.applyFeatures('{"networks_view_enabled":true}');
            sharedState.networkFixtureComplete(JSON.stringify(networks), 0);
            sharedState.applyOutsideDomainsPayload(JSON.stringify({machines_available: true,
                machines: @@ROWS@@.concat([@@EXTERNAL@@])}));
            check(stage.total === 7 && stage.filteredOutside.length === 1,
                  "render fixture did not restore all seven domains");
'''.replace("@@ROWS@@", json.dumps(ROWS)).replace("@@EXTERNAL@@", json.dumps(EXTERNAL))


def native(output: Path | None) -> None:
    runner = shutil.which("qmlscene6") or shutil.which("qmlscene")
    require(runner is not None, "Qt QML runner is required")
    root = (runtime.QML / "shell.qml").read_text()
    binding = re.search(r"networksMachinesVisible:\s*(.*?)\n\s*networksMapVisible:", root, re.S)
    require(binding is not None, "missing Machines network visibility binding")
    setup = SETUP.replace("@@NETWORKS@@", json.dumps(seal.network_rows()))

    def scenario(width: int, height: int, rows: list[dict], body: str, destination: str,
                 owner: str = "dev-desk") -> None:
        source, messages = runtime.scenario_source(width, height, rows, setup + body, out=destination,
            gpu={"text": owner, "class": "", "known": True, "owner": owner, "bound": bool(owner)})
        source = source.replace("import QtQuick.Window", "import QtQuick.Window\nimport QtTest")
        source = source.replace("ShellState { id: sharedState }", "ShellState { id: sharedState\n"
                                "networksMachinesVisible: " + binding[1] + "\n}\nTestCase { id: keyEvents; when: false }")
        runtime.run(runner, directory, f"showcase {width}x{height}", source, messages)
        if destination:
            require(len(set(png_pixels(Path(destination), (width, height)))) > 32, "native render is blank")

    directory = runtime.stage()
    try:
        for width, height in ((1440, 900), (1920, 1080)):
            destination = str(output / f"native-showcase-{width}x{height}.png") if output else ""
            scenario(width, height, ROWS, CHECKS, destination)
            if output:
                captures = {
                    "lower": 'const view = viewportFor(tile("lab-desk")); view.contentY = view.contentHeight - view.height;',
                    "selected": 'tile("dev-desk").activated();',
                    "empty": 'sharedState.applyOutsideDomainsPayload(JSON.stringify({machines_available:true, machines:[]})); update([]);',
                }
                for label, body in captures.items():
                    scenario(width, height, ROWS, body, str(output / f"native-showcase-{width}x{height}-{label}.png"))
        if output:
            for case in json.loads(seal.FIXTURE.read_text())["cases"]:
                if case["id"] not in {"no-machines", "five-networks", "thirty", "isolated"}:
                    continue
                rows = seal.rows_for(case)
                outside = json.dumps(rows + case["external"])
                body = f"sharedState.applyOutsideDomainsPayload(JSON.stringify({{machines_available:true, machines:{outside}}}));"
                body += f'check(stage.total === {len(rows) + len(case["external"])}, "capture population changed");'
                if case["id"] == "five-networks":
                    body += 'tile("dev-desk").activated();'
                if case.get("enter"):
                    body += 'find(stage, "band-entry-lab").activate();'
                    body += 'check(stage.networkFilter === "lab" && stage.groups.length === 0, "isolated selection failed");'
                scenario(1920, 1080, rows, body, str(output / (case["id"] + "-1920x1080.png")), case["gpu_owner"])
    finally:
        shutil.rmtree(directory)


def recovery() -> int:
    """Render the real GTK builder, not a reproduction of its styling."""
    with gtk_display() as gtk:
        from gi.repository import Gdk, GLib, Graphene
        namespace = load_manager(gtk)
        namespace.update(Path=Path, os=os)
        window = namespace["HyperlabWindow"]()
        window.model = namespace["Model"](
            domains=ROWS + [EXTERNAL],
            specs=[{"spec": {"name": row["name"], "network_profile": row["provenance"],
                              "lifecycle": row["lifecycle"]}} for row in ROWS],
            product_inventory={"machines_available": True, "machines": ROWS},
        )
        window.selected_vm = None
        window._grid_columns = {}
        css = gtk.CssProvider()
        palette = runtime.ROOT / "themes/trust-model/rendered/hyperlab-palette-gtk.css"
        css.load_from_data((palette.read_text() + "\n" + namespace["CSS"]).encode())
        gtk.Settings.get_default().set_property("gtk-application-prefer-dark-theme", True)
        gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css,
                                                  gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        require([window._domain_for_vm(row) for row in ROWS] == [row["provenance"] for row in ROWS],
                "GTK comparison lost the reviewed domain identities")
        page = window._build_vm_showcase(columns=3)
        labels = [item.get_text() for item in descendants(page) if isinstance(item, gtk.Label)]
        require(all(row["name"] in labels for row in ROWS + [EXTERNAL]), "GTK comparison lost a Machine")
        host = gtk.Window()
        host.set_decorated(False)
        host.set_default_size(1440, 900)
        scroll = gtk.ScrolledWindow()
        scroll.set_child(page)
        host.set_child(scroll)
        host.present()
        context = GLib.MainContext.default()
        for _ in range(40):
            while context.pending():
                context.iteration(False)
            GLib.usleep(5000)
        # Capture the allocated showcase itself, including the groups below
        # the scroll viewport, without scaling a constrained display window.
        width, height = page.get_width(), page.get_height()
        require(width > 0 and height > 0, "GTK showcase was not allocated")
        paintable = gtk.WidgetPaintable.new(page)
        snapshot = gtk.Snapshot()
        ground = Gdk.RGBA()
        require(ground.parse(json.loads(runtime.PALETTE.read_text())["base"]), "GTK ground is not a palette colour")
        snapshot.append_color(ground, Graphene.Rect().init(0, 0, width, height))
        paintable.snapshot(snapshot, width, height)
        node = snapshot.to_node()
        require(node is not None, "GTK snapshot is empty")
        texture = host.get_renderer().render_texture(node, Graphene.Rect().init(0, 0, width, height))
        destination = Path(os.environ["MACHINE_SHOWCASE_OUTPUT"]) / "gtk-showcase.png"
        require(texture.save_to_png(str(destination)), "GTK capture failed")
        host.destroy()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render-dir", type=Path)
    args = parser.parse_args()
    source_contract()
    if args.render_dir:
        args.render_dir.mkdir(parents=True, exist_ok=True)
        args.render_dir = args.render_dir.resolve()
    native(args.render_dir)
    if args.render_dir:
        os.environ["MACHINE_SHOWCASE_OUTPUT"] = str(args.render_dir)
        require(run_gtk_worker(Path(__file__)) == 0, "GTK comparison failed")
    print("Machine showcase contract: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(recovery() if "--gtk-worker" in sys.argv else main())
