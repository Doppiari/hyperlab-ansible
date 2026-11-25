// One inventory Machine, with its host-confirmed identity, attachments and allocation.
// Selection opens its existing pane; this tile performs no Machine action.
// A product Machine whose provisioning receipt does not say "finished" says
// so, with the command that resumes it; it never reads as ready.
import QtQuick

ShellCard {
    id: tile

    required property var icons
    required property var machine
    signal navigationRequested(int key)

    readonly property string relation: String(tile.machine.gpu_relation)
    readonly property string memoryText: {
        const value = tile.machine.memory_mb;
        if (typeof value !== "number") return "unknown";
        return value >= 1024
            ? (value / 1024).toFixed(value % 1024 === 0 ? 0 : 1) + " GiB"
            : value + " MiB";
    }
    readonly property string networkText: typeof tile.machine.networks?.join !== "function" ? "unknown"
        : tile.machine.networks.join(", ") || "none"
    readonly property string osLabel: "OS " + (tile.machine.os || "unknown")
    readonly property var facts: [
        ["Memory", tile.memoryText],
        ["vCPU", typeof tile.machine.vcpus === "number" ? String(tile.machine.vcpus) : "unknown"],
        ["Network", tile.networkText]
    ]
    readonly property string hardwareText:
        tile.relation === "held" ? "Holds the GPU"
        : tile.relation === "configured" ? "Passthrough configured"
        : tile.relation === "none" ? "No passthrough" : "Passthrough unknown"
    readonly property string footer: tile.machine.lifecycle === "disposable"
        ? (tile.machine.runtime_present === true && tile.machine.runtime_drift === false
            ? "Disposable · discarded at shutdown" : "Disposable configured · discard unknown")
            + (tile.relation === "held" || tile.relation === "configured" ? " · " + tile.hardwareText : "")
        : tile.hardwareText
    // Only a product Machine has a provisioning; without a reading, or with
    // one that is not hyperlabctl's, it is unknown, never provisioned.
    readonly property var provisioning: tile.machine.provisioning
    readonly property bool provisioningShown:
        tile.machine.product_managed === true
        && !(tile.provisioning && tile.provisioning.status === "finished")
    readonly property bool provisioningRead:
        !!tile.provisioning
        && ["incomplete", "unknown"].indexOf(tile.provisioning.status) >= 0
        && typeof tile.provisioning.text === "string"
        && tile.provisioning.text.indexOf("Provisioning ") === 0
    readonly property string provisioningText: !tile.provisioningShown ? ""
        : tile.provisioningRead ? tile.provisioning.text : "Provisioning unknown"
    readonly property string resumeText:
        tile.provisioningShown && tile.provisioningRead && typeof tile.provisioning.resume === "string"
        ? tile.provisioning.resume : ""
    readonly property color wash: tile.theme.knownProvenance(tile.machine.provenance)
        ? tile.theme.mix(tile.theme.provenanceColor(tile.machine.provenance), tile.theme.raised, 0.07)
        : tile.theme.raised

    objectName: "machine-tile-" + tile.machine.name
    height: Math.max(tile.tokens.cardHeight, content.implicitHeight + padding * 2)
    interactive: true
    color:
        tile.selected
        ? tile.theme.mix(tile.theme.textPrimary, tile.wash, 0.08)
        : (tile.actionable && (tile.hovered || tile.pressed)
            ? tile.theme.mix(tile.theme.textPrimary, tile.wash, 0.05)
            : tile.wash)
    accessibleName: tile.machine.name + ", " + tile.osLabel + ", "
        + tile.theme.provenanceLabel(tile.machine.provenance) + ", " + tile.icons.machineStateWord(tile.machine.state)
        + ", " + tile.facts.map(fact => fact.join(" ")).join(", ") + ", " + tile.footer
        + (tile.footer.includes(tile.hardwareText) ? "" : ", " + tile.hardwareText)
        + (tile.provisioningText ? ", " + tile.provisioningText : "")
        + (tile.resumeText ? ", resume with " + tile.resumeText : "")

    Column {
        id: content
        width: parent.width
        spacing: tile.tokens.spaceSm

        Row {
            width: parent.width
            spacing: tile.tokens.spaceSm
            ProvenanceMarker {
                anchors.verticalCenter: parent.verticalCenter
                tokens: tile.tokens
                theme: tile.theme
                identity: tile.machine.provenance
            }
            ShellLabel {
                width: parent.width - os.width - tile.tokens.markerSize - parent.spacing * 2
                tokens: tile.tokens
                role: "title"
                text: tile.machine.name
                color: tile.theme.textPrimary
            }
            ShellLabel {
                id: os
                anchors.verticalCenter: parent.verticalCenter
                width: Math.min(implicitWidth, parent.width / 3)
                tokens: tile.tokens
                role: "meta"
                text: tile.machine.os || tile.osLabel
                color: tile.theme.textQuiet
                Accessible.name: tile.osLabel
            }
        }
        Item {
            width: parent.width
            height: chip.height
            ShellLabel {
                anchors.verticalCenter: parent.verticalCenter
                tokens: tile.tokens
                role: "label"
                text: tile.theme.provenanceLabel(tile.machine.provenance)
                color: tile.theme.provenanceColor(tile.machine.provenance)
            }
            StateChip {
                id: chip
                anchors.right: parent.right
                tokens: tile.tokens
                theme: tile.theme
                icons: tile.icons
                state: String(tile.machine.state)
            }
        }
        Row {
            width: parent.width
            spacing: tile.tokens.spaceMd
            Repeater {
                model: tile.facts
                delegate: Column {
                    required property var modelData
                    width: (parent.width - parent.spacing * 2) / 3
                    ShellLabel {
                        tokens: tile.tokens
                        role: "meta"
                        text: modelData[0]
                        color: tile.theme.textQuiet
                    }
                    ShellLabel {
                        width: parent.width
                        tokens: tile.tokens
                        role: "mono"
                        text: modelData[1]
                        color: tile.theme.textPrimary
                        Accessible.name: modelData.join(" ")
                    }
                }
            }
        }
        ShellDivider {
            width: parent.width
            tokens: tile.tokens
            theme: tile.theme
            vertical: false
        }
        ShellLabel {
            width: parent.width
            tokens: tile.tokens
            role: "meta"
            wrapMode: Text.WordWrap
            text: tile.footer
            color: tile.theme.textSecondary
        }
        ShellLabel {
            objectName: "machine-provisioning-" + tile.machine.name
            width: parent.width
            visible: tile.provisioningText.length > 0
            tokens: tile.tokens
            role: "meta"
            wrapMode: Text.WordWrap
            text: tile.provisioningText
            color: tile.theme.semanticStatusColor("warn")
        }
        ShellLabel {
            width: parent.width
            visible: tile.resumeText.length > 0
            tokens: tile.tokens
            role: "mono"
            wrapMode: Text.WrapAnywhere
            text: tile.resumeText
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
