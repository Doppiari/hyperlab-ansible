// The Sfere view: the seal (ADR 0069, ADR 0064, ADR 0056).
//
// The host is the keystone at the centre; every network the network
// inventory lists is a glass sphere floating over its place on an engraved
// seal, joined to the host by one spoke from its own port, because Machines
// talk only through the host. Each mark is a fact the shell already holds:
//
//   sphere     a network of `net list`, in its palette colour and character;
//              an unknown network is neutral and calm
//   lit core   a managed Machine in that network runs (Machine inventory)
//   port       one per listed network; sealed, with a broken spoke, exactly
//              when the network is isolated
//   electron   a managed Machine attached to the network: bright when
//              running, hollow otherwise, on a dashed ring when disposable
//   heartbeat  one beat of the host's core per successful refresh of the
//              network inventory, the Machine inventory or GPU ownership;
//              when any of them is stale it stops, dims and says so
//   panel      the selected network's facts and its Machines' cards
//
// The live layer (ADR 0070) shows what is true now, and moves only for it:
//
//   orbit      a running Machine's electron travels its ring at one speed
//              for all; a stopped one stands still
//   trail      behind a running electron, as long as its CPU load (rated by
//              ShellState between two inventory polls); no reading, none
//   traffic    particles both ways on a whole spoke, more for more bytes per
//              second; none at rest, unknown or on a broken spoke
//   GPU beam   a dotted beam from the host to the electron of the Machine
//              GPU ownership names, with a token beside it; the token on the
//              host when the host holds it; nothing when unknown
//   focus      a wave round the network, and a ring round the electron, of
//              the Machine the provenance answer names; round the host when
//              the host has focus; none when focus is unrecognised
//   rule       a pulse network -> port -> host -> port -> network for each
//              rule ShellState declares between two listed networks (the
//              flow matrix declares none, so none is drawn on a real host)
//
// The rest is atmosphere (SealAmbient) and never carries state. One 33 ms
// timer drives every clock here and stops when nothing needs it.
//
// Presentation only. Selecting and entering a network are the only things
// the seal does; a card opens the existing Machine pane.

import QtQuick
import QtQuick.Shapes

