// HyperLab IPC receivers (V447-C9.3).
//
// The only way into the shell from outside: fixed, argument-checked
// functions that summon presentation surfaces. A caller can open the command
// palette, open a product destination or ask the OSD to show a telemetry
// kind; it cannot pass a value, a command or a path, and nothing here starts
// a process.
//
//   qs -c hyperlab ipc call launcher toggle
//   qs -c hyperlab ipc call workspace sfere
//   qs -c hyperlab ipc call workspace machines
//   qs -c hyperlab ipc call workspace close
//   qs -c hyperlab ipc call osd show audio
//   qs -c hyperlab ipc call panel system
//   qs -c hyperlab ipc call session locking
//   qs -c hyperlab ipc call navigate open controls-audio
//   qs -c hyperlab ipc call navigate machine dev-desk
//
// Compositor keybindings use these so the host shortcuts and the pointer
// reach exactly the same surfaces, on Hyprland and on Sway alike.
//
// `navigate` reaches every section of the navigation model by a fixed route
// id, so documentation captures need no input simulation. It is navigation
// only: it opens, closes and selects, never asks the compositor for anything,
// never arms a confirmation and never reaches an action.

import Quickshell
import Quickshell.Io
import QtQuick

Scope {
    id: ipc

    required property var shellState
    required property var shellSurfaces
    required property var theme

    // One route per section of the navigation model, and nothing else.
    // Workspace pages name their destination and page; the Create form is a
    // state of Machines; launcher modes, the system panel and the idle
    // desktop are the surfaces outside the workspace.
    readonly property var navigationRoutes: ({
        "sfere": { "workspace": "sfere", "page": "map" },
        "machines": { "workspace": "machines", "page": "inventory" },
        "create": { "workspace": "machines", "page": "inventory", "form": "create" },
        "controls-session": { "workspace": "controls", "page": "session" },
        "controls-audio": { "workspace": "controls", "page": "audio" },
        "controls-appearance": { "workspace": "controls", "page": "appearance" },
        "controls-networks": { "workspace": "controls", "page": "networks" },
        "controls-nitro": { "workspace": "controls", "page": "nitro" },
        "diagnostics-overview": { "workspace": "diagnostics", "page": "overview" },
        "diagnostics-isolation": { "workspace": "diagnostics", "page": "isolation" },
        "diagnostics-inventory": { "workspace": "diagnostics", "page": "inventory" },
        "diagnostics-session": { "workspace": "diagnostics", "page": "session" },
        "workbench": { "workspace": "workbench", "page": "candidates" },
        "devices": { "workspace": "devices", "page": "usb" },
        "launcher": { "launcher": "" },
        "clipboard": { "launcher": "clipboard" },
        "keys": { "launcher": "keys" },
        "panel": { "panel": "system" },
        "desktop": { "desktop": "idle" }
    })

    function routeAvailable(entry) {
        if (entry.workspace === undefined)
            return true;

        return ipc.shellSurfaces.validWorkspace(entry.workspace)
            && ipc.shellSurfaces.validSubpage(entry.workspace, entry.page);
    }

    // State-only, like a click inside the workspace: no raise is requested,
    // so the compositor is never asked to move focus or switch a slot.
    function enterRoute(entry) {
        if (entry.desktop !== undefined) {
            ipc.shellSurfaces.dismissAll();
            ipc.shellSurfaces.closeWorkspace();
        } else if (entry.panel !== undefined) {
            ipc.shellSurfaces.openSystemPanel("");
        } else if (entry.launcher !== undefined) {
            ipc.shellSurfaces.openLauncher("", entry.launcher);
        } else if (entry.form !== undefined) {
            ipc.shellSurfaces.openCreateForm();
        } else {
            ipc.shellSurfaces.openWorkspacePage(entry.workspace, entry.page, false);

            if (entry.workspace === "machines")
                ipc.shellSurfaces.closeCreateForm();
        }
    }

    function routeReached(entry) {
        if (entry.desktop !== undefined)
            return !ipc.shellSurfaces.workspaceOpen
                && !ipc.shellSurfaces.launcherOpen
                && !ipc.shellSurfaces.systemPanelOpen;

        if (entry.panel !== undefined)
            return ipc.shellSurfaces.systemPanelOpen;

        if (entry.launcher !== undefined)
            return ipc.shellSurfaces.launcherOpen
                && ipc.shellSurfaces.launcherMode === entry.launcher;

        return ipc.shellSurfaces.workspaceOpen
            && ipc.shellSurfaces.workspaceView === entry.workspace
            && ipc.shellSurfaces.subpage === entry.page;
    }

    Timer {
        id: appearanceRefreshDebounce

        interval: 120
        repeat: false

        onTriggered: {
            ipc.theme.refreshPalette();
            ipc.shellState.refreshAppearanceState();
        }
    }

    IpcHandler {
        target: "launcher"

        function toggle(): string {
            ipc.shellSurfaces.toggleLauncher("");
            return ipc.shellSurfaces.launcherOpen ? "open" : "closed";
        }

        function open(): string {
            ipc.shellSurfaces.openLauncher("");
            return "open";
        }

        function close(): string {
            ipc.shellSurfaces.closeLauncher();
            return "closed";
        }

        // SUPER + SHIFT + V: choose the one Machine that receives the host
        // clipboard (ADR 0020). Choosing is the only way to send.
        function clipboard(): string {
            ipc.shellSurfaces.openLauncher("", "clipboard");
            return "open";
        }

        // SUPER + F1: the host key sheet, read-only.
        function keys(): string {
            ipc.shellSurfaces.openLauncher("", "keys");
            return "open";
        }
    }

    IpcHandler {
        target: "appearance"

        function refresh(): string {
            appearanceRefreshDebounce.restart();
            return "queued";
        }
    }

    IpcHandler {
        target: "osd"

        // The OSD shows the host's state for the kind, never a caller value.
        function show(kind: string): string {
            if (!ipc.shellSurfaces.showOsd(kind, ""))
                return "refused";

            if (String(kind) === "audio")
                ipc.shellState.refreshTelemetry();

            return "shown";
        }
    }

    IpcHandler {
        target: "workspace"

        function sfere(): string {
            ipc.shellSurfaces.openWorkspace("sfere");
            return "sfere";
        }

        function machines(): string {
            ipc.shellSurfaces.openWorkspace("machines");
            return "machines";
        }

        function controls(): string {
            ipc.shellSurfaces.openWorkspace("controls");
            return "controls";
        }

        function diagnostics(): string {
            ipc.shellSurfaces.openWorkspace("diagnostics");
            return "diagnostics";
        }

        function workbench(): string {
            ipc.shellSurfaces.openWorkspace("workbench");
            return "workbench";
        }

        function devices(): string {
            ipc.shellSurfaces.openWorkspace("devices");
            return "devices";
        }

        function close(): string {
            ipc.shellSurfaces.closeWorkspace();
            return "closed";
        }
    }

    IpcHandler {
        target: "navigate"

        // Every route id, one per line, in the model's order.
        function routes(): string {
            return Object.keys(ipc.navigationRoutes).join("\n");
        }

        // Opens one section. Answers the route id when the coordinator shows
        // it, "unavailable" for a page that is switched off and "refused"
        // for anything else; a refusal changes nothing.
        function open(route: string): string {
            const name = String(route);

            if (!Object.prototype.hasOwnProperty.call(ipc.navigationRoutes, name))
                return "refused";

            const entry = ipc.navigationRoutes[name];

            if (!ipc.routeAvailable(entry))
                return "unavailable";

            ipc.enterRoute(entry);
            return ipc.routeReached(entry) ? name : "refused";
        }

        // Selects a Machine of the current inventory by its exact name and
        // shows it in Machines. Selecting is not acting: every operation
        // still goes through the Machine pane and its confirmation.
        function machine(name: string): string {
            const wanted = String(name);

            if (ipc.shellState.machineById(wanted) === null)
                return "refused";

            ipc.shellSurfaces.closeCreateForm();

            if (!ipc.shellSurfaces.selectMachine(
                    wanted, ipc.shellState.machinesGeneration, false))
                return "refused";

            return wanted;
        }

        // Where the shell is, so a caller can put it back: the open
        // workspace route (empty when closed), the open transient route,
        // the selected Machine and whether the rail is shown.
        function current(): string {
            const names = Object.keys(ipc.navigationRoutes);
            const workspace = names.filter(name => {
                const entry = ipc.navigationRoutes[name];

                return entry.workspace !== undefined && entry.form === undefined
                    && ipc.routeReached(entry);
            });
            const transient = names.filter(name => {
                const entry = ipc.navigationRoutes[name];

                return (entry.launcher !== undefined || entry.panel !== undefined)
                    && ipc.routeReached(entry);
            });

            return JSON.stringify({
                "workspace": workspace.length === 1 ? workspace[0] : "",
                "transient": transient.length === 1 ? transient[0] : "",
                "machine": ipc.shellSurfaces.workspaceOpen
                    ? ipc.shellSurfaces.selectedMachineId : "",
                "rail": ipc.shellSurfaces.topRailVisible ? "visible" : "hidden"
            });
        }
    }

    IpcHandler {
        target: "bar"

        function toggle(): string {
            ipc.shellSurfaces.toggleTopRail();
            return ipc.shellSurfaces.topRailVisible ? "visible" : "hidden";
        }

        function show(): string {
            ipc.shellSurfaces.showTopRail();
            return "visible";
        }

        function hide(): string {
            ipc.shellSurfaces.hideTopRail();
            return "hidden";
        }
    }

    // Sent by the shared lock helper on every lock path. It only withdraws
    // shell state; it cannot lock, unlock or run anything.
    IpcHandler {
        target: "session"

        function locking(): string {
            ipc.shellSurfaces.sessionLocking();
            return "dismissed";
        }
    }

    IpcHandler {
        target: "panel"

        function system(): string {
            ipc.shellSurfaces.toggleSystemPanel("");
            return ipc.shellSurfaces.systemPanelOpen ? "open" : "closed";
        }

        function dismiss(): string {
            ipc.shellSurfaces.dismissAll();
            return "closed";
        }
    }
}
