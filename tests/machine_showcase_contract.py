#!/usr/bin/env python3
"""Execute the native Machines showcase and render its GTK comparison.

Only host transports are substituted by the shared offscreen Qt harness.
The fixture is six registry Machines in four domains and one external domain;
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
        "MachineStage.qml", "MachineTile.qml", "MachineListRow.qml", "MachineContextPane.qml")]
    for path in paths:
        require(path.is_file(), f"{path.name} is missing")
        source = path.read_text(encoding="utf-8")
        if path.name == "MachineTile.qml":
            require(len(list(blocks(strip_noise(source), "MachineSphere", False))) == 1,
                    "MachineTile must contain one MachineSphere")
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
            sharedState.applyOutsideDomainsPayload(JSON.stringify({
                machines_available: true, machines: sharedState.machines.concat([@@EXTERNAL@@]) }));
            sharedSurfaces.openWorkspace("machines");
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
            function update(rows) {
                sharedSurfaces.clearMachineSelection();
                sharedState.applyMachinePayload(JSON.stringify({machines_available: true, machines: rows}));
                stage.query = "";
                stage.layoutMode = "grid";
                keyEvents.wait(30);
            }
            keyEvents.wait(40);
'''.replace("@@EXTERNAL@@", json.dumps(EXTERNAL))

CHECKS = r'''
            check(stage.groups.map(group => group.identity).join(",") === "clean,dev,services,lab",
                  "groups must follow palette order and omit empty domains");
            check(nodes(stage, item => item.objectName.indexOf("machine-group-") === 0
                        && item.visible).map(item => item.objectName).join(",")
                  === "machine-group-clean,machine-group-dev,machine-group-services,machine-group-lab",
                  "drawn groups differ from the nonempty inventory groups");
            for (const row of sharedState.machines) {
                const card = tile(row.name);
                check(card && card.visible, "Machine tile missing");
                if (!card) continue;
                const ball = sphere(card);
                check(ball !== undefined, "tile has no MachineSphere");
                if (!ball) continue;
                check(ball.domain === row.provenance && ball.state === row.state
                      && ball.disposable === (row.lifecycle === "disposable")
                      && ball.gpuOwner === (row.gpu_relation === "held"),
                      "tile sphere lost confirmed Machine facts");
                check(card.Accessible.name.indexOf(row.name) >= 0 && card.activeFocusOnTab,
                      "tile has no accessible name or keyboard focus");
                check(visibleText(card, stage.icons.machineStateWord(row.state))
                      && visibleText(card, row.name)
                      && visibleText(card, "8 GiB · 4 vCPU · " + row.provenance),
                      "tile lost state, name or allocation line");
                check(card.width >= 300 && card.width <= 420 && card.height >= 150,
                      "tile dimensions escape the reviewed range");
                check(!Qt.colorEqual(card.color, sharedTheme.raised), "tile has no domain wash");
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
            const external = find(stage, "external-machine-outside-desk");
            check(external && external.visible && sphere(external), "external tile has no sphere");
            if (external) {
                check(external.color.a === 0 && Qt.colorEqual(external.border.color, sharedTheme.textPrimary)
                      && !sphere(external).classified && sphere(external).domainWord === "external",
                      "external tile borrowed a domain colour or fill");
                check(visibleText(external, "Unknown · Unknown vCPU · external"),
                      "external allocation must remain unknown when the projection omits it");
                check(external.Accessible.name.indexOf("outside-desk") >= 0
                      && !external.activeFocusOnTab && external.activated === undefined,
                      "external tile lost accessibility or gained selection");
                const last = tile("lab-desk").mapToItem(stage, 0, 0);
                check(external.mapToItem(stage, 0, 0).y > last.y,
                      "external group must follow every managed group");
            }
            tile("dev-desk").activated();
            keyEvents.wait(30);
            const header = find(stage, "machine-context-sphere");
            check(header && header.size > sphere(tile("dev-desk")).size
                  && header.domain === "dev" && header.state === "running" && header.gpuOwner,
                  "context header has no matching larger sphere");
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
            check(nodes(stage, item => item.objectName.indexOf("machine-list-sphere-") === 0
                        && item.visible).length === 6, "dense rows lost their spheres");
            update([]);
            check(find(stage, "empty-host-sphere").visible
                  && find(stage, "empty-host-sphere").isHost,
                  "empty registry has no host sphere");
            const creates = nodes(stage, item => item.visible && item.accessibleName !== undefined
                                  && /^(New Machine|Create a Machine)$/.test(item.accessibleName));
            check(creates.length === 1 && creates[0].accessibleName === "Create a Machine",
                  "empty registry must offer one Create a Machine action");
            check(visibleText(stage, "No Machines yet") && find(stage, "external-machine-outside-desk").visible,
                  "empty registry hid first-Machine guidance or external inventory");
            sharedState.applyOutsideDomainsPayload(JSON.stringify({machines_available: true, machines: []}));
            keyEvents.wait(30);
            check(nodes(stage, item => item.visible && typeof item.activated === "function").length === 1
                  && !search.visible, "an empty view must expose only the creation action");
            creates[0].activated();
            check(stage.creating, "empty creation action did not open the existing Create view");
            stage.creating = false;
            sharedState.applyMachinePayload("{}");
            check(!find(stage, "empty-host-sphere").visible
                  && visibleText(stage, "Machine inventory cannot be read"),
                  "unavailable inventory was presented as empty");
            update(@@ROWS@@);
            stage.query = "absent-name";
            keyEvents.wait(30);
            check(visibleText(stage, "No machine matches this filter")
                  && !find(stage, "empty-host-sphere").visible,
                  "filtered inventory was presented as empty");
            stage.query = "";
            const unknown = Object.assign({}, @@ROWS@@[0], {memory_mb: null, vcpus: null,
                provenance: "unclassified", state: "crashed", gpu_relation: "unknown"});
            update([unknown]);
            const unknownTile = tile(unknown.name);
            check(visibleText(unknownTile, "Unknown · Unknown vCPU · unclassified")
                  && visibleText(unknownTile, "Crashed") && visibleText(unknownTile, "Passthrough unknown")
                  && !sphere(unknownTile).classified && Qt.colorEqual(unknownTile.color, sharedTheme.raised),
                  "missing facts became a classified or plausible default");
            update(@@ROWS@@);
            sharedState.applyOutsideDomainsPayload(JSON.stringify({machines_available: true,
                machines: @@ROWS@@.concat([@@EXTERNAL@@])}));
            check(stage.total === 7 && stage.filteredOutside.length === 1,
                  "render fixture did not restore all seven domains");
'''.replace("@@ROWS@@", json.dumps(ROWS)).replace("@@EXTERNAL@@", json.dumps(EXTERNAL))


def native(output: Path | None) -> None:
    runner = shutil.which("qmlscene6") or shutil.which("qmlscene")
    require(runner is not None, "Qt QML runner is required")
    directory = runtime.stage()
    try:
        for width, height in ((1440, 900), (1920, 1080)):
            destination = str(output / f"native-showcase-{width}x{height}.png") if output else ""
            source, messages = runtime.scenario_source(width, height, ROWS, SETUP + CHECKS, out=destination,
                                                       gpu={"text": "dev-desk", "class": "", "known": True,
                                                            "owner": "dev-desk", "bound": True})
            source = source.replace("import QtQuick.Window", "import QtQuick.Window\nimport QtTest")
            source = source.replace("ShellState { id: sharedState }", "ShellState { id: sharedState }\n"
                                    "    TestCase { id: keyEvents; when: false }")
            runtime.run(runner, directory, f"showcase {width}x{height}", source, messages)
            if output:
                pixels = png_pixels(Path(destination), (width, height))
                require(len(set(pixels)) > 32, "native render is blank")
                captures = {
                    "lower": """
                        let view = find(stage, "external-machine-list").parent;
                        while (view && view.contentY === undefined) view = view.parent;
                        check(view !== null, "showcase has no scroll viewport");
                        if (view) view.contentY = Math.max(0, view.contentHeight - view.height);
                    """,
                    "selected": 'tile("dev-desk").activated();',
                    "empty": """
                        sharedState.applyOutsideDomainsPayload(JSON.stringify({
                            machines_available: true, machines: []}));
                        update([]);
                    """,
                }
                for label, body in captures.items():
                    destination = str(output / f"native-showcase-{width}x{height}-{label}.png")
                    source, messages = runtime.scenario_source(width, height, ROWS, SETUP + body, out=destination,
                                                               gpu={"text": "dev-desk", "class": "", "known": True,
                                                                    "owner": "dev-desk", "bound": True})
                    source = source.replace("import QtQuick.Window", "import QtQuick.Window\nimport QtTest")
                    source = source.replace("ShellState { id: sharedState }", "ShellState { id: sharedState }\n"
                                            "    TestCase { id: keyEvents; when: false }")
                    runtime.run(runner, directory, f"showcase capture {label} {width}x{height}", source, messages)
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
