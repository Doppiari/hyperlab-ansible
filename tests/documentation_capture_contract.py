#!/usr/bin/env python3
"""Documentation captures are reproducible without input simulation.

The shell's `navigate` IPC target opens every section of its navigation
model and selects a Machine by name, and nothing else. This contract proves:

  1. coverage: every destination and page of ShellSurfaces (the gated
     Networks and Nitro pages included), every launcher mode, the Create
     form, the system panel and the idle desktop has exactly one route, and
     no route names a section the model does not have;
  2. navigation only, statically: the route functions call nothing but the
     reviewed coordinator functions and reads, hold no action object, ask
     for no compositor raise, and nothing they reach inside ShellSurfaces is
     a confirmation, a clipboard send or an action OSD;
  3. navigation only, at runtime: the real ShellIpc, adapted like every
     other window host of the offscreen harness, walks every route over the
     real coordinator and views; each route lands where it says, refusals
     change nothing, and the recording action fixtures stay empty;
  4. `tools/docs/capture-shell` walks every route on a fake session (fake
     `qs`, `grim` and compositor adapter) with navigation calls only,
     captures one PNG per available route on an empty compositor slot and
     puts the shell, the rail and the slot back; it refuses an output
     directory inside the repository, a symlink or a non-empty directory;
  5. `capture-shell --demo DIR` renders every listed surface at 1920x1080
     and 3840x2160 from the fixture state file, offscreen, with no bridge.

What this does not prove: the real Quickshell IPC dispatcher, a real
compositor slot switch and real grim captures. That is the operator's run
on the Nitro.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

import host_quickshell_runtime_contract as runtime

ROOT = runtime.ROOT
QML = runtime.QML
SCRIPT = ROOT / "tools/docs/capture-shell"
RENDERER = ROOT / "tools/docs/render_demo.py"
FIXTURE = ROOT / "tests/fixtures/documentation-demo.json"

# Surfaces outside the destination table, each with its own reviewed route.
EXTRA_ROUTES = {
    "create": {"workspace": "machines", "page": "inventory", "form": "create"},
    "panel": {"panel": "system"},
    "desktop": {"desktop": "idle"},
}

# What a navigation route may call on the coordinator and on the state.
SURFACE_CALLS = {
    "openWorkspace", "openWorkspacePage", "openCreateForm", "closeCreateForm",
    "selectMachine",
    "openLauncher", "openSystemPanel", "closeWorkspace", "dismissAll",
    "validWorkspace", "validSubpage",
}
SURFACE_READS = {
    "workspaceOpen", "workspaceView", "subpage", "launcherOpen", "launcherMode",
    "systemPanelOpen", "selectedMachineId", "topRailVisible",
}
STATE_CALLS = {"machineById"}
STATE_READS = {"machinesGeneration"}
# Plain JavaScript a route may use on its own values.
BUILTIN_CALLS = {"String", "Object.keys", "Object.prototype.hasOwnProperty.call",
                 "JSON.stringify"}
VALUE_METHODS = {"join", "indexOf", "filter", "map", "some", "push"}
# Coordinator functions and signals that arm, send or report an action.
ACTIONS = {"requestClipboardSend", "clipboardSendRequested", "requestConfirmation",
           "submitConfirmation", "showActionOsd", "settleActionOsd"}
# Called with a third argument: a navigation route never asks for a raise.
NO_RAISE = {"openWorkspacePage": 2, "selectMachine": 2}
NAVIGATION_TARGETS = ("navigate", "workspace")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("Documentation capture contract: " + message)


# ------------------------------------------------------------- QML source

def without_comments(source: str) -> str:
    """Drop comments, keep string literals (route ids live in them)."""
    out: list[str] = []
    index = 0
    while index < len(source):
        if source.startswith("//", index):
            end = source.find("\n", index)
            index = len(source) if end < 0 else end
            continue
        if source.startswith("/*", index):
            end = source.find("*/", index + 2)
            require(end >= 0, "unterminated comment")
            index = end + 2
            continue
        char = source[index]
        if char in "\"'":
            end = index + 1
            while end < len(source) and source[end] != char:
                end += 2 if source[end] == "\\" else 1
            out.append(source[index:end + 1])
            index = end + 1
            continue
        out.append(char)
        index += 1
    return "".join(out)


def blank_strings(source: str) -> str:
    return re.sub(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'',
                  lambda match: '"' + " " * (len(match[0]) - 2) + '"', source)


def balanced(source: str, start: int, opening: str = "{", closing: str = "}") -> int:
    """Index just past the bracket matching the one at `start`."""
    require(source[start] == opening, "parser lost its bracket")
    depth = 0
    plain = blank_strings(source)
    for index in range(start, len(plain)):
        if plain[index] == opening:
            depth += 1
        elif plain[index] == closing:
            depth -= 1
            if depth == 0:
                return index + 1
    raise SystemExit("Documentation capture contract: unbalanced brackets")


def functions(body: str, indent: str) -> dict[str, tuple[str, str]]:
    """`name -> (parameters, body)` of the functions declared at `indent`."""
    found: dict[str, tuple[str, str]] = {}
    for match in re.finditer(r"(?m)^" + indent + r"function (\w+)\(([^)]*)\)[^{\n]*\{", body):
        end = balanced(body, match.end() - 1)
        require(match[1] not in found, f"function {match[1]} is declared twice")
        found[match[1]] = (match[2], body[match.end():end - 1])
    return found


def handlers(source: str) -> dict[str, dict[str, tuple[str, str]]]:
    found: dict[str, dict[str, tuple[str, str]]] = {}
    for match in re.finditer(r"(?m)^    IpcHandler \{", source):
        end = balanced(source, match.end() - 1)
        body = source[match.end():end - 1]
        target = re.findall(r'(?m)^        target: "([\w-]+)"$', body)
        require(len(target) == 1, "an IPC handler without exactly one literal target")
        require(target[0] not in found, f"IPC target {target[0]} is declared twice")
        found[target[0]] = functions(body, "        ")
    return found


def routes_table(source: str) -> dict[str, dict[str, str]]:
    match = re.search(r"(?m)^    readonly property var navigationRoutes: \((\{.*?\n    \})\)$",
                      source, re.S)
    require(match is not None, "ShellIpc.qml has no navigationRoutes table")
    pairs = json.loads(match[1], object_pairs_hook=lambda items: items)
    keys = [key for key, _ in pairs]
    require(len(keys) == len(set(keys)), "navigationRoutes names a route twice")
    table = {key: dict(value) for key, value in pairs}
    require(all(re.fullmatch(r"[a-z][a-z-]{1,30}", key) for key in table),
            "a route id is not lowercase words joined by dashes")
    return table


def navigation_model() -> dict[str, dict[str, str]]:
    """Every section the coordinator can show, keyed by its expected route."""
    source = without_comments((QML / "ShellSurfaces.qml").read_text(encoding="utf-8"))
    destinations = re.search(r"readonly property var destinations: (\[[^]]*\])", source)
    subpages = re.search(r"readonly property var subpages: \((\{.*?\})\)", source, re.S)
    require(destinations is not None and subpages is not None,
            "ShellSurfaces.qml lost its destination or subpage table")
    views = json.loads(destinations[1])
    pages = json.loads(subpages[1])
    require(sorted(views) == sorted(pages), "destinations and subpages disagree")
    gated = re.findall(r'String\(view\) === "(\w+)" && String\(candidate\) === "(\w+)"', source)
    require(gated, "validSubpage lost its gated pages")
    for view, page in gated:
        require(view in pages and page not in pages[view], f"gated page {view}/{page} is not extra")
        pages[view] = pages[view] + [page]
    model: dict[str, dict[str, str]] = {}
    for view in views:
        for page in pages[view]:
            route = view if len(pages[view]) == 1 else f"{view}-{page}"
            model[route] = {"workspace": view, "page": page}
    launcher = re.search(r'\[("[\w"\s,]*")\]\.indexOf\(String\(mode\)\)', source)
    require(launcher is not None, "openLauncher lost its mode list")
    modes = json.loads("[" + launcher[1] + "]")
    model["launcher"] = {"launcher": ""}
    for mode in modes:
        model[mode] = {"launcher": mode}
    model.update(EXTRA_ROUTES)
    return model


def callees(body: str) -> list[str]:
    plain = blank_strings(body)
    return re.findall(r"(?<![\w.])((?:\w+\s*\.\s*)*\w+)\s*\(", plain)


def check_body(where: str, body: str, helpers: set[str]) -> set[str]:
    """Refuse anything but reviewed navigation; return coordinator calls."""
    plain = blank_strings(body)
    surfaces: set[str] = set()
    for match in re.finditer(r"\bipc\b(?:\s*\.\s*(\w+))?(?:\s*\.\s*(\w+))?", plain):
        owner, member = match[1], match[2]
        require(owner is not None, f"{where}: refers to the whole IPC scope")
        if owner == "shellSurfaces":
            require(member in SURFACE_CALLS | SURFACE_READS,
                    f"{where}: navigation route uses shellSurfaces.{member}")
            if member in SURFACE_CALLS:
                surfaces.add(member)
        elif owner == "shellState":
            require(member in STATE_CALLS | STATE_READS,
                    f"{where}: navigation route uses shellState.{member}")
        else:
            require(owner in helpers or owner == "navigationRoutes",
                    f"{where}: navigation route uses ipc.{owner}")
    for callee in callees(body):
        name = re.sub(r"\s+", "", callee)
        parts = name.split(".")
        if parts[0] in {"function", "if", "for", "while", "switch", "return"}:
            continue
        if parts[0] == "ipc":
            continue  # checked member by member above
        if name in BUILTIN_CALLS:
            continue
        require(len(parts) > 1 and parts[-1] in VALUE_METHODS,
                f"{where}: navigation route calls {name}")
    for function, position in NO_RAISE.items():
        for match in re.finditer(r"ipc\.shellSurfaces\." + function + r"\(", plain):
            end = balanced(plain, match.end() - 1, "(", ")")
            arguments = plain[match.end():end - 1].split(",")
            require(len(arguments) > position and arguments[position].strip() == "false",
                    f"{where}: {function} may ask the compositor for a raise")
    return surfaces


def reachable(entry: set[str]) -> set[str]:
    """Coordinator functions and signals reached from `entry`."""
    source = without_comments((QML / "ShellSurfaces.qml").read_text(encoding="utf-8"))
    declared = functions(source, "    ")
    signals = set(re.findall(r"(?m)^    signal (\w+)\(", source))
    seen: set[str] = set()
    pending = list(entry)
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        require(name in declared or name in signals, f"ShellSurfaces has no {name}")
        seen.add(name)
        if name in declared:
            pending.extend(re.findall(r"\bsurfaces\.(\w+)\s*\(", blank_strings(declared[name][1])))
    return seen


def static_contract() -> dict[str, dict[str, str]]:
    source = without_comments((QML / "ShellIpc.qml").read_text(encoding="utf-8"))
    require(not re.search(r"\b(?:Process|Quickshell\.exec\w*|execDetached)\b", source),
            "ShellIpc.qml can start a process")
    properties = set(re.findall(r"(?m)^    (?:required )?property \w+ (\w+)", source))
    require(properties == {"shellState", "shellSurfaces", "theme"},
            f"ShellIpc.qml holds more than state, coordinator and theme: {sorted(properties)}")
    table = routes_table(source)
    model = navigation_model()
    for route, section in model.items():
        require(route in table, f"no IPC route for {route}")
        require(table[route] == section, f"route {route} opens {table[route]}, not {section}")
    for route in table:
        require(route in model, f"route {route} names no section of the navigation model")

    scope = functions(source, "    ")
    targets = handlers(source)
    for target in NAVIGATION_TARGETS:
        require(target in targets, f"ShellIpc.qml has no {target} target")
    require({"routes", "open", "machine", "current"} <= set(targets["navigate"]),
            "the navigate target lost routes, open, machine or current")
    coordinator: set[str] = set()
    pending = [(f"{target}.{name}", body) for target in NAVIGATION_TARGETS
               for name, (_, body) in targets[target].items()]
    checked: set[str] = set()
    while pending:
        where, body = pending.pop()
        coordinator |= check_body(where, body, set(scope))
        for helper in re.findall(r"\bipc\.(\w+)\s*\(", blank_strings(body)):
            if helper in scope and helper not in checked:
                checked.add(helper)
                pending.append((helper, scope[helper][1]))
    reached = reachable(coordinator)
    require(not reached & ACTIONS,
            f"a navigation route reaches {sorted(reached & ACTIONS)}")
    return table


# ------------------------------------------------------------------ runtime

RUNTIME = r"""
            const routes = @@ROUTES@@;
            const navigate = ipcTarget("navigate");
            const workspaceTarget = ipcTarget("workspace");
            check(navigate !== null && workspaceTarget !== null, "the adapted IPC targets are missing");
            if (window.firstFailure >= 0) { Qt.exit(@@BASE@@ + window.firstFailure); return; }
            const stage = find(workspaceSurface, "machine-stage");
            function snapshot() {
                return JSON.stringify([sharedSurfaces.workspaceOpen, sharedSurfaces.workspaceView,
                    sharedSurfaces.subpage, sharedSurfaces.launcherOpen, sharedSurfaces.launcherMode,
                    sharedSurfaces.systemPanelOpen, sharedSurfaces.selectedMachineId,
                    sharedSurfaces.topRailVisible, stage.creating]);
            }
            function nothingActed() {
                return sharedActions.invoked.length === 0 && sharedActions.launched.length === 0
                    && sharedActions.workspaces.length === 0
                    && sharedMachineActions.operations.length === 0
                    && sharedMachineActions.created.length === 0
                    && sharedMachineActions.usbAllowed.length === 0
                    && sharedMachineActions.panicRestores.length === 0
                    && sharedMachineActions.diagnosticsCalls.length === 0
                    && sharedSurfaces.confirmation === null;
            }
            check(navigate.routes() === routes.join("\n"), "routes() differs from the route table");

            // Refusals change nothing.
            let before = snapshot();
            for (const name of ["", "nonsense", "toString", "__proto__", "constructor",
                                "controls", "Machines", "sfere "])
                check(navigate.open(name) === "refused", "an unknown route was not refused");
            check(snapshot() === before, "a refused route changed the shell");
            for (const name of ["controls-networks", "controls-nitro"])
                check(navigate.open(name) === "unavailable", "a switched-off page was not unavailable");
            check(snapshot() === before, "an unavailable route changed the shell");
            for (const name of ["", "absent", "fixture-001 ", "FIXTURE-001"])
                check(navigate.machine(name) === "refused", "an unknown Machine was selected");
            check(snapshot() === before, "a refused Machine changed the shell");

            sharedState.applyFeatures('{"networks_view_enabled": true, "nitro_view_enabled": true}');
            for (const name of routes) {
                const entry = sharedIpc.navigationRoutes[name];
                check(navigate.open(name) === name, "a route did not land where it says");
                const state = JSON.parse(navigate.current());
                if (entry.desktop !== undefined)
                    check(!sharedSurfaces.workspaceOpen && !sharedSurfaces.launcherOpen
                          && !sharedSurfaces.systemPanelOpen && state.workspace === ""
                          && state.transient === "", "desktop left a surface open");
                else if (entry.panel !== undefined)
                    check(sharedSurfaces.systemPanelOpen && systemPanel.visible && state.transient === name,
                          "the panel route did not show the system panel");
                else if (entry.launcher !== undefined)
                    check(sharedSurfaces.launcherOpen && launcher.visible
                          && sharedSurfaces.launcherMode === entry.launcher && state.transient === name,
                          "a launcher route did not show its mode");
                else
                    check(sharedSurfaces.workspaceOpen && workspaceSurface.visible
                          && sharedSurfaces.workspaceView === entry.workspace
                          && sharedSurfaces.subpage === entry.page
                          && (entry.workspace !== "machines" || stage.creating === (entry.form === "create"))
                          && state.workspace === (entry.form === "create" ? "machines" : name),
                          "a workspace route did not show its page, or left the Create form");
            }
            check(navigate.open("create") === "create" && stage.creating, "create did not open the form");
            check(navigate.open("machines") === "machines" && !stage.creating,
                  "machines left the Create form over the inventory");
            check(navigate.open("create") === "create", "create did not reopen");
            check(navigate.machine("fixture-002") === "fixture-002"
                  && sharedSurfaces.selectedMachineId === "fixture-002" && !stage.creating
                  && JSON.parse(navigate.current()).machine === "fixture-002",
                  "machine() did not select and show the named Machine");
            // A creation in flight keeps its form.
            navigate.open("create");
            sharedMachineActions.creating = true;
            navigate.open("machines");
            check(stage.creating, "a creation in flight lost its form");
            sharedMachineActions.creating = false;
            navigate.open("machines");
            check(!stage.creating, "the form stayed after the creation settled");

            // A confirmation armed before navigating is withdrawn, never run.
            navigate.open("controls-session");
            sharedSurfaces.requestConfirmation({kind: "session", actionId: "session-reboot",
                targetId: "host", targetName: "This host", title: "t", consequence: "c",
                confirmLabel: "Reboot", requiresName: false, generation: -1});
            navigate.open("diagnostics-overview");
            check(nothingActed(), "a navigation route reached an action or kept a dialog armed");
            sharedSurfaces.hideTopRail();
            check(JSON.parse(navigate.current()).rail === "hidden", "current() hides the rail state");
            sharedSurfaces.showTopRail();

            // The older workspace target asks only for the reviewed raise.
            for (const name of ["sfere", "machines", "controls", "diagnostics", "workbench",
                                "devices", "close"])
                workspaceTarget[name]();
            check(sharedActions.invoked.every(action => action === "workspace-window-focus")
                  && sharedMachineActions.operations.length === 0,
                  "the workspace target reached an action other than the raise");
