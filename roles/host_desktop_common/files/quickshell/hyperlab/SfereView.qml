// The Sfere view (ADR 0064, ADR 0067).
//
// The whole system in one picture: the host at the centre, every Machine a
// sphere around it. Each mark is a fact the shell already holds:
//
//   orbit      inner while the Machine runs, outer otherwise; never the domain
//   sector     the domain, in palette order, external domains last
//   link       a network the Machine is attached to, declared as NAT and
//              reported active by the Networks read; nothing else draws one
//   GPU token  the current answer of the GPU ownership source
//   reboot     the levels above the boot claim, from the trust claim
//
// Distance from the host carries no meaning. The centre is the HOST grey and
// never takes a Machine's colour. The layout has no drift. Only a reported
// transition can move the shared sphere's arc, which honours reduced motion.
//
// Presentation only. A sphere opens the existing Machine pane; the view
// reads nothing from the host itself and runs nothing.

import QtQuick
import QtQuick.Shapes

Item {
    id: view

    objectName: "sfere-view"

    required property var tokens
    required property var theme
    required property var shellState

    // The existing Create view lives in Machines; the window host opens it.
    signal createRequested()
    signal machineRequested(string identifier)

    // ------------------------------------------------------------- facts

    readonly property bool inventoryAvailable: view.shellState.machinesAvailable

    readonly property var sectorOrder:
        view.shellState.provenanceOrder.concat(["external"])

    // Past this many spheres the largest sectors collapse into counts.
    readonly property int legibleSpheres: 24

    // GPU ownership, only while the source is current. An empty owner in a
    // known reading means no Machine holds it: the GPU is on the host.
    readonly property var ownership: view.shellState.gpuOwnership
    readonly property bool gpuKnown: view.ownership.known === true
    readonly property string gpuOwner:
        view.gpuKnown ? String(view.ownership.owner) : ""
    readonly property bool gpuOnHost: view.gpuKnown && view.gpuOwner.length === 0

    // The boot claim. A claim that was seen stays a restriction when a later
    // read fails; it is then qualified as last seen, never dropped.
    readonly property var claim: view.shellState.trustClaim
    readonly property string claimState: view.shellState.trustClaimState
    readonly property bool claimCurrent: view.claimState === "ok"
    readonly property bool claimed: view.claim.claimed === true

    // The Networks read is opt-in. Without a current answer no link exists.
    readonly property string networksStatus:
        view.shellState.networksViewEnabled
        ? view.shellState.networksStatus
        : "off"

    // The networks that declare a path through the host: NAT forwarding in
    // the repository and an active libvirt network. An isolated network, an
    // unknown forwarding word, an inactive or a missing network declare none.
    readonly property var paths: {
        const out = [];

        if (view.networksStatus !== "ready")
            return out;

        const rows = view.shellState.networksRows;

        for (let index = 0; index < rows.length; index++) {
            if (rows[index].forward === "nat" && rows[index].state === "active")
                out.push(String(rows[index].name));
        }

        return out;
    }

    function needsReboot(sector) {
        const ladder = view.shellState.gpuLadder;

        return view.claimed
            && ladder.hasOwnProperty(sector)
            && ladder[sector] > view.claim.level;
    }

    function memberPath(networks) {
        for (let index = 0; index < networks.length; index++) {
            if (view.paths.indexOf(networks[index]) >= 0)
                return networks[index];
        }

        return "";
    }

    // The network that links an entry to the host, or "". An external
    // domain follows the same rule as a Machine: the attachment it reports.
    // A count sphere is linked only when every Machine it stands for is.
    function pathFor(entry) {
        if (entry.kind === "machine" || entry.kind === "external")
            return view.memberPath(entry.networks);

        if (entry.kind !== "group")
            return "";

        let name = "";

        for (let index = 0; index < entry.members.length; index++) {
            const path = view.memberPath(entry.members[index].networks);

            if (path.length === 0)
                return "";

            if (name.length === 0)
                name = path;
            else if (name !== path)
                return "";
        }

        return name;
    }

    function inner(entry) {
        return entry.observed === "running";
    }

    // Every registry Machine and every other observed domain, once. View
    // keys are separate from backend identifiers, so a sector count cannot
    // shadow a Machine named group-clean.
    readonly property var members: {
        const out = [];
        const machines = view.shellState.machines;

        for (let index = 0; index < machines.length; index++) {
            const row = machines[index];

            out.push({
                "id": String(row.name),
                "key": "machine:" + String(row.name),
                "kind": "machine",
                "name": String(row.name),
                "sector": String(row.provenance),
                "domain": String(row.provenance),
                "sphereState": String(row.state),
                "observed": String(row.state),
                "disposable": row.lifecycle === "disposable",
                "networks": Array.isArray(row.networks) ? row.networks.map(String) : [],
                "count": 1
            });
        }

        const outside = view.shellState.outsideDomains;

        for (let index = 0; index < outside.length; index++) {
            out.push({
                "id": String(outside[index].name),
                "key": "external:" + String(outside[index].name),
                "kind": "external",
                "name": String(outside[index].name),
                "sector": "external",
                "domain": "unclassified",
                "sphereState": view.inventoryAvailable ? "external" : "unclassified",
                "observed": String(outside[index].state),
                "disposable": false,
                "networks": Array.isArray(outside[index].networks)
                    ? outside[index].networks.map(String) : [],
                "count": 1
            });
        }

        return out;
    }

    // A crowded sector collapses into one count per orbit, so a count sits
    // only on the orbit all its Machines are on. Preserve the current GPU
    // owner; a count never claims a state or lifecycle its members do not
    // share.
    function collapse(rows) {
        const out = rows.filter(row => view.gpuOwner.length > 0 && row.id === view.gpuOwner);
        const rest = rows.filter(row => out.indexOf(row) < 0);
        const orbits = ["inner", "outer"];

        for (let orbit = 0; orbit < orbits.length; orbit++) {
            const group = rest.filter(row => view.inner(row) === (orbits[orbit] === "inner"));

            if (group.length < 2) {
                for (let index = 0; index < group.length; index++)
                    out.push(group[index]);

                continue;
            }

            const sameState = group.every(row => row.observed === group[0].observed);
            out.push({
                "id": "group-" + group[0].sector + "-" + orbits[orbit],
                "key": "group:" + group[0].sector + ":" + orbits[orbit],
                "kind": "group",
                "name": group.length + " Machines",
                "sector": group[0].sector,
                "domain": group[0].domain,
                "sphereState": sameState ? group[0].sphereState : "unclassified",
                "observed": sameState ? group[0].observed : "mixed states",
                "disposable": group.every(row => row.disposable),
                "networks": [],
                "members": group,
                "count": group.length
            });
        }

        return out;
    }

    // What is drawn, in sector order: running first, then by name. The
    // layout keeps each orbit in this order; the arrow keys follow the
    // angles it gives, around the ring.
    readonly property var entries: {
        const order = view.sectorOrder;
        const bySector = {};

        for (let index = 0; index < view.members.length; index++) {
            const row = view.members[index];

            if (bySector[row.sector] === undefined)
                bySector[row.sector] = [];

            bySector[row.sector].push(row);
        }

        const present = order.filter(sector => bySector[sector] !== undefined);
        const collapsed = {};
        let total = view.members.length;

        if (total > view.legibleSpheres) {
            const largest = present.slice().sort(
                (a, b) => bySector[b].length - bySector[a].length
                    || order.indexOf(a) - order.indexOf(b));

            for (let index = 0; index < largest.length; index++) {
                if (total <= view.legibleSpheres)
                    break;

                const rows = bySector[largest[index]];
                const groups = view.collapse(rows);

                if (groups.length >= rows.length)
                    continue;

                total += groups.length - rows.length;
                collapsed[largest[index]] = groups;
            }
        }

        const out = [];

        for (let index = 0; index < present.length; index++) {
            const rows = (collapsed[present[index]] || bySector[present[index]]).slice();

            rows.sort((a, b) =>
                (view.inner(a) ? 0 : 1) - (view.inner(b) ? 0 : 1)
                || (a.id < b.id ? -1 : (a.id > b.id ? 1 : 0)));

            for (let row = 0; row < rows.length; row++)
                out.push(rows[row]);
        }

        return out;
    }

    // ------------------------------------------------------------ layout

    // One empty slot between sectors, so a sector reads as a group.
    readonly property real sectorGap: 1

    // Sectors take a share of the turn by the number of spheres they hold.
    // Every sphere has its own angle: a link runs from its sphere straight
    // to the host, so no other sphere may stand on that ray, or the line
    // would seem to join two Machines. Inside a sector the running Machines
    // are spread evenly among the angles and the others take the rest.
    readonly property var layout: {
        const sectors = [];
        const known = {};

        for (let index = 0; index < view.entries.length; index++) {
            const entry = view.entries[index];

            if (known[entry.sector] === undefined) {
                known[entry.sector] = sectors.length;
                sectors.push({ "id": entry.sector, "inner": [], "outer": [] });
            }

            const sector = sectors[known[entry.sector]];

            (view.inner(entry) ? sector.inner : sector.outer).push(entry);
        }

        let weight = 0;

        for (let index = 0; index < sectors.length; index++) {
            sectors[index].slots = Math.max(
                1, sectors[index].inner.length + sectors[index].outer.length);
            weight += sectors[index].slots + view.sectorGap;
        }

        const slots = [];
        const words = [];
        let cursor = 0;

        for (let index = 0; index < sectors.length; index++) {
            const sector = sectors[index];
            const start = cursor + view.sectorGap / 2;
            const running = sector.inner.length;
            const total = running + sector.outer.length;
            let inner = 0;
            let outer = 0;

            for (let angle = 0; angle < total; angle++) {
                const takeInner = Math.floor((angle + 1) * running / total)
                    > Math.floor(angle * running / total);

                slots.push({
                    "entry": takeInner ? sector.inner[inner++] : sector.outer[outer++],
                    "orbit": takeInner ? "inner" : "outer",
                    "fraction": (start + angle + 0.5) / weight
                });
            }

            words.push({
                "id": sector.id,
                "fraction": (start + sector.slots / 2) / weight
            });

            cursor += sector.slots + view.sectorGap;
        }

        return { "slots": slots, "sectors": words, "weight": weight };
    }

    // The drawn model changes only when the layout does, so an identical
    // inventory poll never rebuilds the spheres under the pointer or the
    // keyboard focus.
    property var slots: []
    property var sectors: []
    property real layoutWeight: 0
    property string layoutKey: ""

    function adoptLayout() {
        const key = JSON.stringify(view.layout);

        if (key === view.layoutKey)
            return;

        view.layoutKey = key;
        view.layoutWeight = view.layout.weight;
        view.slots = view.layout.slots;
        view.sectors = view.layout.sectors;
    }

    onLayoutChanged: view.adoptLayout()
    Component.onCompleted: view.adoptLayout()

    // ---------------------------------------------------------- geometry

    // The orbits are circles seen at an angle: one ratio for both.
    readonly property real tilt: 0.42
    readonly property real innerRatio: 0.68

    // Room for the sector words beside the outer orbit, for the words above
    // it, and for the readout and the legend below it.
    readonly property int marginSide: view.tokens.navigationWidth
    readonly property int marginTop: view.tokens.spaceSection + view.tokens.spaceXxl
    readonly property int marginBottom:
        view.tokens.spaceSection * 2 + view.tokens.spaceXl

    // The sphere's marks are promised from 32 units (ADR 0064).
    readonly property int sphereMin: view.tokens.spaceHuge
    readonly property int sphereMax: view.tokens.spaceSection + view.tokens.spaceLg
    readonly property int orbitMin: 260

    // Cumulative length along the tilted orbit, from the top, clockwise.
    // Spheres are spaced by length, so they do not bunch at the sides.
    readonly property int arcSteps: 360
    readonly property var arcTable: {
        const table = [0];
        let length = 0;
        let lastX = 0;
        let lastY = -view.tilt;

        for (let step = 1; step <= view.arcSteps; step++) {
            const angle = -Math.PI / 2 + step * 2 * Math.PI / view.arcSteps;
            const x = Math.cos(angle);
            const y = view.tilt * Math.sin(angle);

            length += Math.hypot(x - lastX, y - lastY);
            table.push(length);
            lastX = x;
            lastY = y;
        }

        return table;
    }
    readonly property real unitPerimeter: view.arcTable[view.arcSteps]

    function angleAt(fraction) {
        const table = view.arcTable;
        const wanted = (fraction - Math.floor(fraction)) * view.unitPerimeter;
        let low = 0;
        let high = view.arcSteps;

        while (high - low > 1) {
            const middle = Math.floor((low + high) / 2);

            if (table[middle] <= wanted)
                low = middle;
            else
                high = middle;
        }

        const part = (wanted - table[low]) / (table[high] - table[low]);

        return -Math.PI / 2 + (low + part) * 2 * Math.PI / view.arcSteps;
    }

    readonly property real weight: Math.max(view.layoutWeight, 8)

    readonly property real fitOuter: Math.min(
        (view.width - view.marginSide * 2) / 2,
        (scroll.height - view.marginTop - view.marginBottom) / 2 / view.tilt)

    // The smallest orbit on which every sphere keeps its own slot. A window
    // too small for it scrolls; the spheres never overlap instead.
    readonly property real neededOuter: Math.max(
        view.weight * (view.sphereMin + view.tokens.spaceMd)
            / view.unitPerimeter / view.innerRatio,
        (view.sphereMin + view.tokens.spaceSm) / (view.tilt * (1 - view.innerRatio)))

    readonly property real orbitOuter:
        Math.max(view.fitOuter, view.neededOuter, view.orbitMin)
    readonly property real orbitInner: view.orbitOuter * view.innerRatio

    // The one place an orbit radius is chosen: by the orbit, nothing else.
    function orbitRadius(orbit) {
        return orbit === "inner" ? view.orbitInner : view.orbitOuter;
    }

    // How far a ray from the origin along (dx, dy) runs before it leaves the
    // box, or 0 when it never enters it. A link starts and ends outside the
    // words it would otherwise strike through.
    function leave(x, y, width, height, dx, dy) {
        let low = 0;
        let high = Infinity;
        const spans = [[x, width, dx], [y, height, dy]];

        for (let index = 0; index < spans.length; index++) {
            const start = spans[index][0];
            const end = start + spans[index][1];
            const step = spans[index][2];

            if (Math.abs(step) < 1e-9) {
                if (start > 0 || end < 0)
                    return 0;

                continue;
            }

            const a = start / step;
            const b = end / step;

            low = Math.max(low, Math.min(a, b));
            high = Math.min(high, Math.max(a, b));
        }

        return high >= low ? high : 0;
    }

    readonly property real sceneWidth:
        Math.max(view.width, view.orbitOuter * 2 + view.marginSide * 2)
    readonly property real sceneHeight: Math.max(
        scroll.height,
        view.orbitOuter * view.tilt * 2 + view.marginTop + view.marginBottom)

    readonly property real centreX: view.sceneWidth / 2
    readonly property real centreY:
        view.marginTop
        + (view.sceneHeight - view.marginTop - view.marginBottom) / 2

    readonly property real slotArc:
        view.orbitInner * view.unitPerimeter / view.weight

    readonly property int sphereSize: Math.max(
        view.sphereMin,
        Math.min(view.sphereMax, Math.floor(view.slotArc * 0.62),
            Math.floor(view.orbitOuter * view.tilt * (1 - view.innerRatio) - view.tokens.spaceSm)))

    // The emblem and its word stay inside the inner orbit, so no sphere
    // passes behind it and a link from below still has room to be seen.
    readonly property int hostSize: Math.max(
        view.tokens.spaceSection,
        Math.min(320, Math.floor(
            (view.orbitInner * view.tilt - view.sphereSize / 2 - view.tokens.spaceHuge
                - hostWord.height - view.tokens.spaceXs)
            * 2 / (host.radiusRatio * 2))))
    readonly property real hostRadius: view.hostSize * host.radiusRatio

    readonly property bool namesVisible:
        view.slotArc >= 80 && view.sphereSize >= 40

    // ------------------------------------------------------------- words

    function domainWord(entry) {
        if (entry.kind === "external" || entry.sector === "external")
            return view.inventoryAvailable ? "external" : "membership unknown";

        return view.theme.provenanceAvailable ? entry.domain : "unclassified";
    }

    function sectorWord(sector) {
        if (sector === "external")
            return view.inventoryAvailable ? "External" : "Membership unknown";

        return view.theme.provenanceLabel(sector);
    }

    function rebootWords() {
        return view.claimCurrent ? "GPU needs a reboot" : "GPU needs a reboot, last seen";
    }

    // What one sphere says, as the parts of one sentence.
    function partsFor(entry) {
        const parts = [
            entry.name,
            view.domainWord(entry),
            entry.observed.length > 0 ? entry.observed : "unknown"
        ];

        const observedAt = entry.kind === "external"
            ? view.shellState.outsideDomainsObservedAt : view.shellState.machinesObservedAt;
        if (view.shellState.sourceState("ok", observedAt) === "stale")
            parts.push("last observed");

        if (entry.disposable)
            parts.push("disposable");

        if (entry.kind !== "group" && view.gpuOwner.length > 0
            && entry.id === view.gpuOwner)
            parts.push("owns the GPU");

        if (view.networksStatus === "ready") {
            const path = view.pathFor(entry);

            parts.push(path.length === 0
                ? "no network link"
                : (entry.kind === "group" ? "network link" : "network link on " + path));
        }

        if (view.needsReboot(entry.sector))
            parts.push(view.rebootWords());

        return parts;
    }

    readonly property string hostLine:
        view.gpuOnHost ? "Host, holds the GPU" : "Host"

    // The same content as the picture, for a screen reader.
    readonly property var listLines: [view.hostLine].concat(
        view.members.slice().sort((a, b) =>
            view.sectorOrder.indexOf(a.sector) - view.sectorOrder.indexOf(b.sector)
            || (view.inner(a) ? 0 : 1) - (view.inner(b) ? 0 : 1)
            || (a.id < b.id ? -1 : (a.id > b.id ? 1 : 0)))
        .map(entry => view.partsFor(entry).join(", ")))

    property string readoutId: ""

    readonly property string readoutText: {
        for (let index = 0; index < view.entries.length; index++) {
            if (view.entries[index].key === view.readoutId)
                return view.partsFor(view.entries[index]).join(" · ");
        }

        const inventoryState = view.shellState.sourceState(
            view.shellState.machinesSourceState, view.shellState.machinesObservedAt);
        return (inventoryState === "stale" ? "Machine inventory last observed · " : "")
            + (view.inventoryAvailable ? "" : "Product inventory unavailable · ")
            + view.shellState.runningMachinesSummary;
    }

    readonly property string gpuLine: {
        if (!view.gpuKnown)
            return "GPU ownership unknown";

        if (view.gpuOnHost)
            return "GPU · on the host";

        return "GPU · " + view.gpuOwner
            + (view.members.some(row => row.id === view.gpuOwner)
                ? "" : " · not in this view");
    }

    readonly property string claimLine: {
        const word = view.claimed
            ? view.theme.provenanceLabel(view.claim.identity) + " " + view.claim.level
            : "";

        if (view.claimCurrent) {
            if (!view.claimed)
                return "No boot claim · every GPU level is still reachable";

            const ladder = view.shellState.gpuLadder;
            const above = Object.keys(ladder)
                .filter(name => ladder[name] > view.claim.level)
                .sort((a, b) => ladder[b] - ladder[a])
                .map(name => view.theme.provenanceLabel(name));

            return "Boot claim · " + word
                + (above.length > 0
                    ? " · " + above.join(", ") + " "
                        + (above.length > 1 ? "need" : "needs") + " a reboot"
                    : "");
        }

        if (view.claimState === "loading")
            return "Reading the boot claim";

        return view.claimed ? "Boot claim · " + word + " last seen" : "Boot claim unknown";
    }

    readonly property string linksLine: {
        switch (view.networksStatus) {
        case "off":
            return "Network links are not shown: the Networks view is off on this host";
        case "loading":
            return "Reading declared networks";
        case "empty":
            return "No declared networks";
        case "stale":
            return "Networks observation is stale: no link is drawn";
        case "ready":
            return "A link is a declared NAT network that libvirt reports active, "
                + "not proof of reachability";
        default:
            return "Networks unavailable: no link is drawn";
        }
    }

    // ------------------------------------------------------- interaction

    function open(entry) {
        // Only registry Machines have an operational pane; an external or
        // counted sphere asks for the existing read-only inventory instead.
        view.machineRequested(entry.kind === "machine" ? entry.id : "");
    }

    function moveFocus(index, step) {
        const count = slotRepeater.count;

        if (count === 0)
            return;

        const target = slotRepeater.itemAt((index + step + count) % count);

        if (target)
            target.forceActiveFocus(Qt.TabFocusReason);
    }

    // A new hover or keyboard focus speaks immediately. When either leaves,
    // fall back to the focused sphere, then the one under a parked pointer.
    function noteReadout() {
        let focused = "";
        let hovered = "";

        for (let index = 0; index < slotRepeater.count; index++) {
            const item = slotRepeater.itemAt(index);

            if (!item)
                continue;

            if (item.hovered)
                hovered = item.entry.key;

            if (item.activeFocus)
                focused = item.entry.key;
        }

        view.readoutId = focused.length > 0 ? focused : hovered;
    }

    onSlotsChanged: view.noteReadout()

    // ------------------------------------------------------------- scene

    Flickable {
        id: scroll

        anchors.fill: parent
        anchors.bottomMargin: legend.height + view.tokens.workspacePadding * 2
        contentWidth: view.sceneWidth
        contentHeight: view.sceneHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Item {
            id: scene

            width: view.sceneWidth
            height: view.sceneHeight

            // The orbits. The half behind the host is quieter than the half
            // in front; the outer orbit, where nothing runs, is dashed.
            Shape {
                objectName: "sfere-orbits"
                visible: view.members.length > 0
                anchors.fill: parent
                antialiasing: true

                ShapePath {
                    strokeColor: view.theme.hairline
                    strokeWidth: view.tokens.borderSize
                    fillColor: view.theme.alpha(view.theme.textPrimary, 0)

                    PathAngleArc {
                        centerX: view.centreX
                        centerY: view.centreY
                        radiusX: view.orbitInner
                        radiusY: view.orbitInner * view.tilt
                        startAngle: 180
                        sweepAngle: 180
                    }
                }

                ShapePath {
                    strokeColor: view.theme.boundary
                    strokeWidth: view.tokens.borderSize
                    fillColor: view.theme.alpha(view.theme.textPrimary, 0)

                    PathAngleArc {
                        centerX: view.centreX
                        centerY: view.centreY
                        radiusX: view.orbitInner
                        radiusY: view.orbitInner * view.tilt
                        startAngle: 0
                        sweepAngle: 180
                    }
                }

                ShapePath {
                    strokeColor: view.theme.hairline
                    strokeWidth: view.tokens.borderSize
                    strokeStyle: ShapePath.DashLine
                    dashPattern: [2, 6]
                    fillColor: view.theme.alpha(view.theme.textPrimary, 0)

                    PathAngleArc {
                        centerX: view.centreX
                        centerY: view.centreY
                        radiusX: view.orbitOuter
                        radiusY: view.orbitOuter * view.tilt
                        startAngle: 180
                        sweepAngle: 180
                    }
                }

                ShapePath {
                    strokeColor: view.theme.boundary
                    strokeWidth: view.tokens.borderSize
                    strokeStyle: ShapePath.DashLine
                    dashPattern: [2, 6]
                    fillColor: view.theme.alpha(view.theme.textPrimary, 0)

                    PathAngleArc {
                        centerX: view.centreX
                        centerY: view.centreY
                        radiusX: view.orbitOuter
                        radiusY: view.orbitOuter * view.tilt
                        startAngle: 0
                        sweepAngle: 180
                    }
                }
            }

            // The host: the product symbol, in the HOST grey, always.
            IsolationGlyph {
                id: host

                objectName: "sfere-host"
                x: view.centreX - width / 2
                y: view.centreY - height / 2
                z: 2
                size: view.hostSize
                stroke: view.theme.provenanceColor("host")
                core: view.theme.provenanceColor("host")
            }

            ShellLabel {
                id: hostWord

                objectName: "sfere-host-word"
                x: view.centreX - width / 2
                y: view.centreY + view.hostRadius + view.tokens.spaceXs
                z: 4
                tokens: view.tokens
                role: "label"
                text: "Host"
                color: view.theme.textSecondary
            }

            // The GPU token on the host: a chip with two pins beside the
            // emblem, in the HOST grey, and the word.
            Item {
                id: hostToken

                readonly property real side:
                    Math.max(view.tokens.markerSize, view.hostSize * 0.07)

                objectName: "sfere-host-gpu"
                visible: view.gpuOnHost
                x: view.centreX + view.hostRadius + view.tokens.spaceSm
                y: view.centreY - hostToken.side * 0.6
                z: 2
                width: hostToken.side * 1.5
                height: hostToken.side * 1.2

                Rectangle {
                    x: hostToken.side * 0.25
                    width: hostToken.side
                    height: hostToken.side * 1.2
                    color: view.theme.provenanceColor("host")
                }

                Rectangle {
                    y: hostToken.side * 0.2
                    width: hostToken.side * 1.5
                    height: Math.max(1, hostToken.side * 0.15)
                    color: view.theme.provenanceColor("host")
                }

                Rectangle {
                    y: hostToken.side * 0.85
                    width: hostToken.side * 1.5
                    height: Math.max(1, hostToken.side * 0.15)
                    color: view.theme.provenanceColor("host")
                }

                Rectangle {
                    x: hostToken.side * 0.5
                    y: hostToken.side * 0.3
                    width: hostToken.side * 0.5
                    height: hostToken.side * 0.6
                    color: Qt.darker(view.theme.provenanceColor("host"), 5)
                }

                ShellLabel {
                    x: hostToken.side * 1.5 + view.tokens.spaceXs
                    y: (hostToken.height - height) / 2
                    tokens: view.tokens
                    role: "label"
                    text: "GPU"
                    color: view.theme.textSecondary
                }
            }

            // Every Machine, every other domain and every count.
            Repeater {
                id: slotRepeater

                model: view.slots

                delegate: ShellControl {
                    id: slot

                    required property var modelData
                    required property int index

                    readonly property var entry: modelData.entry
                    readonly property string orbitName: modelData.orbit
                    readonly property real angle: view.angleAt(modelData.fraction)
                    readonly property real orbit: view.orbitRadius(modelData.orbit)
                    readonly property real centreX:
                        view.centreX + slot.orbit * Math.cos(slot.angle)
                    readonly property real centreY:
                        view.centreY + slot.orbit * view.tilt * Math.sin(slot.angle)

                    readonly property string network: view.pathFor(slot.entry)

                    // A state outside the sphere's vocabulary is drawn as the
                    // outline, so its word is always written beside it.
                    readonly property bool unsupported:
                        slot.entry.kind !== "external"
                        && sphere.knownDomain && !sphere.knownState

                    objectName: "sfere-slot-" + slot.entry.key
                    x: Math.round(slot.centreX - slot.width / 2)
                    y: Math.round(slot.centreY - slot.height / 2)
                    // Behind the host on the far half of the orbit, in front
                    // of it on the near half.
                    z: Math.sin(slot.angle) < 0 ? 1 : 3
                    width: view.sphereSize + view.tokens.spaceSm
                    height: view.sphereSize + view.tokens.spaceSm
                    radius: width / 2
                    flat: true
                    tokens: view.tokens
                    theme: view.theme
                    accessibleName: view.partsFor(slot.entry).join(", ")
                    Accessible.description:
                        slot.entry.kind === "machine"
                        ? "Open this Machine"
                        : "Open Machines, where it is listed"

                    content: [
                        MachineSphere {
                            id: sphere

                            objectName: "sfere-sphere-" + slot.entry.key
                            tokens: view.tokens
                            theme: view.theme
                            machineName: slot.entry.name
                            domain: slot.entry.domain
                            state: slot.entry.sphereState
                            disposable: slot.entry.disposable
                            gpuOwner:
                                slot.entry.kind !== "group"
                                && view.gpuOwner.length > 0
                                && slot.entry.id === view.gpuOwner
                            size: view.sphereSize
                        }
                    ]

                    // The link: a declared path, from outside this sphere and its
                    // name to outside the emblem, its word and its GPU token. A
                    // neutral line: a link is not a trust identity, and it never
                    // reaches the core. Drawn under the sphere.
                    Item {
                        id: link

                        readonly property string machine: slot.entry.key
                        readonly property string network: slot.network
                        readonly property real reach: Math.hypot(
                            view.centreX - slot.centreX, view.centreY - slot.centreY)
                        readonly property real dirX: (view.centreX - slot.centreX) / link.reach
                        readonly property real dirY: (view.centreY - slot.centreY) / link.reach
                        readonly property real fromGap: Math.max(
                            view.sphereSize / 2 + view.tokens.spaceSm,
                            name.visible
                                ? view.leave(name.x - slot.width / 2, name.y - slot.height / 2,
                                    name.width, name.height, link.dirX, link.dirY)
                                    + view.tokens.spaceXs
                                : 0)
                        readonly property real toGap: Math.max(
                            view.hostRadius + view.tokens.spaceSm,
                            view.leave(hostWord.x - view.centreX, hostWord.y - view.centreY,
                                hostWord.width, hostWord.height, -link.dirX, -link.dirY)
                                + view.tokens.spaceXs,
                            hostToken.visible
                                ? view.leave(
                                    hostToken.x + hostToken.childrenRect.x - view.centreX,
                                    hostToken.y + hostToken.childrenRect.y - view.centreY,
                                    hostToken.childrenRect.width, hostToken.childrenRect.height,
                                    -link.dirX, -link.dirY) + view.tokens.spaceXs
                                : 0)
                        readonly property real span:
                            Math.max(0, link.reach - link.fromGap - link.toGap)
                        readonly property real fromX: slot.centreX + link.dirX * link.fromGap
                        readonly property real fromY: slot.centreY + link.dirY * link.fromGap
                        readonly property real toX: link.fromX + link.dirX * link.span
                        readonly property real toY: link.fromY + link.dirY * link.span

                        objectName: "sfere-link-" + slot.entry.key
                        visible: link.network.length > 0
                        z: -1
                        x: link.fromX - slot.x
                        y: link.fromY - slot.y
                        transformOrigin: Item.TopLeft
                        rotation: Math.atan2(link.dirY, link.dirX) * 180 / Math.PI

                        Rectangle {
                            y: -height / 2
                            width: link.span
                            height: view.tokens.focusOutline
                            antialiasing: true
                            color: view.theme.boundaryStrong
                        }
                    }

                    ShellLabel {
                        id: name

                        objectName: "sfere-name-" + slot.entry.key
                        anchors.top: parent.bottom
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: Math.min(
                            implicitWidth,
                            Math.max(view.sphereSize, view.slotArc - view.tokens.spaceSm))
                        visible:
                            view.namesVisible
                            || slot.entry.kind === "group"
                            || slot.unsupported
                        tokens: view.tokens
                        role: "meta"
                        horizontalAlignment: Text.AlignHCenter
                        elide: slot.entry.kind === "group" ? Text.ElideNone : Text.ElideRight
                        text: slot.entry.name
                            + (slot.entry.kind === "group" ? "\n" + slot.entry.observed
                                : (slot.unsupported ? " · " + slot.entry.observed : ""))
                        color: view.theme.textSecondary
                    }

                    onActivated: view.open(slot.entry)
                    onHoveredChanged: {
                        if (slot.hovered)
                            view.readoutId = slot.entry.key;
                        else
                            view.noteReadout();
                    }
                    onActiveFocusChanged: {
                        if (slot.activeFocus)
                            view.readoutId = slot.entry.key;
                        else
                            view.noteReadout();
                    }

                    Keys.onPressed: event => {
                        if (event.key === Qt.Key_Right || event.key === Qt.Key_Down) {
                            view.moveFocus(slot.index, 1);
                            event.accepted = true;
                        } else if (event.key === Qt.Key_Left || event.key === Qt.Key_Up) {
                            view.moveFocus(slot.index, -1);
                            event.accepted = true;
                        }
                    }
                }
            }

            // The domain of each sector, as a word, outside the outer orbit.
            Repeater {
                model: view.sectors

                // Above and below the orbit the reboot words follow the domain
                // on one line, so the heading fits the margin; beside it they
                // stack.
                delegate: Grid {
                    id: sector

                    required property var modelData

                    readonly property real angle: view.angleAt(modelData.fraction)
                    readonly property real reach:
                        view.sphereSize / 2 + view.tokens.spaceLg
                        + (view.namesVisible ? view.tokens.spaceXxl : 0)
                    readonly property real anchorX: view.centreX
                        + (view.orbitOuter + sector.reach) * Math.cos(sector.angle)
                    readonly property real anchorY: view.centreY
                        + (view.orbitOuter * view.tilt + sector.reach) * Math.sin(sector.angle)
                    readonly property real side: Math.cos(sector.angle)
                    readonly property real depth: Math.sin(sector.angle)
                    readonly property bool needsReboot: view.needsReboot(modelData.id)

                    objectName: "sfere-sector-" + modelData.id
                    x: Math.max(view.tokens.spaceSm, Math.min(
                        view.sceneWidth - width - view.tokens.spaceSm,
                        sector.side > 0.35 ? sector.anchorX
                        : (sector.side < -0.35 ? sector.anchorX - width
                            : sector.anchorX - width / 2)))
                    y: Math.max(view.tokens.spaceSm, Math.min(
                        view.sceneHeight - height - view.tokens.spaceSm,
                        sector.depth < -0.35 ? sector.anchorY - height
                        : (sector.depth > 0.35 ? sector.anchorY
                            : sector.anchorY - height / 2)))
                    z: 4
                    columns: Math.abs(sector.side) > 0.35 ? 1 : 2
                    rowSpacing: 2
                    columnSpacing: view.tokens.spaceSm
                    verticalItemAlignment: Grid.AlignVCenter

                    ShellLabel {
                        tokens: view.tokens
                        role: "label"
                        text: view.sectorWord(sector.modelData.id)
                        color: view.theme.textSecondary
                        Accessible.role: Accessible.Heading
                    }

                    ShellLabel {
                        objectName: "sfere-sector-reboot-" + sector.modelData.id
                        visible: sector.needsReboot
                        tokens: view.tokens
                        role: "meta"
                        text: view.rebootWords()
                        color: view.theme.textQuiet
                    }
                }
            }

            // An inventory that cannot be read never looks like an empty one.
            EmptyState {
                objectName: "sfere-unavailable"
                x: view.tokens.workspacePadding
                y: view.tokens.spaceSm
                width: Math.min(view.tokens.dialogWidth, view.sceneWidth / 3)
                z: 4
                visible: !view.inventoryAvailable
                tokens: view.tokens
                theme: view.theme
                kind: "unavailable"
                title: "Machine inventory cannot be read"
                description:
                    "The host inventory source did not answer. "
                    + "Diagnostics has the observation detail."
            }

            // No Machines: the host alone, and the one thing to do next.
            Column {
                objectName: "sfere-empty"
                x: view.tokens.workspacePadding
                y: view.tokens.workspacePadding
                z: 4
                visible:
                    view.inventoryAvailable && view.members.length === 0
                    && view.shellState.outsideDomainsAvailable
                spacing: view.tokens.spaceMd

                ShellLabel {
                    tokens: view.tokens
                    role: "heading"
                    text: "No Machines yet"
                    color: view.theme.textPrimary
                }

                ShellControl {
                    objectName: "sfere-create"
                    tokens: view.tokens
                    theme: view.theme
                    accessibleName: "Create a Machine"

                    content: [
                        ShellLabel {
                            anchors.verticalCenter: parent.verticalCenter
                            tokens: view.tokens
                            role: "label"
                            text: "Create a Machine"
                            color: view.theme.textPrimary
                        }
                    ]

                    onActivated: view.createRequested()
                }
            }

            // The same content as a list: the host first, then every sphere
            // in sector order. It draws nothing.
            Item {
                objectName: "sfere-list"
                width: 1
                height: 1

                Accessible.role: Accessible.List
                Accessible.name: "The host and its Machines"

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
    }

    // What the sphere under the pointer or the keyboard is, and what
    // the picture is built from.
    Column {
        id: legend

        x: view.tokens.workspacePadding
        y: view.height - height - view.tokens.workspacePadding
        z: 4
        width: view.width - view.tokens.workspacePadding * 2
        spacing: view.tokens.spaceXs

        ShellLabel {
            objectName: "sfere-readout"
            width: parent.width
            tokens: view.tokens
            role: "body"
            wrapMode: Text.Wrap
            text: view.readoutText
            color: view.theme.textPrimary
        }

        ShellLabel {
            objectName: "sfere-legend-gpu"
            width: parent.width
            tokens: view.tokens
            role: "meta"
            text: view.gpuLine
            color: view.gpuKnown
                ? view.theme.textSecondary
                : view.theme.semanticStatusColor("warn")
        }

        ShellLabel {
            objectName: "sfere-legend-claim"
            width: parent.width
            tokens: view.tokens
            role: "meta"
            text: view.claimLine
            color: view.claimCurrent || view.claimState === "loading"
                ? view.theme.textSecondary
                : view.theme.semanticStatusColor("warn")
        }

        ShellLabel {
            objectName: "sfere-legend-links"
            width: parent.width
            tokens: view.tokens
            role: "meta"
            text: view.linksLine
            color: view.networksStatus === "unavailable"
                    || view.networksStatus === "stale"
                ? view.theme.semanticStatusColor("warn")
                : view.theme.textQuiet
        }
    }

    FocusFollow {
        flickable: scroll
    }
}
