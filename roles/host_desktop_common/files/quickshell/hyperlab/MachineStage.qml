// HyperLab Machines workspace (V447-C9.3).
//
// The inventory and the machine an operator is working on, in one page. The
// inventory is grouped by observed network attachments, with one count per group.
// Other libvirt domains remain read-only in their own Not managed
// group, without gaining product membership or operational controls.
//
// Every fact is the host inventory projection. Empty, filtered and
// unavailable are three different states with three different sentences, and
// an unavailable inventory never looks like an empty one. Selecting a card
// opens the machine's pane; selection never starts anything.
//
// Large inventories stay reachable: the list layout is virtualized and
// becomes the default past the point where a grid stops being readable.

import QtQuick

Item {
    id: stage
    objectName: "machine-stage"

    required property var tokens
    required property var theme
    required property var icons
    required property var shellState
    required property var machineActions
    required property var shellSurfaces

    property string query: ""
    property string layoutMode: "auto"
    property string networkFilter: ""
    property string stateFilter: "all"

    // The Create view replaces the inventory while it is open; it is built
    // on demand, so every opening reads a fresh creation plan.
    property bool creating: false

    readonly property int total:
        stage.shellState.machines.length + stage.shellState.outsideDomains.length

    // Past this a grid stops being an inventory and starts being wallpaper.
    readonly property int denseThreshold: 60

    readonly property string layout:
        stage.layoutMode !== "auto"
        ? stage.layoutMode
        : (stage.total > stage.denseThreshold ? "list" : "grid")

    readonly property string selectedId:
        stage.shellSurfaces.selectedMachineId

    readonly property bool hasSelection: stage.selectedId.length > 0

    readonly property var machine:
        stage.shellState.machineById(stage.selectedId)

    readonly property bool wide:
        stage.width >= stage.tokens.breakpointMedium

    // Narrow outputs show one region at a time: the pane replaces the
    // inventory and an explicit Back returns to it.
    readonly property bool paneOnly: stage.hasSelection && !stage.wide

    readonly property int paneWidth:
        stage.width >= stage.tokens.breakpointWide
        ? stage.tokens.contextPaneWide
        : stage.tokens.contextPaneCompact

    Keys.onEscapePressed: event => {
        event.accepted = stage.networkFilter.length > 0 && !stage.creating;
        if (event.accepted) stage.networkFilter = "";
    }

    readonly property var filtered: {
        const needle = stage.query.trim().toLowerCase();
        const out = [];

        for (let index = 0; index < stage.shellState.machines.length; index++) {
            const row = stage.shellState.machines[index];
            const running = String(row.state) === "running";

            if (stage.networkFilter && !(Array.isArray(row.networks) && row.networks.includes(stage.networkFilter)))
                continue;

            if (stage.stateFilter === "running" && !running)
                continue;

            if (stage.stateFilter === "stopped" && running)
                continue;

            if (needle.length > 0) {
                const haystack =
                    String(row.name).toLowerCase()
                    + " " + String(row.provenance).toLowerCase()
                    + " " + (row.networks || []).join(" ").toLowerCase()
                    + " " + String(row.state).toLowerCase();

                if (haystack.indexOf(needle) < 0)
                    continue;
            }

            out.push(row);
        }

        return out;
    }

    readonly property var filteredOutside: stage.shellState.outsideDomains.filter(row => {
        const running = row.state === "running";
        const needle = stage.query.trim().toLowerCase();
        if (stage.networkFilter && !(Array.isArray(row.networks) && row.networks.includes(stage.networkFilter)))
            return false;

        return (stage.stateFilter !== "running" || running)
            && (stage.stateFilter !== "stopped" || !running)
            && (needle.length === 0
                || (row.name + " " + (stage.inventoryAvailable ? "external" : "membership unknown")
                    + " " + row.state).toLowerCase().indexOf(needle) >= 0);
    })

    readonly property var groups: {
        const groups = new Map();
        for (const row of stage.filtered) {
            const networks = Array.isArray(row.networks)
                ? (row.networks.length ? row.networks : [""]) : [null];
            for (const name of new Set(networks)) {
                if (stage.networkFilter && stage.networkFilter !== name) continue;
                if (!groups.has(name)) {
                    const net = band.networks.find(item => item.name === name);
                    groups.set(name, {
                        identity: name,
                        title: name === null ? "Network unknown" : name === "" ? "No network"
                            : name.charAt(0).toUpperCase() + name.slice(1),
                        description: name ? "Subnet " + (net && net.subnet || "unknown")
                            + " · Mode " + band.modeWord(net && net.forward) : "",
                        machines: []
                    });
                }
                groups.get(name).machines.push(row);
            }
        }
        return Array.from(groups.values()).sort((a, b) => band.rank(a.identity) - band.rank(b.identity));
    }

    readonly property string inventoryState:
        stage.shellState.sourceState(
            stage.shellState.machinesSourceState,
            stage.shellState.machinesObservedAt
        )

    readonly property bool inventoryAvailable:
        stage.shellState.machinesAvailable

    // The total covers every domain only when libvirt answered; otherwise
    // it names the product part and says the rest is unavailable. A stale
    // registry read keeps its own age next to that count.
    readonly property string definedSummary:
        (stage.shellState.outsideDomainsAvailable
            ? stage.total + " defined"
            : stage.shellState.machines.length + " managed · other domains unavailable")
        + (stage.inventoryState === "stale"
            ? " · last observed "
                + stage.shellState.observedAge(stage.shellState.machinesObservedAt)
            : "")

    // Capabilities belong to the selected machine and the generation it was
    // resolved against; a new selection or a new snapshot re-asks the bridge.
    function refreshCapabilities() {
        if (!stage.hasSelection) {
            stage.machineActions.clearCapabilities();
            return;
        }

        stage.machineActions.probe(
            stage.selectedId,
            stage.shellState.machinesGeneration
        );
    }

    Connections {
        target: stage.shellSurfaces

        function onSelectedMachineIdChanged() {
            stage.refreshCapabilities();
        }
    }

    Connections {
        target: stage.shellState

        // The inventory changed underneath the answer: ask again. An
        // identical poll does not change the generation, so an unchanged
        // machine is not re-probed every 30 seconds.
        function onMachinesGenerationChanged() {
            if (
                stage.hasSelection
                && stage.shellState.capabilityRequest.generation
                    !== stage.shellState.machinesGeneration
            ) {
                stage.refreshCapabilities();
            }
        }
    }

    Loader {
        anchors.fill: parent
        active: stage.creating
        visible: stage.creating

        sourceComponent: CreateMachineView {
            tokens: stage.tokens
            theme: stage.theme
            icons: stage.icons
            shellState: stage.shellState
            machineActions: stage.machineActions
            shellSurfaces: stage.shellSurfaces

            onClosed: stage.creating = false
        }
    }

    Item {
        anchors.fill: parent
        visible: !stage.creating

        WorkspaceFrame {
            id: frame
            objectName: "machine-inventory-summary"

            visible: !stage.paneOnly
            width: parent.width
            height: parent.height

            tokens: stage.tokens
            theme: stage.theme

            title: "Machines"

            subtitle:
                stage.inventoryAvailable
                ? stage.definedSummary + " · " + stage.shellState.runningMachinesSummary
                : "Product inventory unavailable · " + stage.shellState.runningMachinesSummary

            subtitleClass:
                stage.inventoryAvailable
                ? (stage.inventoryState === "stale" ? "warn" : "")
                : "warn"

            trailing: [
                ShellControl {
                    objectName: "newMachine"
                    anchors.verticalCenter: parent.verticalCenter
                    height: stage.tokens.controlHeightLarge
                    tokens: stage.tokens
                    theme: stage.theme
                    accessibleName: "New Machine"
                    visible: !stage.inventoryAvailable || stage.shellState.machines.length > 0

                    content: [
                        ShellLabel {
                            anchors.verticalCenter: parent.verticalCenter
                            tokens: stage.tokens
                            role: "label"
                            text: "New Machine"
                            color: stage.theme.textPrimary
                        }
                    ]

                    onActivated: {
                        stage.shellSurfaces.clearMachineSelection();
                        stage.creating = true;
                    }
                },

                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: frame.width > 640 && (stage.total > 0 || !stage.inventoryAvailable)
                    width: Math.min(240, frame.width / 3)
                    height: stage.tokens.controlHeightLarge
                    radius: stage.tokens.radiusControl
                    color: stage.theme.raised
                    border.width:
                        searchInput.activeFocus
                        ? stage.tokens.focusOutline
                        : stage.tokens.borderSize
                    border.color:
                        searchInput.activeFocus
                        ? stage.theme.focusRing
                        : stage.theme.boundary

                    Row {
                        anchors.fill: parent
                        anchors.leftMargin: stage.tokens.spaceMd
                        anchors.rightMargin: stage.tokens.spaceMd
                        spacing: stage.tokens.spaceSm

                        ShellIcon {
                            anchors.verticalCenter: parent.verticalCenter
                            tokens: stage.tokens
                            text: stage.icons.search
                            color: stage.theme.textSecondary
                        }

                        TextInput {
                            id: searchInput

                            anchors.verticalCenter: parent.verticalCenter
                            width:
                                parent.width
                                - stage.tokens.iconBar
                                - stage.tokens.spaceSm

                            font.family: stage.tokens.fontSans
                            font.pixelSize: stage.tokens.fontBody
                            color: stage.theme.textPrimary
                            selectionColor: stage.theme.fillSelected
                            selectedTextColor: stage.theme.textPrimary
                            clip: true

                            Accessible.role: Accessible.EditableText
                            Accessible.name: "Filter machines"

                            onTextChanged: stage.query = text

                            ShellLabel {
                                anchors.verticalCenter: parent.verticalCenter
                                visible: searchInput.text.length === 0
                                tokens: stage.tokens
                                role: "body"
                                text: "Filter"
                                color: stage.theme.textQuiet
                            }
                        }
                    }
                },

                ShellControl {
                    anchors.verticalCenter: parent.verticalCenter
                    height: stage.tokens.controlHeightLarge
                    tokens: stage.tokens
                    theme: stage.theme
                    flat: true
                    visible: stage.total > 0 || !stage.inventoryAvailable
                    accessibleName:
                        stage.layout === "grid"
                        ? "Switch to list layout"
                        : "Switch to grid layout"

                    content: [
                        ShellIcon {
                            anchors.verticalCenter: parent.verticalCenter
                            tokens: stage.tokens
                            text:
                                stage.layout === "grid"
                                ? stage.icons.list
                                : stage.icons.grid
                            color: stage.theme.textSecondary
                        }
                    ]

                    onActivated:
                        stage.layoutMode =
                            stage.layout === "grid" ? "list" : "grid"
                }
            ]

            Column {
                id: inventoryColumn
                width: frame.bodyWidth - (stage.hasSelection && stage.wide ? stage.paneWidth + 1 : 0)
                spacing: stage.tokens.spaceLg

                NetworkBand {
                    id: band
                    width: frame.bodyWidth
                    tokens: stage.tokens
                    theme: stage.theme
                    shellState: stage.shellState
                    networkFilter: stage.networkFilter
                    onFilterRequested: name => stage.networkFilter = name
                    onNetworksChanged: {
                        if (!networks.some(net => net.name === stage.networkFilter))
                            stage.networkFilter = "";
                    }
                }

                // Unavailable and empty are different sentences, and a filter
                // that hides everything is a third.
                EmptyState {
                    width: parent.width
                    visible: !stage.inventoryAvailable
                    tokens: stage.tokens
                    theme: stage.theme
                    kind: "unavailable"
                    title: "Machine inventory cannot be read"
                    description:
                        "The host inventory source did not answer. "
                        + "Diagnostics has the observation detail."
                }

                Column {
                    objectName: "machine-empty-state"
                    width: parent.width
                    visible: stage.inventoryAvailable && stage.shellState.machines.length === 0
                    spacing: stage.tokens.spaceMd

                    ShellLabel {
                        tokens: stage.tokens
                        role: "heading"
                        text: "No Machines yet"
                        color: stage.theme.textPrimary
                    }
                    ShellLabel {
                        width: parent.width
                        tokens: stage.tokens
                        role: "body"
                        objectName: "machine-empty-description"
                        text: "Create a Machine from a reviewed Template."
                            + (stage.shellState.outsideDomains.length > 0
                                ? " Other libvirt domains appear below as Not managed." : "")
                        color: stage.theme.textSecondary
                    }
                    ShellControl {
                        tokens: stage.tokens
                        theme: stage.theme
                        accessibleName: "Create a Machine"
                        content: [
                            ShellLabel {
                                tokens: stage.tokens
                                role: "label"
                                text: "Create a Machine"
                                color: stage.theme.textPrimary
                            }
                        ]
                        onActivated: {
                            stage.shellSurfaces.clearMachineSelection();
                            stage.creating = true;
                        }
                    }
                }

                EmptyState {
                    width: parent.width
                    visible:
                        stage.inventoryAvailable
                        && stage.total > 0
                        && stage.filtered.length === 0
                        && stage.filteredOutside.length === 0
                    tokens: stage.tokens
                    theme: stage.theme
                    kind: "filtered"
                    title: "No machine matches this filter"
                    description:
                        "Clear the filter to see all "
                        + stage.total + " machines."
                }

                // Grouped grid.
                Repeater {
                    id: gridGroups
                    model:
                        stage.layout === "grid" && stage.filtered.length > 0
                        ? stage.groups
                        : []

                    delegate: Column {
                        required property var modelData
                        property alias tiles: tileRepeater
                        objectName: "machine-group-" + modelData.identity

                        width: inventoryColumn.width
                        spacing: stage.tokens.spaceMd

                        SectionHeader {
                            width: parent.width
                            tokens: stage.tokens
                            theme: stage.theme
                            label: modelData.title
                            description: modelData.description

                            trailing: [
                                ShellLabel {
                                    anchors.verticalCenter: parent.verticalCenter
                                    tokens: stage.tokens
                                    role: "mono"
                                    text: modelData.machines.length + (modelData.machines.length === 1 ? " Machine" : " Machines")
                                    color: stage.theme.textSecondary
                                }
                            ]
                        }

                        Flow {
                            width: parent.width
                            spacing: stage.tokens.cardGap

                            Repeater {
                                id: tileRepeater
                                model: modelData.machines

                                delegate: MachineTile {
                                    id: machineTile
                                    required property var modelData

                                    width: stage.cardWidth(inventoryColumn.width)
                                    tokens: stage.tokens
                                    theme: stage.theme
                                    icons: stage.icons
                                    machine: modelData
                                    selected:
                                        String(modelData.name)
                                        === stage.selectedId

                                    onNavigationRequested: key => stage.moveTileFocus(machineTile, key)

                                    onActivated:
                                        stage.shellSurfaces.selectMachine(
                                            String(modelData.name),
                                            stage.shellState.machinesGeneration,
                                            false
                                        )
                                }
                            }
                        }

                        ShellDivider {
                            width: parent.width
                            vertical: false
                            tokens: stage.tokens
                            theme: stage.theme
                        }
                    }
                }

                // Virtualized list. Every machine stays reachable regardless
                // of how many there are.
                ListView {
                    id: denseList
                    readonly property var rows: {
                        const result = [];
                        if (stage.layout === "list") {
                            for (const group of stage.groups) {
                                group.machines.forEach((row, index) => result.push(Object.assign({}, row, {
                                    heading: index === 0 ? group.title : "",
                                    detail: group.description,
                                    count: group.machines.length
                                })));
                            }
                        }
                        return result;
                    }
                    width: parent.width
                    visible: stage.layout === "list" && stage.filtered.length > 0
                    height:
                        visible
                        ? Math.min(
                            (denseList.rows.length + stage.groups.length) * stage.tokens.listRowHeight,
                            Math.max(
                                stage.tokens.listRowHeight,
                                stage.height - stage.tokens.workspaceHeaderHeight
                                    - stage.tokens.spaceSection
                            )
                          )
                        : 0

                    model: denseList.rows
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    cacheBuffer: stage.tokens.listRowHeight * 4

                    delegate: Item {
                        required property var modelData

                        width: ListView.view.width
                        height: stage.tokens.listRowHeight + denseHeading.height

                        SectionHeader {
                            id: denseHeading
                            width: parent.width
                            height: visible ? stage.tokens.listRowHeight : 0
                            visible: modelData.heading.length > 0
                            tokens: stage.tokens
                            theme: stage.theme
                            label: modelData.heading
                            description: modelData.detail + (modelData.detail ? " · " : "")
                                + modelData.count + (modelData.count === 1 ? " Machine" : " Machines")
                        }
                        MachineListRow {
                            anchors.top: denseHeading.bottom
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            anchors.bottomMargin: 1
                            tokens: stage.tokens
                            theme: stage.theme
                            icons: stage.icons
                            machine: modelData
                            selected:
                                String(modelData.name) === stage.selectedId

                            onActivated:
                                stage.shellSurfaces.selectMachine(
                                    String(modelData.name),
                                    stage.shellState.machinesGeneration,
                                    false
                                )
                        }
                    }
                }

                SectionHeader {
                    objectName: "external-machines-heading"
                    width: parent.width
                    visible: stage.filteredOutside.length > 0
                    tokens: stage.tokens
                    theme: stage.theme
                    label: stage.inventoryAvailable
                        ? "Not managed" + (stage.shellState.productName ? " · outside " + stage.shellState.productName : "")
                        : "Observed domains · membership unavailable"
                    description: (stage.inventoryAvailable ? "Read only · external" : "Read only · membership unknown") + " · "
                        + stage.filteredOutside.length + " domains"
                }

                ShellLabel {
                    width: parent.width
                    visible: !stage.shellState.outsideDomainsAvailable
                    tokens: stage.tokens
                    role: "body"
                    text: "External inventory unavailable"
                    color: stage.theme.textSecondary
                }

                GridView {
                    id: externalGrid
                    objectName: "external-machine-list"
                    // GridView reserves the trailing gap as part of a cell.
                    // Include that gap so it fits the same columns as Flow.
                    width: parent.width + (stage.layout === "grid" ? stage.tokens.cardGap : 0)
                    visible: stage.filteredOutside.length > 0
                    cellWidth: stage.layout === "grid"
                        ? stage.cardWidth(inventoryColumn.width) + stage.tokens.cardGap : width
                    cellHeight: stage.layout === "grid"
                        ? stage.tokens.cardHeight + stage.tokens.cardGap : stage.tokens.listRowHeight
                    height: visible ? Math.min(
                        Math.ceil(stage.filteredOutside.length / Math.max(1, Math.floor(width / cellWidth))) * cellHeight,
                        Math.max(cellHeight, stage.height / 2)
                    ) : 0
                    model: stage.filteredOutside
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds

                    delegate: Rectangle {
                        required property var modelData
                        readonly property string lifecycle: modelData.lifecycle
                        objectName: "external-machine-" + modelData.name
                        width: externalGrid.cellWidth - (stage.layout === "grid" ? stage.tokens.cardGap : 0)
                        height: externalGrid.cellHeight - (stage.layout === "grid" ? stage.tokens.cardGap : 1)
                        radius: stage.tokens.radiusCard
                        color: stage.theme.alpha(stage.theme.textPrimary, 0)
                        Accessible.role: Accessible.Grouping
                        Accessible.name: modelData.name + ", "
                            + (stage.inventoryAvailable ? "external" : "membership unknown")
                            + ", " + stage.icons.machineStateWord(modelData.state)
                            + ", OS unknown, " + allocation + ", Network " + networkText + ", Read only"
                        border.width: stage.tokens.borderSize
                        border.color: stage.theme.textPrimary

                        readonly property string membership: stage.inventoryAvailable ? "external" : "membership unknown"
                        readonly property string stateCaption: membership + " · " + stage.icons.machineStateWord(modelData.state)
                        readonly property string networkText: typeof modelData.networks?.join === "function"
                            ? modelData.networks.join(", ") || "none" : "unknown"
                        readonly property string allocation: "Memory "
                            + (modelData.memory_mb === null ? "unknown" : modelData.memory_mb + " MiB")
                            + " · vCPU " + (modelData.vcpus ?? "unknown")
                        Column {
                            anchors.fill: parent
                            anchors.margins: stage.layout === "grid" ? stage.tokens.cardPadding : stage.tokens.spaceXs
                            spacing: stage.tokens.spaceXs
                            Row {
                                width: parent.width
                                spacing: stage.tokens.spaceSm
                                Rectangle {
                                    id: outsideMark
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: stage.tokens.markerSize
                                    height: width
                                    color: stage.theme.alpha(stage.theme.textPrimary, 0)
                                    border.color: stage.theme.textPrimary
                                    border.width: stage.tokens.borderSize
                                }
                                ShellLabel {
                                    width: parent.width - outsideMark.width - parent.spacing
                                        - (compactStatus.visible ? compactStatus.width + parent.spacing : 0)
                                    tokens: stage.tokens
                                    role: stage.layout === "grid" ? "title" : "body"
                                    text: modelData.name
                                    color: stage.theme.textPrimary
                                }
                                Row {
                                    id: compactStatus
                                    visible: stage.layout === "list"
                                    anchors.verticalCenter: parent.verticalCenter
                                    spacing: stage.tokens.spaceXs
                                    ShellLabel {
                                        tokens: stage.tokens
                                        role: "meta"
                                        text: "OS unknown · Read only ·"
                                        color: stage.theme.textSecondary
                                    }
                                    ShellLabel {
                                        tokens: stage.tokens
                                        role: "meta"
                                        text: stateCaption
                                        color: stage.theme.textSecondary
                                    }
                                }
                            }
                            ShellLabel {
                                width: parent.width
                                tokens: stage.tokens
                                role: "meta"
                                visible: stage.layout === "grid"
                                text: stateCaption
                                color: stage.theme.textSecondary
                            }
                            ShellLabel {
                                width: parent.width
                                tokens: stage.tokens
                                role: "mono"
                                text: stage.layout === "grid" ? allocation : allocation + " · Network " + networkText
                                color: stage.theme.textSecondary
                            }
                            ShellLabel {
                                width: parent.width
                                visible: stage.layout === "grid"
                                tokens: stage.tokens
                                role: "mono"
                                text: "Network " + networkText
                                color: stage.theme.textSecondary
                            }
                            ShellLabel {
                                width: parent.width
                                visible: stage.layout === "grid"
                                tokens: stage.tokens
                                role: "meta"
                                text: "OS unknown"
                                color: stage.theme.textQuiet
                            }
                            ShellLabel {
                                width: parent.width
                                visible: stage.layout === "grid"
                                tokens: stage.tokens
                                role: "meta"
                                text: "Read only · " + membership
                                color: stage.theme.textSecondary
                            }
                        }
                    }
                }

                ShellLabel {
                    width: parent.width
                    visible:
                        stage.inventoryAvailable
                        && !stage.hasSelection
                        && stage.filtered.length > 0
                    tokens: stage.tokens
                    role: "meta"
                    text: "Select a machine to see its connections and power controls."
                    color: stage.theme.textQuiet
                }
            }
        }

        Rectangle {
            visible: stage.hasSelection && stage.wide
            anchors.right: contextPane.left
            y: contextPane.y
            width: 1
            height: contextPane.height
            color: stage.theme.hairline
        }

        MachineContextPane {
            id: contextPane
            visible: stage.hasSelection
            anchors.right: parent.right
            width: stage.paneOnly ? parent.width : stage.paneWidth
            // As the band scrolls away, the pane keeps the fixed heading clear.
            y: stage.paneOnly ? 0 : Math.min(stage.height, Math.max(stage.tokens.workspaceHeaderHeight + 1,
                frame.bodyTop + band.height + inventoryColumn.spacing))
            height: parent.height - y

            tokens: stage.tokens
            theme: stage.theme
            icons: stage.icons
            shellState: stage.shellState
            machineActions: stage.machineActions
            shellSurfaces: stage.shellSurfaces
            machine: stage.machine
            showBack: stage.paneOnly
        }
    }

    function moveTileFocus(source, key) {
        const tiles = [];
        for (let group = 0; group < gridGroups.count; group++) {
            const repeater = gridGroups.itemAt(group).tiles;
            for (let index = 0; index < repeater.count; index++)
                tiles.push(repeater.itemAt(index));
        }
        const index = tiles.indexOf(source);
        let target = null;
        if (key === Qt.Key_Left || key === Qt.Key_Right) {
            target = tiles[index + (key === Qt.Key_Left ? -1 : 1)];
        } else {
            const origin = source.mapToItem(stage, 0, 0);
            let best = Infinity;
            for (const tile of tiles) {
                const point = tile.mapToItem(stage, 0, 0);
                const dy = point.y - origin.y;
                if ((key === Qt.Key_Up && dy >= 0) || (key === Qt.Key_Down && dy <= 0))
                    continue;
                const distance = Math.abs(dy) * stage.width + Math.abs(point.x - origin.x);
                if (distance < best) {
                    best = distance;
                    target = tile;
                }
            }
        }
        if (target)
            target.forceActiveFocus(Qt.TabFocusReason);
    }

    // Cards stay inside the reviewed 300-420 range and fill the row evenly
    // rather than leaving a ragged trailing gap.
    function cardWidth(available) {
        const gap = stage.tokens.cardGap;
        const columns = Math.max(
            1,
            Math.floor((available + gap) / (stage.tokens.cardMinWidth + gap))
        );

        return Math.min(
            stage.tokens.cardMaxWidth,
            Math.floor((available - gap * (columns - 1)) / columns)
        );
    }
}