"""


def runtime_contract(table: dict[str, dict[str, str]]) -> None:
    sys.path.insert(0, str(ROOT / "tools/docs"))
    import render_demo

    runner = shutil.which("qmlscene", path="/usr/lib/qt6/bin") or shutil.which("qmlscene6")
    require(runner is not None, "Qt 6 qmlscene is required")
    directory = render_demo.stage()
    try:
        body = (RUNTIME.replace("@@ROUTES@@", json.dumps(list(table)))
                .replace("@@BASE@@", str(runtime.FAILURE_BASE)))
        source, messages = render_demo.harness(1920, 1080, runtime.machines(6), body)
        runtime.run(runner, directory, "navigation routes", source, messages)
    finally:
        shutil.rmtree(directory, ignore_errors=True)


# ------------------------------------------------------------------- script

# A fake session: the shell answers from the real route table, the
# compositor has slots 1, 2 and 5 occupied and 2 active, grim writes a PNG.
# Every call is logged; the shell refuses anything but navigation.
FAKE_QS = r"""#!/usr/bin/env python3
import json, os, sys
state_path, log = os.environ["FAKE_STATE"], os.environ["FAKE_LOG"]
state = json.load(open(state_path))
with open(log, "a") as handle:
    handle.write(json.dumps(["qs"] + sys.argv[1:]) + "\n")
