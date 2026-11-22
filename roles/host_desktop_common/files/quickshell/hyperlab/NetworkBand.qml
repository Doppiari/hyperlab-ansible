// Network definitions come from the shared, opt-in net list reader.
// Only a current registry Machine's observed attachments can light a core.
import QtQuick

Column {
    id: band
    objectName: "network-band"

    required property var tokens
    required property var theme
    required property var shellState
    required property string networkFilter
    signal filterRequested(string name)

    readonly property var order: band.shellState.provenanceOrder
    readonly property var networks: band.shellState.networksRows.slice().sort((a, b) =>
        band.rank(a.name) - band.rank(b.name))
    readonly property bool current: band.shellState.machinesAvailable
        && band.shellState.sourceState(band.shellState.machinesSourceState, band.shellState.machinesObservedAt) === "ok"
    readonly property bool incomplete: band.shellState.machines.some(row => !Array.isArray(row.networks))
    readonly property int columns: Math.max(1, Math.min(networks.length,
        Math.floor((width + grid.spacing) / (230 + grid.spacing))))

    function rank(name) {
        const index = band.order.indexOf(name);
        return index < 0 ? band.order.length : index;
    }

    function modeWord(mode) {
        return mode === "nat" ? "NAT" : mode === "isolated" ? "Isolated" : mode || "unknown";
    }

    spacing: band.tokens.spaceSm
    Accessible.role: Accessible.List
    Accessible.name: "Filter Machines by network"

    Row {
        width: parent.width
        spacing: band.tokens.spaceSm

        NetworkSphere {
            id: host
            objectName: "band-host"
            width: band.tokens.spaceXxl
            height: width
            anchors.verticalCenter: parent.verticalCenter
            colour: band.theme.provenanceColor("host")
            character: 0
            lit: 1
            forceStill: true
        }
        ShellLabel {
            id: hostTitle
            anchors.verticalCenter: parent.verticalCenter
            tokens: band.tokens
            text: "Host"
            role: "section"
            color: band.theme.textPrimary
        }
        ShellLabel {
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - host.width - hostTitle.width - parent.spacing * 2
            tokens: band.tokens
            text: "Host name unknown · reaches every network · from a network only DHCP and DNS on its own gateway, nothing else unless a rule says so"
            role: "meta"
            color: band.theme.textSecondary
            wrapMode: Text.WordWrap
        }
    }

    ShellLabel {
        width: parent.width
        visible: !band.networks.length
        tokens: band.tokens
        role: "meta"
        color: band.theme.textSecondary
        text: !band.shellState.networksViewEnabled ? "Network inventory off"
            : band.shellState.networksStatus === "empty" ? "No declared networks"
            : "Network inventory " + band.shellState.networksStatus
    }

    Grid {
        id: grid
        width: parent.width
        columns: band.columns
        spacing: band.tokens.spaceSm

        Repeater {
            id: entries
            model: band.networks
            delegate: ShellCard {
                id: entry
                required property int index
                required property var modelData
                readonly property string name: modelData.name
                readonly property var attached: band.shellState.machines.filter(row =>
                    Array.isArray(row.networks) && row.networks.includes(entry.name))
                readonly property int running: attached.filter(row => row.state === "running").length
                readonly property bool unknownRunning: attached.some(row => row.state === "unknown")
                readonly property bool complete: band.current && !band.incomplete
                readonly property bool empty: complete && !attached.length
                readonly property string summary: !band.current ? "machines unknown"
                    : !attached.length ? (empty ? "no machines" : "machines unknown")
                    : (band.incomplete ? "≥" : "") + attached.length
                        + (attached.length === 1 ? " machine · " : " machines · ")
                        + (unknownRunning || band.incomplete ? (running ? "≥" + running : "unknown") : running)
                        + " running"
                readonly property int paletteIndex: band.rank(name)
                readonly property color tone: paletteIndex < band.order.indexOf("unclassified")
                    ? band.theme.provenanceColor(name) : band.theme.textSecondary
                readonly property string subnet: modelData.subnet || "unknown"
                readonly property var facts: [
                    ["Gateway", modelData.gateway === false ? "none" : modelData.gateway || "unknown"],
                    ["Mode", band.modeWord(modelData.forward)],
                    ["DHCP", modelData.dhcp === false ? "off" : modelData.dhcp
                        ? modelData.dhcp.start + " – " + modelData.dhcp.end : "unknown"],
                    ["GPU level", modelData.gpuLevel]
                ]
                readonly property string outbound: modelData.forward === "isolated" ? "No route out"
                    : modelData.forward === "nat" ? "Internet via NAT" : "unknown"

                objectName: "band-entry-" + name
                width: Math.floor((grid.width - grid.spacing * (grid.columns - 1)) / grid.columns)
                height: details.implicitHeight + padding * 2
                padding: tokens.spaceMd
                tokens: band.tokens
                theme: band.theme
                interactive: true
                selected: band.networkFilter === name
                accessibleName: "Network " + name + ", " + summary + ", Subnet " + subnet + ", "
                    + facts.map(fact => fact.join(" ")).join(", ") + ", Outbound " + outbound
                Accessible.role: Accessible.ListItem
                Accessible.selectable: true
                Accessible.selected: selected
                onActivated: {
                    entry.focus = true;
                    band.filterRequested(selected ? "" : name);
                }
                Keys.onPressed: event => {
                    const offsets = { [Qt.Key_Left]: -1, [Qt.Key_Right]: 1,
                                      [Qt.Key_Up]: -grid.columns, [Qt.Key_Down]: grid.columns };
                    if (event.key in offsets) {
                        const next = entries.itemAt(index + offsets[event.key]);
                        if (next) next.focus = true;
                        event.accepted = true;
                    }
                }

                Column {
                    id: details
                    width: parent.width
                    spacing: band.tokens.spaceXs
                    Row {
                        width: parent.width
                        spacing: band.tokens.spaceSm
                        Item {
                            width: band.tokens.spaceHuge
                            height: width
                            anchors.verticalCenter: parent.verticalCenter
                            NetworkSphere {
                                objectName: "network-core"
                                anchors.fill: parent
                                visible: band.current && entry.attached.length > 0
                                    && (entry.running > 0 || (entry.complete && !entry.unknownRunning))
                                colour: entry.tone
                                character: entry.paletteIndex < band.order.indexOf("unclassified")
                                    ? entry.paletteIndex + 1 : 1
                                lit: band.current && entry.running > 0 ? 1 : 0
                                forceStill: true
                            }
                            Rectangle {
                                objectName: "network-outline"
                                anchors.centerIn: parent
                                visible: entry.empty
                                width: parent.width * 0.8
                                height: width
                                radius: width / 2
                                color: band.theme.alpha(entry.tone, 0)
                                border.color: entry.tone
                                border.width: band.tokens.borderSize
                            }
                        }
                        ShellLabel {
                            id: networkName
                            anchors.verticalCenter: parent.verticalCenter
                            width: Math.min(implicitWidth, parent.width * 0.36)
                            tokens: band.tokens
                            role: "section"
                            text: entry.name.charAt(0).toUpperCase() + entry.name.slice(1)
                            color: band.theme.textPrimary
                        }
                        ShellLabel {
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - band.tokens.spaceHuge - networkName.width - parent.spacing * 2
                            tokens: band.tokens
                            role: "meta"
                            text: entry.summary
                            color: band.theme.textSecondary
                            wrapMode: Text.WordWrap
                        }
                    }
                    ShellLabel {
                        width: parent.width
                        tokens: band.tokens
                        role: "value"
                        text: entry.subnet
                        color: band.theme.textPrimary
                        Accessible.name: "Subnet " + text
                    }
                    Grid {
                        width: parent.width
                        columns: 2
                        spacing: band.tokens.spaceXs
                        Repeater {
                            model: entry.facts
                            delegate: Column {
                                required property var modelData
                                required property int index
                                width: (parent.width - parent.spacing) * (index % 2 === 0 ? 0.68 : 0.32)
                                ShellLabel {
                                    tokens: band.tokens
                                    text: modelData[0]
                                    role: "meta"
                                    color: band.theme.textQuiet
                                }
                                ShellLabel {
                                    width: parent.width
                                    tokens: band.tokens
                                    text: modelData[1]
                                    role: "mono"
                                    wrapMode: Text.WrapAnywhere
                                    color: band.theme.textPrimary
                                    Accessible.name: modelData.join(" ")
                                }
                            }
                        }
                    }
                    ShellDivider {
                        width: parent.width
                        tokens: band.tokens
                        theme: band.theme
                        vertical: false
                    }
                    ShellLabel {
                        width: parent.width
                        tokens: band.tokens
                        role: "meta"
                        text: entry.outbound
                        color: band.theme.textSecondary
                        Accessible.name: "Outbound " + text
                    }
                }
            }
        }
    }
}