Item {
    id: view

    objectName: "sfere-view"

    required property var tokens
    required property var theme
    required property var shellState
    required property var icons

    signal createRequested()
    signal machineRequested(string identifier)

    // ------------------------------------------------------------- facts

    // The network palette lookup and the character table, keyed by network
    // name. Both have the same keys; a network outside them is drawn in the
    // neutral colour with the calm character.
    readonly property var networkPalette: ({
        "clean": "dom_clean",
        "dev": "dom_dev",
        "services": "dom_services",
        "dirty": "dom_dirty",
        "lab": "dom_lab"
    })
    readonly property var networkCharacters: ({
        "clean": 1,
        "dev": 2,
        "services": 3,
        "dirty": 4,
        "lab": 5
    })
    readonly property int calmCharacter: 1

    function knownNetwork(name) {
        return Object.prototype.hasOwnProperty.call(view.networkPalette, name)
            && Object.prototype.hasOwnProperty.call(view.networkCharacters, name);
    }

    function networkColour(name) {
        const value = view.knownNetwork(name) ? view.theme.palette[view.networkPalette[name]] : undefined;

        return typeof value === "string" ? value : view.theme.textSecondary;
    }

    readonly property string networksStatus:
        view.shellState.networksViewEnabled ? view.shellState.networksStatus : "off"
    readonly property bool networksReady: view.networksStatus === "ready"

    readonly property bool inventoryAvailable: view.shellState.machinesAvailable
    // A Machine lights its network only while the inventory is current.
    readonly property bool machinesCurrent: view.inventoryAvailable
        && view.shellState.sourceState(view.shellState.machinesSourceState,
                                       view.shellState.machinesObservedAt) === "ok"
    readonly property var managed: view.inventoryAvailable ? view.shellState.machines : []

    readonly property var gpuOwnership: view.shellState.gpuOwnership
    readonly property bool gpuLent: view.gpuOwnership.known === true
        && String(view.gpuOwnership.owner).length > 0

    // Past this many Machines a network's last ring stands for the rest.
    readonly property int ringLimit: 8

    // Live facts. Load and traffic are empty unless the inventory is
    // current; a name without an entry has no reading.
    readonly property var loads: view.shellState.machineLoad
    readonly property var traffic: view.shellState.networkTraffic
    // The Machine GPU ownership names, "" when the host holds the GPU or
    // ownership is unknown; `gpuHome` only when it is known to be the host.
    readonly property string gpuHolder: view.gpuLent ? String(view.gpuOwnership.owner) : ""
    readonly property bool gpuHome: view.gpuOwnership.known === true && !view.gpuLent
    // Focus from the reviewed provenance answer only, never a window title.
    readonly property var focusAnswer: view.shellState.focusedMachine
    readonly property string focusName: view.focusAnswer.kind === "machine" ? String(view.focusAnswer.name) : ""
    readonly property bool hostFocused: view.focusAnswer.kind === "host"

    function own(object, key) {
        return object !== null && typeof object === "object" && Object.prototype.hasOwnProperty.call(object, key);
    }

    // A running Machine's load as a share of its vCPUs, or null.
    function loadOf(row) {
        const name = String(row.name);

        return view.machinesCurrent && view.running(row) && view.own(view.loads, name)
            ? view.loads[name] : null;
    }

    // A network's bytes per second, or -1 when there is no reading.
    function trafficOf(name) {
        return view.own(view.traffic, name) && typeof view.traffic[name] === "number"
            ? view.traffic[name] : -1;
    }

    function rateWords(rate) {
        if (rate < 0)
            return "unknown";

        if (rate === 0)
            return "none";

        const units = ["B/s", "kB/s", "MB/s", "GB/s"];
        let value = rate;
        let unit = 0;

        while (value >= 1000 && unit < units.length - 1) {
            value /= 1000;
            unit += 1;
        }

        return (value < 10 && unit > 0 ? value.toFixed(1) : String(Math.round(value))) + " " + units[unit];
    }

    // A Machine in words: state, load, the GPU, focus and lifecycle. The
    // same words read in its tooltip, its card and the hidden list.
    function machineFacts(row) {
        const name = String(row.name);
        const words = [String(row.state)];
        const load = view.loadOf(row);

        if (view.inventoryAvailable && !view.machinesCurrent)
            words[0] = "last observed " + words[0];

        if (view.machinesCurrent && view.running(row))
            words.push(load === null ? "load unavailable" : "load " + Math.round(load * 100) + "%");

        if (name === view.gpuHolder)
            words.push("holds the GPU");

        if (name === view.focusName)
            words.push("has focus");

        if (row.lifecycle === "disposable")
            words.push("disposable");

        return words;
    }

    // The Machines drawn on rings: the GPU holder and the focused Machine
    // first, so neither hides behind "+N", then running ones, then by name.
    function ringOrder(a, b) {
        const marked = row => String(row.name) === view.gpuHolder || String(row.name) === view.focusName ? 0 : 1;

        return marked(a) - marked(b) || view.byRunningThenName(a, b);
    }

    function attached(row, name) {
        return Array.isArray(row.networks) && row.networks.map(String).indexOf(name) >= 0;
    }

    function running(row) {
        return String(row.state) === "running";
    }

    function byRunningThenName(a, b) {
        return (view.running(a) ? 0 : 1) - (view.running(b) ? 0 : 1)
            || (String(a.name) < String(b.name) ? -1 : (String(a.name) > String(b.name) ? 1 : 0));
    }

    function modeWord(forward) {
        if (forward === "nat")
            return "NAT";

        if (forward === "isolated")
            return "Isolated";

        return forward === null || forward === undefined ? "mode unknown" : String(forward);
    }

    function title(name) {
        return name.length > 0 ? name.charAt(0).toUpperCase() + name.slice(1) : name;
    }

    // The words under a sphere: its Machines, then what isolates it.
    function stateWords(network) {
        let words;

        if (!view.inventoryAvailable)
            words = "machines unknown";
        else if (network.machines.length === 0)
            words = network.isolated ? "isolated · sealed" : "empty";
        else
            words = network.machines.length
                + (network.machines.length === 1 ? " machine · " : " machines · ")
                + (network.lit ? "lit: " + network.runningCount + " running"
                   : network.runningCount + " running")
                + (network.isolated ? " · isolated · sealed" : "");

        if (view.inventoryAvailable && !view.machinesCurrent && network.machines.length > 0)
            words += " · last observed";

        if (network.state === "inactive")
            words += " · inactive";
        else if (network.state === "missing")
            words += " · not defined in libvirt";

        return words;
    }

    // Every listed network, in the source's order, which is the seal's.
    readonly property var networks: {
        const rows = view.networksReady ? view.shellState.networksRows : [];
        const out = [];

        for (let index = 0; index < rows.length; index++) {
            const row = rows[index];
            const name = String(row.name);
            const machines = view.managed.filter(machine => view.attached(machine, name))
                .slice().sort(view.byRunningThenName);
            const runningCount = machines.filter(view.running).length;
            const rings = machines.length > view.ringLimit
                ? machines.slice().sort(view.ringOrder).slice(0, view.ringLimit - 1)
                : machines.slice().sort(view.ringOrder);
            const network = {
                "name": name,
                "title": view.title(name),
                "state": String(row.state),
                "subnet": row.subnet,
                "forward": row.forward,
                "gateway": row.gateway,
                "dhcp": row.dhcp,
                "isolated": row.forward === "isolated",
                "known": view.knownNetwork(name),
                "colour": view.networkColour(name),
                "character": view.knownNetwork(name) ? view.networkCharacters[name] : view.calmCharacter,
                "machines": machines,
                "runningCount": runningCount,
                "lit": view.machinesCurrent && runningCount > 0,
                "traffic": view.trafficOf(name),
                "rings": rings.map(machine => ({
                    "name": String(machine.name),
                    // Bright, and moving, only while the inventory is
                    // current: a stale observation is not a running Machine.
                    "running": view.machinesCurrent && view.running(machine),
                    "disposable": machine.lifecycle === "disposable",
                    "load": view.loadOf(machine),
                    "gpu": String(machine.name) === view.gpuHolder,
                    "focused": String(machine.name) === view.focusName,
                    "words": [String(machine.name), view.title(name), "address unknown"]
                        .concat(view.machineFacts(machine)).join(" · "),
                    "more": 0
                })).concat(machines.length > view.ringLimit
                    ? [{ "name": "", "running": false, "disposable": false, "load": null,
                         "gpu": false, "focused": false, "words": "",
                         "more": machines.length - rings.length }]
                    : [])
            };

            network.words = view.stateWords(network);
            out.push(network);
        }

        return out;
    }

    // Managed Machines on no listed network, and every unmanaged domain:
    // both outside the seal, never on a ring.
    readonly property var outside: {
        const out = [];

        if (view.networksReady) {
            for (const row of view.managed) {
                if (!view.networks.some(network => view.attached(row, network.name)))
                    out.push({ "name": String(row.name), "words": "managed · on no listed network" });
            }
        }

        for (const row of view.shellState.outsideDomains)
            out.push({ "name": String(row.name), "words": "not managed · outside the seal" });

        // GPU ownership may name a Machine with no electron: it says so here.
        for (const row of out) {
            if (row.name === view.gpuHolder)
                row.words += " · holds the GPU";
        }

        return out;
    }

    // ------------------------------------------------------- freshness

    readonly property var sources: view.shellState.sealSources
    readonly property bool fresh: view.sources.every(source => source.fresh)
    readonly property real lastRefresh:
        Math.max.apply(null, view.sources.map(source => source.at))

    function sourceWords(source) {
        if (source.state === "off")
            return source.name + " is off on this host";

        if (source.state === "loading" && source.at <= 0)
            return "reading " + source.name.toLowerCase();

        return source.name + " not answering";
    }

    readonly property string freshnessLine: {
        if (view.fresh)
            return "data current";

        const known = view.sources.filter(source => source.at > 0).map(source => source.at);
        const stale = view.sources.filter(source => !source.fresh).map(view.sourceWords);

        return (known.length > 0
                ? "data from " + view.shellState.observedText(Math.min.apply(null, known))
                : "no data yet")
            + " · " + stale.join(" · ");
    }

    // --------------------------------------------------------- selection

    // The network the keyboard is on, the one selected for the panel, the
    // one entered (or -1) and the Machine the keyboard is on inside it.
    property int cursor: 0
    property string selectedName: ""
    property int entered: -1
    property string machineCursor: ""

    readonly property int selectedIndex: {
        const index = view.networks.findIndex(network => network.name === view.selectedName);

        return index >= 0 ? index : (view.networks.length > 0 ? 0 : -1);
    }
    readonly property var selected: view.selectedIndex >= 0 ? view.networks[view.selectedIndex] : null
    readonly property bool zoomed: view.entered >= 0 && view.entered < view.networks.length

    onNetworksChanged: {
        if (view.cursor >= view.networks.length)
            view.cursor = Math.max(0, view.networks.length - 1);

        if (view.entered >= view.networks.length)
            view.leave();
    }

    function select(index) {
        if (index < 0 || index >= view.networks.length)
            return;

        view.cursor = index;
        view.selectedName = view.networks[index].name;
    }

    // Activation selects; a second activation of the selected network enters.
    function activateNetwork(index) {
        if (view.zoomed && index === view.entered) {
            if (view.machineCursor.length > 0)
                view.highlighted = view.machineCursor;

            return;
        }

        if (index === view.selectedIndex && !view.zoomed && view.selectedName.length > 0)
            view.enter(index);
        else
            view.select(index);
    }

    function enter(index) {
        if (index < 0 || index >= view.networks.length)
            return;

        view.select(index);
        view.entered = index;
        view.machineCursor = "";
        view.aim();
    }

    function leave() {
        view.entered = -1;
        view.machineCursor = "";
        view.aim();
    }

    property string highlighted: ""

    function moveNetwork(step) {
        const count = view.networks.length;

        if (count === 0)
            return;

        const next = (view.cursor + step + count) % count;
        const target = networkRepeater.itemAt(next);

        if (target)
            target.forceActiveFocus(Qt.TabFocusReason);

        view.cursor = next;
    }

    function moveMachine(step) {
        const machines = view.networks[view.entered].machines;

        if (machines.length === 0)
            return;

        const index = machines.findIndex(row => String(row.name) === view.machineCursor);
        const next = index < 0 ? (step > 0 ? 0 : machines.length - 1)
            : (index + step + machines.length) % machines.length;

        view.machineCursor = String(machines[next].name);
    }

    function stageKey(event) {
        const forward = event.key === Qt.Key_Right || event.key === Qt.Key_Down;
        const back = event.key === Qt.Key_Left || event.key === Qt.Key_Up;

        if (forward || back) {
            if (view.zoomed)
                view.moveMachine(forward ? 1 : -1);
            else
                view.moveNetwork(forward ? 1 : -1);

            event.accepted = true;
        } else if (event.key === Qt.Key_Plus && !view.zoomed) {
            view.enter(view.cursor);
            event.accepted = true;
        } else if (event.key === Qt.Key_Escape && view.zoomed) {
            view.leave();
            event.accepted = true;
        }
    }

    // ------------------------------------------------------------ clocks

    // Visible to the operator: this tab, in a shown window that is neither
    // hidden nor minimised.
    readonly property bool shown: view.visible && view.Window.window !== null
        && view.Window.window.visible
        && view.Window.visibility !== Window.Minimized
        && view.Window.visibility !== Window.Hidden
    readonly property bool reduced: view.tokens.reducedMotion
    readonly property bool ambientActive:
        view.shown && view.shellState.ambientMotion && !view.reduced
    readonly property bool coresMoving:
        view.shown && !view.reduced && view.networks.some(network => network.lit)
    readonly property real beatSeconds: 1.2
    property real beatDoneAt: 0
    readonly property bool beatPending:
        view.shown && !view.reduced && view.fresh && view.lastRefresh > view.beatDoneAt
    readonly property bool cameraMoving: view.shown && !view.reduced
        && Math.abs(view.camT - view.aimT) > 0.002
    // The live layer moves while something live is on the seal: a running
    // electron (and its trail and traffic), a focus wave or a rule pulse.
    readonly property bool liveMoving: view.shown && !view.reduced
        && (view.networks.some(network => network.rings.some(row => row.running))
            || view.focusNetwork >= 0 || view.hostFocused || view.pulses.length > 0)
    readonly property bool clockNeeded: view.ambientActive || view.coresMoving
        || view.liveMoving || view.beatPending || view.cameraMoving

    // Seconds the lit cores and the atmosphere have moved: each advances
    // only while it may.
    property real coreTime: 0
    property real ambientTime: 0
    // Seconds the live layer has moved, and the one speed of every running
    // electron, in radians per second: the motion means "running" and
    // nothing else, so no load or traffic enters it.
    property real liveTime: 0
    readonly property real orbitRate: 0.9
    property real beat: 0
    property real lastTick: 0

    // The sphere effects drop to half resolution while the RTX is lent to a
    // Machine (the host then draws on the integrated GPU) or once frames
    // keep missing their budget.
    readonly property int frameBudgetMs: 50
    property int slowFrames: 0
    property bool overBudget: false
    readonly property real textureScale: view.gpuLent || view.overBudget ? 0.5 : 1

    onShownChanged: {
        if (!view.shown) {
            view.overBudget = false;
            view.slowFrames = 0;
        }
        view.aim();
    }
    onReducedChanged: view.aim()

    function tick() {
        const now = Date.now();
        const step = view.lastTick > 0 ? (now - view.lastTick) : 0;

        if (step > 0 && step < 1000) {
            view.slowFrames = step > view.frameBudgetMs
                ? view.slowFrames + 1 : Math.max(0, view.slowFrames - 1);

            if (view.slowFrames >= 30)
                view.overBudget = true;
        }

        view.lastTick = now;
        const seconds = Math.min(0.1, step / 1000);

        if (view.coresMoving)
            view.coreTime += seconds;

        if (view.ambientActive)
            view.ambientTime += seconds;

        if (view.liveMoving)
            view.liveTime += seconds;

        view.updateBeat(now);

        if (view.cameraMoving) {
            view.camT += (view.aimT - view.camT) * 0.2;
        }
    }

    function updateBeat(now) {
        if (!view.fresh || view.reduced) {
            view.beat = 0;
            return;
        }

        const age = (now - view.lastRefresh) / 1000;

        if (age < 0 || age >= view.beatSeconds) {
            view.beat = 0;
            view.beatDoneAt = view.lastRefresh;
            return;
        }

        view.beat = Math.pow(Math.sin(Math.PI * age / view.beatSeconds), 2);
    }

    onFreshChanged: {
        if (!view.fresh)
            view.beat = 0;
    }

    // The host's light: a beat over a steady glow while every source is
    // fresh, dim and still when any is not.
    readonly property real hostLight: !view.fresh ? 0.12
        : (view.reduced ? 0.8 : 0.55 + 0.45 * view.beat)

    Timer {
        id: clock

        interval: 33
        repeat: true
        running: view.clockNeeded
        // A stopped clock leaves no beat half drawn.
        onRunningChanged: {
            if (!clock.running) {
                view.lastTick = 0;
                view.beat = 0;
            }
        }
        onTriggered: view.tick()
    }

    // ---------------------------------------------------------- geometry

    readonly property int headerHeight: view.tokens.spaceSection + view.tokens.spaceLg
    readonly property int panelHeight: Math.ceil(Math.min(view.height * 0.36,
        Math.max(view.tokens.cardHeight + view.tokens.spaceLg * 2,
                 panel.neededHeight + view.tokens.spaceSm)))

    readonly property real stageWidth: stage.width
    readonly property real stageHeight: stage.height

    // The seal on the floor, seen at a tilt, and the host above its centre.
    // `depthSpan` is the seal's half height on screen: the largest that
    // keeps the host's words, the far networks' words over their spheres and
    // the near networks' words under the engraving on the stage, measured
    // with the labels' real heights.
    readonly property real tilt: 0.36
    readonly property real networkWordsHeight: wordsProbe.height
    readonly property real hostWordsHeight: hostWords.height
    readonly property real minDepth: view.tokens.spaceSection
    readonly property real maxDepth: Math.max(view.minDepth, view.stageWidth * 0.33 * view.tilt)

    function hostRadiusFor(depth) {
        return Math.max(view.tokens.spaceHuge, Math.min(124, view.stageWidth / 11.5, depth * 0.62));
    }

    function sphereBaseFor(depth) {
        return Math.max(view.tokens.spaceLg, Math.min(
            54, view.stageWidth / 26, (depth * 0.3 + view.tokens.spaceXl) / 1.62 / 0.944));
    }

    // The seal at a depth, with the host's centre at 0: each network's place
    // on the floor and its sphere lifted above it, larger toward the front,
    // and how far up and down the drawing and its words reach.
    function sealAt(depth) {
        const count = view.networks.length;
        const lift = depth * 0.5;
        const floorOffset = lift * 1.6;
        const hostRadius = view.hostRadiusFor(depth);
        const base = view.sphereBaseFor(depth);
        const wordsLine = floorOffset + depth * 1.13 + view.tokens.spaceLg;
        const spots = [];
        let top = -hostRadius * 1.18 - view.hostWordsHeight;
        let bottom = floorOffset + depth * 1.15;

        for (let index = 0; index < count; index++) {
            const angle = Math.PI / 2 + index * 2 * Math.PI / count;
            const near = (Math.sin(angle) + 1) / 2;
            const scale = 0.82 + 0.24 * near;
            const floorPoint = floorOffset + Math.sin(angle) * depth;
            const y = floorPoint - lift * scale;
            const radius = base * scale * 1.12;
            const below = near > 0.75;
            const reach = radius * 1.62;

            spots.push({
                "angle": angle,
                "depth": near,
                "floorPoint": floorPoint,
                "y": y,
                "radius": radius,
                "below": below,
                "drop": below ? Math.max(reach + view.tokens.spaceXs, wordsLine - y) : 0
            });
            top = Math.min(top, y - reach
                - (below ? 0 : view.tokens.spaceXs + view.networkWordsHeight));
            bottom = Math.max(bottom, below
                ? y + Math.max(reach + view.tokens.spaceXs, wordsLine - y) + view.networkWordsHeight
                : y + reach);
        }

        return {
            "hostRadius": hostRadius,
            "base": base,
            "floorOffset": floorOffset,
            "spots": spots,
            "top": top,
            "bottom": bottom
        };
    }

    readonly property real depthSpan: {
        const fits = depth => {
            const seal = view.sealAt(depth);

            return seal.bottom - seal.top <= view.stageHeight - view.tokens.spaceXs * 2;
        };
        let low = view.minDepth;
        let high = view.maxDepth;

        if (fits(high))
            return high;

        for (let step = 0; step < 24; step++) {
            const middle = (low + high) / 2;

            if (fits(middle))
                low = middle;
            else
                high = middle;
        }

        return low;
    }
    readonly property var seal: view.sealAt(view.depthSpan)
    readonly property real sealRadius: view.depthSpan / view.tilt
    readonly property real sphereBase: view.seal.base
    readonly property real hostRadius: view.seal.hostRadius
    readonly property real centreX: view.stageWidth / 2
    readonly property real hostX: view.centreX
    // A margin of spaceXs on both sides absorbs the half pixels of centring.
    readonly property real hostY: -view.seal.top + view.tokens.spaceXs + Math.max(0,
        view.stageHeight - view.tokens.spaceXs * 2 - (view.seal.bottom - view.seal.top)) / 2
    readonly property real floorY: view.hostY + view.seal.floorOffset

    readonly property var places: view.seal.spots.map((spot, index) => {
        const x = view.centreX + Math.cos(spot.angle) * view.sealRadius;
        const y = view.hostY + spot.y;

        return {
            "name": view.networks[index].name,
            "angle": spot.angle,
            "depth": spot.depth,
            "floorX": x,
            "floorY": view.hostY + spot.floorPoint,
            "x": x,
            "y": y,
            "radius": spot.radius,
            "below": spot.below,
            "drop": spot.drop,
            "toward": Math.atan2(y - view.hostY, x - view.hostX),
            "front": Math.sin(spot.angle) > 0
        };
    })

    readonly property var floorPlaces: view.places.map((place, index) => ({
        "name": place.name,
        "x": place.floorX,
        "y": place.floorY,
        "angle": place.angle,
        "colour": view.networks[index].colour,
        "lit": view.networks[index].lit ? 1 : 0,
        "size": place.radius,
        "words": (view.networks[index].name + " · " + (view.networks[index].subnet || "subnet unknown")
                  + " · " + view.modeWord(view.networks[index].forward)).toUpperCase()
    }))

    readonly property var ports: view.places.map((place, index) => ({
        "name": place.name,
        "angle": place.toward,
        "sealed": view.networks[index].isolated,
        "colour": view.networks[index].colour,
        "lit": view.networks[index].lit ? 1 : 0
    }))

    // ----------------------------------------------------------- live marks

    // Where a network is on the seal, by name, or -1.
    function placeOf(name) {
        return view.networks.findIndex(network => network.name === name);
    }

    // The focused Machine's network: the one listed network whose rings
    // carry it, or -1. A Machine on no ring (outside the seal, or not in the
    // inventory) moves no wave.
    readonly property int focusNetwork: view.focusName.length === 0 ? -1
        : view.networks.findIndex(network => network.rings.some(row => row.focused))

    // The port on the host ring that a network's spoke leaves from.
    function portPoint(index) {
        const angle = view.places[index].toward;

        return Qt.point(view.hostX + Math.cos(angle) * keystone.ringRadius,
                        view.hostY + Math.sin(angle) * keystone.ringRadius);
    }

    // The electron of a Machine on the seal, in the scene, or null.
    function electronPoint(name) {
        for (let index = 0; index < view.networks.length; index++) {
            const ring = view.networks[index].rings.findIndex(row => row.name === name && !(row.more > 0));
            const slot = networkRepeater.count === view.networks.length ? networkRepeater.itemAt(index) : null;

            if (ring < 0 || slot === null)
                continue;

            // The control centres its content on whole pixels: map from the
            // sphere's own centre, read again whenever its place moves.
            if (!view.places[index])
                continue;

            const spot = slot.seal.electronAt(ring);
            const centre = slot.seal.mapToItem(scene, slot.seal.width / 2, slot.seal.height / 2);

            return Qt.point(centre.x + spot.x, centre.y + spot.y);
        }

        return null;
    }

    // The GPU beam's end: the holder's electron, or null when the host holds
    // the GPU, ownership is unknown or the holder is not on a ring.
    readonly property var beamEnd: view.gpuHolder.length > 0 && view.places.length === view.networks.length
        ? view.electronPoint(view.gpuHolder) : null

    // One pulse per declared rule whose two networks are listed, each with
    // its route through the host and its caption.
    readonly property var pulses: {
        const out = [];
        const rules = Array.isArray(view.shellState.networkRules) ? view.shellState.networkRules : [];

        if (view.places.length !== view.networks.length)
            return out;

        for (const rule of rules) {
            const from = view.placeOf(String(rule.from));
            const to = view.placeOf(String(rule.to));

            if (from < 0 || to < 0 || from === to)
                continue;

            out.push({
                "from": view.networks[from].name,
                "to": view.networks[to].name,
                "colours": [view.networks[from].colour, view.networks[to].colour],
                "route": [Qt.point(view.places[from].x, view.places[from].y), view.portPoint(from),
                          Qt.point(view.hostX, view.hostY), view.portPoint(to),
                          Qt.point(view.places[to].x, view.places[to].y)],
                "words": view.networks[from].name + " → " + view.networks[to].name + " · "
                    + String(rule.name) + " · via host"
            });
        }

        return out;
    }

    // Where a pulse is along its route at `share` (0..1) of the way.
    function routePoint(route, share) {
        const legs = route.length - 1;
        const along = Math.max(0, Math.min(legs - 1e-6, share * legs));
        const leg = Math.floor(along);
        const rest = along - leg;

        return Qt.point(route[leg].x + (route[leg + 1].x - route[leg].x) * rest,
                        route[leg].y + (route[leg + 1].y - route[leg].y) * rest);
    }

    // The camera: the whole seal, or one network entered. With reduced
    // motion, or when the view is not shown, it moves at once.
    // `camT` runs from 0 (the whole seal) to 1 (the network last entered);
    // the camera's centre and scale follow it, and the layout, by binding.
    readonly property real zoomScale: 2.1
    property int lastEntered: -1
    readonly property real aimT: view.zoomed ? 1 : 0
    property real camT: 0
    readonly property var zoomPlace: view.lastEntered >= 0 && view.lastEntered < view.places.length
        ? view.places[view.lastEntered] : null
    readonly property real camS: view.camT >= 1 ? view.zoomScale
        : 1 + (view.zoomScale - 1) * view.camT
    readonly property real camX: view.stageWidth / 2 + (view.zoomPlace === null ? 0
        : (view.zoomPlace.x + view.stageWidth * 0.1 / view.zoomScale - view.stageWidth / 2) * view.camT)
    readonly property real camY: view.stageHeight / 2 + (view.zoomPlace === null ? 0
        : (view.zoomPlace.y + view.tokens.spaceSm - view.stageHeight / 2) * view.camT)

    function aim() {
        if (view.zoomed)
            view.lastEntered = view.entered;

        if (view.reduced || !view.shown)
            view.camT = view.aimT;
    }

    // ------------------------------------------------------------- words

    readonly property string summaryLine: {
        const managedCount = view.managed.length;
        const runningCount = view.managed.filter(view.running).length;
        const external = view.shellState.outsideDomains.length;

        return view.networks.length + (view.networks.length === 1 ? " network · " : " networks · ")
            + (view.inventoryAvailable
               ? managedCount + (managedCount === 1 ? " machine · " : " machines · ")
                 + runningCount + " running"
               : "machines unknown")
            + (external > 0 ? " · " + external + " external" : "");
    }

    readonly property string absenceLine: {
        switch (view.networksStatus) {
        case "off":
            return "The network inventory is off on this host (the Networks view is not enabled), "
                + "so the seal draws no network.";
        case "loading":
            return "Reading declared networks.";
        case "empty":
            return "No declared networks.";
        case "stale":
            return "The network inventory is stale: no network is drawn.";
        case "ready":
            return "";
        default:
            return "The network inventory is not answering: no network is drawn.";
        }
    }

    function gatewayWords(value) {
        if (value === false)
            return "none";

        return typeof value === "string" ? value : "unknown";
    }

    function dhcpWords(value) {
        if (value === false)
            return "off";

        return value !== null && typeof value === "object" ? value.start + " – " + value.end : "unknown";
    }

    function levelWords(name) {
        const ladder = view.shellState.gpuLadder;

        return Object.prototype.hasOwnProperty.call(ladder, name) ? String(ladder[name]) : "none";
    }

    // The outbound rule in words, from the frozen flow matrix
    // (docs/network-flows.md).
    function ruleWords(forward) {
        if (forward === "nat")
            return "Out: the internet through the host (NAT). To other networks: no route. "
                + "To the host: DHCP and DNS on its own gateway only.";

        if (forward === "isolated")
            return "Isolated: no route out and no route to any other network; "
                + "DHCP and DNS on its own gateway only.";

        return "The outbound rule of this mode is not known.";
    }

    readonly property var detail: view.selected === null ? null : ({
        "title": view.selected.title,
        "colour": view.selected.colour,
        "subnet": view.selected.subnet || "subnet unknown",
        "summary": !view.inventoryAvailable ? "Machines unknown"
            : view.selected.machines.length === 0 ? "No machines"
            : view.selected.machines.length
              + (view.selected.machines.length === 1 ? " machine · " : " machines · ")
              + view.selected.runningCount + " running",
        "facts": [
            ["Gateway", view.gatewayWords(view.selected.gateway)],
            ["Mode", view.modeWord(view.selected.forward)],
            ["DHCP", view.dhcpWords(view.selected.dhcp)],
            ["GPU level", view.levelWords(view.selected.name)],
            ["Traffic", view.rateWords(view.selected.traffic)]
        ],
        "rule": view.ruleWords(view.selected.forward),
        // An unreadable inventory never reads as an empty network.
        "empty": !view.inventoryAvailable
            ? "Machines unknown: the Machine inventory cannot be read."
            : view.selected.isolated
            ? "This network is sealed and empty: no route out and no route to any other network."
            : "No Machines in this network."
    })

    function networkLine(network) {
        return network.title + ", " + network.words + ", " + view.modeWord(network.forward)
            + ", " + (network.subnet || "subnet unknown")
            + ", traffic " + view.rateWords(network.traffic)
            + (view.focusNetwork >= 0 && view.networks[view.focusNetwork] === network ? ", has focus" : "");
    }

    function machineLine(row, network) {
        return String(row.name) + ", " + network.title + " network, " + view.machineFacts(row).join(", ");
    }

    // Who holds the GPU, in words, from GPU ownership.
    readonly property string gpuLine: {
        if (view.gpuHome)
            return "holds the GPU";

        if (view.gpuHolder.length === 0)
            return "GPU holder unknown";

        return view.beamEnd !== null || view.managed.some(row => String(row.name) === view.gpuHolder
                                                               && view.networks.some(network => view.attached(row, network.name)))
            ? "GPU lent to " + view.gpuHolder
            : "GPU lent to " + view.gpuHolder + ", outside the seal";
    }

    readonly property string hostLine: "Host, every path passes here, " + view.gpuLine
        + (view.hostFocused ? ", has focus" : "") + ", " + view.freshnessLine

    // Each Machine's live words under its card.
    readonly property var cardNotes: {
        const out = {};

        for (const row of view.managed)
            out[String(row.name)] = view.machineFacts(row).join(" · ");

        return out;
    }

    // The same content as the picture, for a screen reader.
    readonly property var listLines: {
        const out = [view.hostLine];

        if (!view.networksReady) {
            out.push(view.absenceLine);

            for (const row of view.managed)
                out.push(String(row.name) + ", " + String(row.state) + ", network not shown");
        }

        for (const network of view.networks) {
            out.push(view.networkLine(network));

            for (const row of network.machines)
                out.push(view.machineLine(row, network));
        }

        for (const row of view.outside)
            out.push(row.name + ", " + row.words);

        return out;
    }

    // ------------------------------------------------------------ header

    Item {
        id: header

        x: view.tokens.workspacePadding
        width: view.width - view.tokens.workspacePadding * 2
        height: view.headerHeight

        Column {
            anchors.verticalCenter: parent.verticalCenter
            spacing: 2

            ShellLabel {
                objectName: "sfere-title"
                tokens: view.tokens
                role: "display"
                text: view.zoomed ? view.networks[view.entered].title : view.shellState.productName
                color: view.theme.textPrimary
            }

            ShellLabel {
                objectName: "sfere-summary"
                tokens: view.tokens
                role: "meta"
                text: view.zoomed
                    ? (view.networks[view.entered].subnet || "subnet unknown") + " · "
                      + view.modeWord(view.networks[view.entered].forward) + " · "
                      + view.networks[view.entered].words
                    : view.summaryLine
                color: view.theme.textSecondary
            }
        }

        ShellControl {
            id: headerAction

            objectName: view.zoomed ? "sfere-leave" : "sfere-enter"
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            visible: view.zoomed || view.selected !== null
            tokens: view.tokens
            theme: view.theme
            accessibleName: view.zoomed ? "← The whole seal"
                : (view.selected ? "Enter " + view.selected.title : "")

            content: [
                ShellLabel {
                    anchors.verticalCenter: parent.verticalCenter
                    tokens: view.tokens
                    role: "body"
                    text: headerAction.accessibleName
                    color: view.theme.textPrimary
                }
            ]

            onActivated: {
                if (view.zoomed)
                    view.leave();
                else
                    view.enter(view.selectedIndex);
            }
        }
    }

    // ------------------------------------------------------------- stage

    Item {
        id: stage

        objectName: "sfere-stage"
        y: view.headerHeight
        width: view.width
        height: view.height - view.headerHeight - view.panelHeight - view.tokens.spaceLg
        clip: true

        Item {
            id: scene

            objectName: "sfere-scene"
            width: stage.width
            height: stage.height
            transformOrigin: Item.TopLeft
            scale: view.camS
            x: stage.width / 2 - view.camX * view.camS
            y: stage.height / 2 - view.camY * view.camS

            SealFloor {
                objectName: "sfere-floor"
                anchors.fill: parent
                opacity: view.zoomed ? 0.5 : 1
                tokens: view.tokens
                theme: view.theme
                centreX: view.centreX
                floorY: view.floorY
                radius: view.sealRadius
                tilt: view.tilt
                places: view.floorPlaces
            }

            SealAmbient {
                objectName: "sfere-ambient"
                anchors.fill: parent
                tokens: view.tokens
                theme: view.theme
                active: view.ambientActive
                time: view.ambientTime
                centreX: view.centreX
                floorY: view.floorY
                radius: view.sealRadius
                tilt: view.tilt
                hostX: view.hostX
                hostY: view.hostY
                hostRadius: view.hostRadius
            }

            // A spoke from each network's own port to its sphere.
            Repeater {
                model: view.places

                SealSpoke {
                    required property var modelData
                    required property int index

                    readonly property var row: view.networks[index]
                    readonly property real portRadius: keystone.ringRadius
                    readonly property real reach: Math.hypot(modelData.x - view.hostX, modelData.y - view.hostY)

                    anchors.fill: parent
                    z: 1
                    opacity: view.zoomed && view.entered !== index ? 0.2 : 1
                    theme: view.theme
                    network: modelData.name
                    fromX: view.hostX + Math.cos(modelData.toward) * portRadius
                    fromY: view.hostY + Math.sin(modelData.toward) * portRadius
                    toX: view.hostX + Math.cos(modelData.toward) * Math.max(portRadius, reach - modelData.radius * 1.02)
                    toY: view.hostY + Math.sin(modelData.toward) * Math.max(portRadius, reach - modelData.radius * 1.02)
                    colour: row.colour
                    broken: row.isolated
                    selected: index === view.selectedIndex
                    lit: row.lit ? 1 : 0
                    traffic: row.traffic
                    time: view.liveTime
                    place: index
                }
            }

            HostKeystone {
                id: keystone

                objectName: "sfere-host"
                x: view.hostX - width / 2
                y: view.hostY - height / 2
                z: 2
                opacity: view.zoomed ? 0.3 : 1
                tokens: view.tokens
                theme: view.theme
                radius: view.hostRadius
                ports: view.ports
                beat: view.hostLight
                // The shell has no source for the host's name yet
                // (problems/sfere-seal-host-name-has-no-source.md): the
                // blades read only words true of every host.
                engravings: ["EVERY PATH PASSES", "HOST"]
                textureScale: view.textureScale
            }

            Column {
                id: hostWords

                objectName: "sfere-host-words"
                x: view.hostX - width / 2
                y: view.hostY - view.hostRadius * 1.18 - height
                z: 4
                opacity: view.zoomed ? 0.3 : 1
                spacing: 2

                ShellLabel {
                    anchors.horizontalCenter: parent.horizontalCenter
                    tokens: view.tokens
                    role: "section"
                    text: "Host"
                    color: view.theme.textPrimary
                }

                ShellLabel {
                    anchors.horizontalCenter: parent.horizontalCenter
                    tokens: view.tokens
                    role: "mono"
                    text: "every path passes here"
                    color: view.theme.textQuiet
                }

                ShellLabel {
                    objectName: "sfere-freshness"
                    anchors.horizontalCenter: parent.horizontalCenter
                    tokens: view.tokens
                    role: "mono"
                    text: view.freshnessLine
                    color: view.fresh ? view.theme.textQuiet : view.theme.semanticStatusColor("warn")
                }
            }

            // Every network: selected by a click or Enter, entered by a
            // second one, by + or by the header's button.
            Repeater {
                id: networkRepeater

                model: view.places

                ShellControl {
                    id: slot

                    required property var modelData
                    required property int index

                    readonly property var network: view.networks[slot.index]
                    readonly property Item seal: sealNetwork

                    objectName: "sfere-network-" + slot.modelData.name
                    x: slot.modelData.x - width / 2
                    y: slot.modelData.y - height / 2
                    z: slot.modelData.front ? 3 : 1
                    width: slot.modelData.radius * 2.2
                    height: width
                    flat: true
                    opacity: view.zoomed && view.entered !== slot.index ? 0.2 : 1
                    // One network takes Tab, the keyboard's; the focused one
                    // keeps it until focus leaves (Qt refuses otherwise).
                    activeFocusOnTab: slot.index === view.cursor || slot.activeFocus
                    tokens: view.tokens
                    theme: view.theme
                    accessibleName: view.networkLine(slot.network)
                    Accessible.description: view.zoomed && view.entered === slot.index
                        ? "Arrows move between its Machines; Escape returns to the whole seal"
                        : "Enter selects; Enter again enters this network"

                    content: [
                        Item {
                            width: 1
                            height: 1

                            SealNetwork {
                                id: sealNetwork

                                x: -width / 2
                                y: -height / 2
                                tokens: view.tokens
                                theme: view.theme
                                network: slot.network
                                place: slot.index
                                radius: slot.modelData.radius
                                time: view.coreTime
                                textureScale: view.textureScale
                                selected: slot.index === view.selectedIndex
                                machineCursor: view.zoomed && view.entered === slot.index
                                    ? view.machineCursor : ""
                                labelBelow: slot.modelData.below
                                labelDrop: slot.modelData.drop
                                liveTime: view.liveTime
                                orbitRate: view.orbitRate
                                focusWave: view.focusNetwork === slot.index
                            }
                        }
                    ]

                    onActivated: view.activateNetwork(slot.index)
                    onActiveFocusChanged: {
                        if (slot.activeFocus)
                            view.cursor = slot.index;
                    }
                    Keys.onPressed: event => view.stageKey(event)
                }
            }

            // The GPU beam: dotted, from the host's core to the electron of
            // the Machine holding the GPU.
            Shape {
                id: beam

                readonly property point from: Qt.point(view.hostX, view.hostY)
                readonly property point to: view.beamEnd === null ? beam.from : view.beamEnd

                objectName: "sfere-gpu-beam"
                anchors.fill: parent
                z: 5
                visible: view.beamEnd !== null
                opacity: view.zoomed ? 0.4 : 1
                antialiasing: true

                ShapePath {
                    objectName: "sfere-path-beam"
                    strokeColor: view.beamEnd === null ? view.theme.alpha(view.theme.textPrimary, 0)
                        : view.theme.alpha(view.theme.textPrimary, 0.85)
                    strokeWidth: 1.4
                    fillColor: view.theme.alpha(view.theme.textPrimary, 0)
                    strokeStyle: ShapePath.DashLine
                    dashPattern: [1, 4]
                    startX: beam.from.x
                    startY: beam.from.y

                    PathLine { x: beam.to.x; y: beam.to.y }
                }

                ShellLabel {
                    objectName: "sfere-gpu-beam-label"
                    x: beam.from.x + (beam.to.x - beam.from.x) * 0.62 + view.tokens.spaceSm
                    y: beam.from.y + (beam.to.y - beam.from.y) * 0.62 - height - 2
                    tokens: view.tokens
                    role: "label"
                    text: "GPU"
                    color: view.theme.textPrimary
                }
            }

            // The host holds the GPU: its token sits on the host.
            Rectangle {
                objectName: view.gpuHome ? "sfere-gpu-token-host" : ""
                visible: view.gpuHome
                x: view.hostX + view.hostRadius * 0.3 - width / 2
                y: view.hostY - view.hostRadius * 0.3 - height / 2
                z: 5
                width: 9
                height: 9
                rotation: 45
                color: view.theme.textPrimary
            }

            // The host has focus: two rings widen round its core.
            Repeater {
                model: view.hostFocused ? 2 : 0

                Rectangle {
                    required property int index

                    readonly property real phase: (view.liveTime * 0.55 + index * 0.5) % 1

                    objectName: "sfere-wave-host"
                    x: view.hostX - width / 2
                    y: view.hostY - height / 2
                    z: 5
                    width: view.hostRadius * 0.84 * (1.05 + phase * 1.6)
                    height: width
                    radius: width / 2
                    color: view.theme.alpha(view.theme.textPrimary, 0)
                    border.width: 1.5
                    border.color: view.theme.alpha(view.theme.textPrimary, (1 - phase) * 0.6 + 0.1)
                }
            }

            // Who holds the GPU and whether the host has focus, in words,
            // under the keystone: the far networks' words leave no room above.
            ShellLabel {
                id: hostLive

                objectName: "sfere-host-live"
                x: view.hostX - width / 2
                y: view.hostY + view.hostRadius + view.tokens.spaceXs
                z: 4
                opacity: view.zoomed ? 0.3 : 1
                tokens: view.tokens
                role: "mono"
                text: view.gpuLine + (view.hostFocused ? " · has focus" : "")
                color: view.theme.textQuiet
            }

            // A declared rule between two networks: a pulse along its route,
            // always through the host, and its caption under the host.
            Repeater {
                model: view.pulses

                Item {
                    id: pulse

                    required property var modelData
                    required property int index

                    // A still pulse stands on the first network's spoke.
                    readonly property real share: (0.15 + view.liveTime * 0.3) % 1
                    readonly property point at: view.routePoint(pulse.modelData.route, pulse.share)

                    objectName: "sfere-pulse-" + pulse.modelData.from + "-" + pulse.modelData.to
                    anchors.fill: parent
                    z: 6

                    Rectangle {
                        x: pulse.at.x - width / 2
                        y: pulse.at.y - height / 2
                        width: 7
                        height: 7
                        radius: 3.5
                        color: view.theme.textPrimary
                        border.width: 2
                        border.color: view.theme.alpha(
                            pulse.modelData.colours[pulse.share < 0.5 ? 0 : 1], 0.6)
                    }

                    Rectangle {
                        objectName: "sfere-rule-caption"
                        x: view.hostX - width / 2
                        y: hostLive.y + hostLive.height + view.tokens.spaceXs + pulse.index * (height + 4)
                        width: caption.width + view.tokens.spaceMd * 2
                        height: caption.height + view.tokens.spaceXs * 2
                        radius: view.tokens.radiusControl
                        color: view.theme.alpha(view.theme.base, 0.85)
                        border.width: 1
                        border.color: view.theme.alpha(view.theme.textSecondary, 0.4)

                        ShellLabel {
                            id: caption

                            anchors.centerIn: parent
                            tokens: view.tokens
                            role: "meta"
                            text: pulse.modelData.words
                            color: view.theme.textPrimary
                        }
                    }
                }
            }
        }

        // External and unplaced Machines, outside the seal, bottom left.
        Column {
            objectName: "sfere-outside"
            x: view.tokens.workspacePadding
            y: stage.height - height - view.tokens.spaceSm
            spacing: view.tokens.spaceXs
            visible: !view.zoomed

            Repeater {
                model: view.outside.length > 4 ? view.outside.slice(0, 3) : view.outside

                Row {
                    required property var modelData

                    spacing: view.tokens.spaceSm

                    // The dashed mark of something the seal does not manage.
                    Shape {
                        anchors.verticalCenter: parent.verticalCenter
                        width: view.tokens.spaceLg
                        height: view.tokens.spaceLg
                        antialiasing: true

                        ShapePath {
                            strokeColor: view.theme.textSecondary
                            strokeWidth: 1.3
                            fillColor: view.theme.alpha(view.theme.textSecondary, 0)
                            strokeStyle: ShapePath.DashLine
                            dashPattern: [2, 3]

                            PathAngleArc {
                                centerX: view.tokens.spaceLg / 2; centerY: view.tokens.spaceLg / 2
                                radiusX: view.tokens.spaceLg / 2 - 1; radiusY: view.tokens.spaceLg / 2 - 1
                                startAngle: 0; sweepAngle: 360
                            }
                        }
                    }

                    ShellLabel {
                        tokens: view.tokens
                        role: "meta"
                        text: modelData.name + " · " + modelData.words
                        color: view.theme.textSecondary
                    }
                }
            }

            ShellLabel {
                visible: view.outside.length > 4
                tokens: view.tokens
                role: "meta"
                text: "+" + (view.outside.length - 3) + " more outside the seal"
                color: view.theme.textSecondary
            }
        }

        ShellLabel {
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: view.tokens.spaceSm
            tokens: view.tokens
            role: "meta"
            text: "Click: details · click again: enter · Esc: back"
            color: view.theme.textQuiet
        }

        // A network inventory that cannot be read never looks like an empty one.
        ShellLabel {
            objectName: "sfere-absence"
            x: view.tokens.workspacePadding
            y: view.tokens.spaceSm
            width: Math.min(view.tokens.dialogWidth, stage.width / 3)
            visible: !view.networksReady
            tokens: view.tokens
            role: "body"
            wrapMode: Text.Wrap
            text: view.absenceLine
            color: view.theme.textSecondary
        }

        EmptyState {
            objectName: "sfere-unavailable"
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: view.tokens.spaceSm
            width: Math.min(view.tokens.dialogWidth, stage.width / 3)
            visible: !view.inventoryAvailable
            tokens: view.tokens
            theme: view.theme
            kind: "unavailable"
            title: "Machine inventory cannot be read"
            description:
                "The host inventory source did not answer. "
                + "Diagnostics has the observation detail."
        }
    }

    // ------------------------------------------------------------- panel

    SealPanel {
        id: panel

        x: view.tokens.workspacePadding
        y: view.height - view.panelHeight
        width: view.width - view.tokens.workspacePadding * 2
        height: view.panelHeight - view.tokens.spaceSm
        tokens: view.tokens
        theme: view.theme
        icons: view.icons
        detail: view.detail
        // With no network to show, every managed Machine is still one card
        // away: the panel lists them all.
        machines: view.selected ? view.selected.machines : (view.networksReady ? [] : view.managed)
        highlighted: view.zoomed && view.machineCursor.length > 0 ? view.machineCursor : view.highlighted
        notes: view.cardNotes
        absence: view.absenceLine
        offerCreate: view.inventoryAvailable && view.managed.length === 0
            && view.shellState.outsideDomainsAvailable

        onMachineRequested: identifier => view.machineRequested(identifier)
        onCreateRequested: view.createRequested()
    }

    // A network's two lines of words, never shown: the layout measures them.
    Column {
        id: wordsProbe

        opacity: 0
        enabled: false
        spacing: 2
        Accessible.ignored: true

        ShellLabel {
            tokens: view.tokens
            role: "section"
            text: "Network"
        }

        ShellLabel {
            tokens: view.tokens
            role: "meta"
            text: "machines"
        }
    }

    // The same content as a list, for a screen reader. It draws nothing.
    Item {
        objectName: "sfere-list"
        width: 1
        height: 1

        Accessible.role: Accessible.List
        Accessible.name: "The host, its networks and their Machines"

        Repeater {
            model: view.listLines

            delegate: Item {
                required property string modelData

                width: 1
                height: 1

                Accessible.role: Accessible.ListItem
                Accessible.name: modelData
            }
        }
    }
}