args = sys.argv[1:]
if args[:4] != ["-c", "hyperlab", "ipc", "call"] or len(args) < 6:
    sys.exit(1)
target, function, rest = args[4], args[5], args[6:]
routes = json.load(open(os.environ["FAKE_ROUTES"]))
answer = None
if target == "navigate" and function == "routes" and not rest:
    answer = "\n".join(routes)
elif target == "navigate" and function == "current" and not rest:
    answer = json.dumps({key: state[key] for key in ("workspace", "transient", "machine", "rail")})
elif target == "navigate" and function == "open" and len(rest) == 1:
    route = rest[0]
    if route not in routes:
        answer = "refused"
    elif route in state["unavailable"]:
        answer = "unavailable"
    else:
        entry = routes[route]
        if "desktop" in entry:
            state.update(workspace="", transient="", machine="")
        elif "launcher" in entry or "panel" in entry:
            state["transient"] = route
        else:
            state.update(workspace="machines" if "form" in entry else route, transient="", machine="")
        answer = route
elif target == "navigate" and function == "machine" and len(rest) == 1:
    if rest[0] in state["machines"]:
        state.update(workspace="machines", transient="", machine=rest[0])
        answer = rest[0]
    else:
        answer = "refused"
elif target == "bar" and function in ("show", "hide") and not rest:
    state["rail"] = "visible" if function == "show" else "hidden"
    answer = state["rail"]
