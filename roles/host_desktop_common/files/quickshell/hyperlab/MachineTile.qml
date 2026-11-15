// One inventory Machine, with the host-confirmed sphere and allocation.
// Selection opens its existing pane; this tile performs no Machine action.
import QtQuick

ShellCard {
    id: tile

    required property var icons
    required property var machine

    signal navigationRequested(int key)

    readonly property string relation: String(tile.machine.gpu_relation)
    readonly property string memoryText: {
        const value = tile.machine.memory_mb;
        if (typeof value !== "number") return "Unknown";
        return value >= 1024
            ? (value / 1024).toFixed(value % 1024 === 0 ? 0 : 1) + " GiB"
            : value + " MiB";
    }
    readonly property string resourceText:
        tile.memoryText + " · "
        + (typeof tile.machine.vcpus === "number" ? tile.machine.vcpus : "Unknown")
        + " vCPU · " + sphere.domainWord
    readonly property string hardwareText:
        tile.relation === "held" ? "Holds the GPU"
        : tile.relation === "configured" ? "Passthrough configured"
        : tile.relation === "unknown" ? "Passthrough unknown" : ""
    readonly property color wash:
        sphere.knownDomain ? tile.theme.mix(tile.theme.provenanceColor(sphere.domain), tile.theme.raised, 0.07)
                           : tile.theme.raised

    objectName: "machine-tile-" + tile.machine.name
    height: tile.tokens.cardHeight
    interactive: true
    color: tile.selected ? tile.theme.mix(tile.theme.textPrimary, tile.wash, 0.08) : tile.wash
    accessibleName:
        sphere.Accessible.name + ", allocation " + tile.resourceText
        + (tile.hardwareText.length > 0 ? ", " + tile.hardwareText : "")

    Row {
        id: identity
        width: parent.width
        spacing: tile.tokens.spaceMd

        MachineSphere {
            id: sphere
            tokens: tile.tokens
            theme: tile.theme
            machineName: String(tile.machine.name)
            domain: String(tile.machine.provenance)
            state: String(tile.machine.state)
            disposable: tile.machine.lifecycle === "disposable"
            gpuOwner: tile.relation === "held"
            size: tile.tokens.spaceSection
        }

        StateChip {
            anchors.verticalCenter: parent.verticalCenter
            tokens: tile.tokens
            theme: tile.theme
            icons: tile.icons
            state: String(tile.machine.state)
        }
    }

    ShellLabel {
        id: nameLabel
        anchors.top: identity.bottom
        anchors.topMargin: tile.tokens.spaceSm
        width: parent.width
        tokens: tile.tokens
        role: "title"
        text: String(tile.machine.name)
        color: tile.theme.textPrimary
    }

    ShellLabel {
        id: allocation
        anchors.top: nameLabel.bottom
        anchors.topMargin: tile.tokens.spaceXs
        width: parent.width
        tokens: tile.tokens
        role: "mono"
        text: tile.resourceText
        color: tile.theme.textSecondary
    }

    Row {
        anchors.top: allocation.bottom
        anchors.topMargin: tile.tokens.spaceXs
        spacing: tile.tokens.spaceSm
        visible: tile.hardwareText.length > 0

        ShellIcon {
            anchors.verticalCenter: parent.verticalCenter
            tokens: tile.tokens
            text: tile.icons.gpu
            color: tile.theme.textSecondary
        }
        ShellLabel {
            tokens: tile.tokens
            role: "meta"
            text: tile.hardwareText
            color: tile.theme.textSecondary
        }
    }

    Keys.onPressed: event => {
        if ([Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down].indexOf(event.key) >= 0) {
            tile.navigationRequested(event.key);
            event.accepted = true;
        }
    }
}
