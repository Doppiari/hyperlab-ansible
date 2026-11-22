// HyperLab machine list row (V447-C9.3).
//
// The dense alternative to the card grid, used when an inventory is large
// enough that a grid stops being readable. It carries the same facts in the
// same host projection, with an identity mark beside the name, operating system,
// state, memory allocation and GPU relationship.

import QtQuick

Rectangle {
    id: row
    objectName: "machine-list-row-" + row.machine.name

    required property var tokens
    required property var theme
    required property var icons
    required property var machine

    property bool selected: false

    signal activated()

    readonly property string relation:
        String(row.machine.gpu_relation)

    readonly property string hardwareText:
        row.relation === "held" ? "Holds the GPU"
        : row.relation === "configured" ? "Passthrough configured"
        : row.relation === "none" ? "No passthrough" : "Passthrough unknown"

    readonly property string memoryText:
        typeof row.machine.memory_mb === "number"
        ? (row.machine.memory_mb >= 1024
            ? (row.machine.memory_mb / 1024).toFixed(
                row.machine.memory_mb % 1024 === 0 ? 0 : 1
              ) + " GiB"
            : row.machine.memory_mb + " MiB")
        : "unknown"

    readonly property string allocation: "Memory " + row.memoryText
        + " · vCPU " + (row.machine.vcpus ?? "unknown") + " · Network "
        + (typeof row.machine.networks?.join === "function" ? row.machine.networks.join(", ") || "none" : "unknown")

    radius: row.tokens.radiusControl

    color:
        row.selected
        ? row.theme.fillSelected
        : (
            press.pressed
            ? row.theme.fillPressed
            : (hover.hovered ? row.theme.fillHover : row.theme.alpha(row.theme.textPrimary, 0))
        )

    border.width:
        row.activeFocus || row.selected ? row.tokens.focusOutline : 0
    border.color:
        row.activeFocus ? row.theme.focusRing : row.theme.boundaryStrong

    activeFocusOnTab: true

    Accessible.role: Accessible.Button
    Accessible.name:
        String(row.machine.name)
        + ", " + row.theme.provenanceLabel(row.machine.provenance)
        + ", " + row.icons.machineStateWord(row.machine.state)
        + ", OS " + (row.machine.os || "unknown") + ", " + row.allocation + ", " + gpuRelation.text
    Accessible.onPressAction: row.activated()

    Behavior on color {
        ColorAnimation {
            duration: row.tokens.motionHover
        }
    }

    Row {
        id: identityLine
        readonly property real labelWidth: Math.max(0, width - mark.width - chip.width - spacing * 3)
        anchors.left: parent.left
        anchors.right: gpuRelation.left
        anchors.leftMargin: row.tokens.spaceMd
        anchors.rightMargin: row.tokens.spaceMd
        anchors.top: parent.top
        anchors.topMargin: row.tokens.spaceXs
        spacing: row.tokens.spaceMd

        ProvenanceMarker {
            id: mark
            anchors.verticalCenter: parent.verticalCenter
            tokens: row.tokens
            theme: row.theme
            identity: row.machine.provenance
        }

        ShellLabel {
            anchors.verticalCenter: parent.verticalCenter
            width: identityLine.labelWidth * 0.62
            tokens: row.tokens
            role: "body"
            font.weight: Font.Medium
            text: String(row.machine.name)
            color: row.theme.textPrimary
        }

        // From the host's image manifest, never from the guest.
        ShellLabel {
            anchors.verticalCenter: parent.verticalCenter
            width: identityLine.labelWidth * 0.38
            tokens: row.tokens
            role: "meta"
            text:
                typeof row.machine.os === "string" && row.machine.os.length > 0
                ? row.machine.os
                : "OS unknown"
            color: row.theme.textQuiet
        }

        StateChip {
            id: chip
            anchors.verticalCenter: parent.verticalCenter
            tokens: row.tokens
            theme: row.theme
            icons: row.icons
            state: String(row.machine.state)
        }
    }

    ShellLabel {
        anchors.left: identityLine.left
        anchors.right: parent.right
        anchors.rightMargin: row.tokens.spaceMd
        anchors.bottom: parent.bottom
        anchors.bottomMargin: row.tokens.spaceXs
        tokens: row.tokens
        role: "mono"
        text: row.allocation
        color: row.theme.textSecondary
    }

    ShellLabel {
        id: gpuRelation

        anchors.right: parent.right
        anchors.rightMargin: row.tokens.spaceMd
        anchors.verticalCenter: identityLine.verticalCenter
        width: Math.min(implicitWidth, row.width / 3)
        tokens: row.tokens
        role: "meta"
        text: row.machine.lifecycle === "disposable"
            ? (row.machine.runtime_present === true && row.machine.runtime_drift === false
                ? "Disposable · discarded at shutdown" : "Disposable configured · discard unknown")
                + (row.relation === "held" || row.relation === "configured" ? " · " + row.hardwareText : "")
            : row.hardwareText
        color: row.theme.textQuiet
    }

    HoverHandler {
        id: hover
        cursorShape: Qt.PointingHandCursor
    }

    TapHandler {
        id: press
        onTapped: row.activated()
    }

    Keys.onPressed: event => {
        if (
            event.key === Qt.Key_Return
            || event.key === Qt.Key_Enter
            || event.key === Qt.Key_Space
        ) {
            row.activated();
            event.accepted = true;
        }
    }
}