else:
    sys.exit(1)
json.dump(state, open(state_path, "w"))
print(answer)
"""

FAKE_ADAPTER = r"""#!/usr/bin/env python3
import json, os, sys
state_path = os.environ["FAKE_STATE"]
state = json.load(open(state_path))
with open(os.environ["FAKE_LOG"], "a") as handle:
    handle.write(json.dumps(["adapter"] + sys.argv[1:]) + "\n")
if sys.argv[1:] == ["workspaces-json"]:
    print(json.dumps({"active": state["slot"], "output": "eDP-1", "occupied": [1, 2, 5],
                      "urgent": []}))
elif len(sys.argv) == 3 and sys.argv[1] == "workspace-select":
    state["slot"] = int(sys.argv[2])
    json.dump(state, open(state_path, "w"))
else:
    sys.exit(2)
"""

FAKE_GRIM = r"""#!/usr/bin/env python3
import json, os, sys
state = json.load(open(os.environ["FAKE_STATE"]))
with open(os.environ["FAKE_LOG"], "a") as handle:
    handle.write(json.dumps(["grim", state["slot"], state["workspace"], state["transient"]]
                            + sys.argv[1:]) + "\n")
if os.environ.get("FAKE_GRIM_FAILS") == sys.argv[-1].rsplit("/", 1)[-1]:
    sys.exit(1)
open(sys.argv[-1], "wb").write(b"\x89PNG\r\n\x1a\nfake")
"""

START = {"workspace": "controls-audio", "transient": "keys", "machine": "", "rail": "hidden",
         "slot": 2, "machines": ["dev-desk"], "unavailable": ["controls-nitro"]}


def fake_session(scratch: Path, table: dict) -> dict[str, str]:
    bindir = scratch / "bin"
    bindir.mkdir()
    for name, body in (("qs", FAKE_QS), ("grim", FAKE_GRIM),
                       ("privatestack-compositor-adapter", FAKE_ADAPTER)):
        (bindir / name).write_text(body, encoding="utf-8")
        (bindir / name).chmod(0o755)
    (scratch / "routes.json").write_text(json.dumps(table), encoding="utf-8")
    (scratch / "state.json").write_text(json.dumps(START), encoding="utf-8")
    (scratch / "log").write_text("", encoding="utf-8")
    return dict(os.environ, PATH=str(bindir) + os.pathsep + os.environ.get("PATH", ""),
                FAKE_STATE=str(scratch / "state.json"), FAKE_LOG=str(scratch / "log"),
                FAKE_ROUTES=str(scratch / "routes.json"))


def capture(arguments: list[str], environment: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(SCRIPT), *arguments], capture_output=True, text=True,
                          timeout=120, env=environment or dict(os.environ), check=False)


def script_contract(table: dict[str, dict[str, str]]) -> None:
    require(SCRIPT.is_file() and os.access(SCRIPT, os.X_OK), "tools/docs/capture-shell is not executable")
    require(capture([]).returncode == 2, "no directory is not a usage error")
    for arguments in (["--demo", "--machine", "dev-desk", "x"], ["--settle", "fast", "x"],
                      ["--machine", "a b", "x"], ["--frobnicate", "x"], ["a", "b"]):
        require(capture(arguments).returncode == 2, f"{arguments} is not a usage error")
    with tempfile.TemporaryDirectory(prefix="capture-shell-") as temporary:
        scratch = Path(temporary)
        (scratch / "full").mkdir()
        (scratch / "full/old.png").write_bytes(b"")
        (scratch / "file").write_text("", encoding="utf-8")
        (scratch / "link").symlink_to(scratch / "full")
        refusals = {
            str(ROOT / "documentation-captures"): "inside the repository",
            str(ROOT / "tests/../tools"): "inside the repository",
            str(scratch / "full"): "is not empty",
            str(scratch / "file"): "is not a directory",
            str(scratch / "link"): "is a symlink",
            str(scratch / "missing/out"): "does not exist",
        }
        for directory, reason in refusals.items():
            result = capture(["--demo", directory])
            created = ROOT / "documentation-captures"
            if created.is_dir() and not any(created.iterdir()):
                created.rmdir()
                raise SystemExit("Documentation capture contract: a refused directory was "
                                 "created inside the repository")
            require(result.returncode == 1 and reason in result.stderr,
                    f"{directory} was not refused ({reason}): {result.stderr.strip()}")

        environment = fake_session(scratch, table)
        out = scratch / "live"
        result = capture(["--settle", "0", "--machine", "dev-desk", str(out)], environment)
        require(result.returncode == 0, f"the live walk failed: {result.stderr.strip()}")
        available = [route for route in table if route not in START["unavailable"]]
        expected = sorted([f"shell-{route}.png" for route in available] + ["shell-machine-dev-desk.png"])
        require(sorted(path.name for path in out.iterdir()) == expected,
                "the live walk did not write one capture per available route")
        log = [json.loads(line) for line in (scratch / "log").read_text().splitlines()]
        state = json.loads((scratch / "state.json").read_text())
        require(all(entry[0] != "qs" or (entry[5], entry[6]) in {
                    ("navigate", "routes"), ("navigate", "current"), ("navigate", "open"),
                    ("navigate", "machine"), ("bar", "show"), ("bar", "hide")} for entry in log),
                "the live walk made a shell call that is not navigation")
        grabs = [entry for entry in log if entry[0] == "grim"]
        require(len(grabs) == len(expected)
                and all(entry[1] == 9 and entry[4:6] == ["-o", "eDP-1"] for entry in grabs),
                "a capture was not taken on the empty slot 9 of the focused output")
        require(all((entry[2] == route or entry[3] == route or (route == "desktop" and entry[2:4] == ["", ""])
                     or (route == "create" and entry[2] == "machines"))
                    for entry in grabs for route in [entry[-1].rsplit("/shell-", 1)[1][:-4]]
                    if not route.startswith("machine-")),
                "a capture was taken on another surface than its route")
        selects = [entry[2] for entry in log if entry[0] == "adapter" and entry[1] == "workspace-select"]
        require(selects == ["9", "2"], f"the slots were not switched to 9 and back to 2: {selects}")
        require({key: state[key] for key in START} == START, f"the shell was not put back: {state}")
        require(log[-1][5:] == ["bar", "hide"], "the hidden rail was not hidden again last")

        # A failing capture still puts everything back.
        (scratch / "again").mkdir()
        environment = fake_session(scratch / "again", table)
        environment["FAKE_GRIM_FAILS"] = "shell-diagnostics-overview.png"
        result = capture(["--settle", "0", str(scratch / "failed")], environment)
        state = json.loads((scratch / "again/state.json").read_text())
        require(result.returncode != 0 and "grim could not capture" in result.stderr,
                "a failed capture did not fail the run")
        require({key: state[key] for key in START} == START, "a failed run did not restore the shell")
        require(not (scratch / "failed/shell-workbench.png").exists(), "the walk continued after a failure")


def demo_contract(table: dict[str, dict[str, str]]) -> None:
    sys.path.insert(0, str(ROOT / "tools/docs"))
    import render_demo
    from trust_pool_v3_generated_contract import png_pixels

    try:
        fixture = render_demo.load_fixture(FIXTURE)
    except render_demo.FixtureError as error:
        raise SystemExit(f"Documentation capture contract: the demo fixture is refused: {error}") from None
    with tempfile.TemporaryDirectory(prefix="capture-shell-demo-") as temporary:
        out = Path(temporary) / "demo"
        result = capture(["--demo", str(out)])
        require(result.returncode == 0, f"capture-shell --demo failed: {result.stderr.strip()}")
        expected = render_demo.expected_names(fixture, list(table))
        require(sorted(path.name for path in out.iterdir()) == sorted(expected),
                "capture-shell --demo did not write exactly the listed renders")
        require(render_demo.LOCK_NOTE in result.stdout, "the lock surface skip is not reported")
        for name in expected:
            size = tuple(int(part) for part in name.rsplit("-", 1)[1][:-4].split("x"))
            header = (out / name).read_bytes()[:24]
            require(header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR"
                    and (int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")) == size,
                    f"{name} is not a {size[0]}x{size[1]} PNG")
            # Decoding every 4K render in Python takes minutes; the 1920x1080
            # set shows the same scenes at the same layout.
            if size == (1920, 1080):
                require(len(set(png_pixels(out / name, size))) > 32, f"{name} is blank")


def fixture_contract() -> None:
    sys.path.insert(0, str(ROOT / "tools/docs"))
    import render_demo

    good = json.loads(FIXTURE.read_text(encoding="utf-8"))
    breaks = {
        "three running": lambda d: d["machines"][2].update(state="running"),
        "two disposable": lambda d: d["machines"][0].update(lifecycle="disposable"),
        "owner shut off": lambda d: d.update(gpu_owner="service-db"),
        "domain twice": lambda d: d["machines"][0].update(domain="dev"),
        "focus order": lambda d: d["focus"].reverse(),
        "focus elsewhere": lambda d: d["focus"][1].update(machine="dev-desk"),
        "extra key": lambda d: d.update(notes=""),
    }
    with tempfile.TemporaryDirectory(prefix="demo-fixture-") as temporary:
        path = Path(temporary) / "fixture.json"
        for label, change in breaks.items():
            document = json.loads(json.dumps(good))
            change(document)
            path.write_text(json.dumps(document), encoding="utf-8")
            try:
                render_demo.load_fixture(path)
            except render_demo.FixtureError:
                continue
            raise SystemExit(f"Documentation capture contract: the fixture break {label!r} was accepted")
        path.write_text(FIXTURE.read_text(encoding="utf-8").replace(
            '"gpu_owner": "dev-desk",', '"gpu_owner": "dev-desk", "gpu_owner": "clean-desk",'),
            encoding="utf-8")
        try:
            render_demo.load_fixture(path)
        except render_demo.FixtureError:
            return
        raise SystemExit("Documentation capture contract: a repeated fixture key was accepted")


def main() -> int:
    table = static_contract()
    print(f"  static: {len(table)} routes, navigation only")
    runtime_contract(table)
    fixture_contract()
    script_contract(table)
    print("  capture-shell: refusals, live walk and restore")
    demo_contract(table)
    print("  capture-shell --demo: every listed render at both sizes")
    print("Documentation capture contract: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
