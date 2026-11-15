// HyperLab focus item (ADR 0064).
//
// Where am I typing? The item draws the answer the bar core gives in colour
// as a shape and words: the Machine's sphere with its name and domain
// ("dev-01 · dev"), the host's grey sphere with "Host", or the neutral
// outline with "Unknown" when focus cannot be placed. Colour is carried by
// the sphere only and never without the domain word; the words stay in the
// primary text tone.
// A proven Machine whose inventory state the sphere cannot draw keeps its
// domain and adds that state word beside the neutral outline (ADR 0064).
//
// The bar passes ShellState.focusedMachine after checking that the domain
// palette is complete: host resolution of the focused surface, never a
// guess made from a window name. It is deliberately not the GPU boot claim:
// which identity may hold the GPU this boot and
// which identity owns the window in front of you are different questions
// with different answers, and collapsing them is how a trust display starts
// lying.

import QtQuick

ShellControl {
    id: badge

    required property var icons
    required property var provenance
    required property var machine

    signal detailsRequested()

    readonly property bool resolved:
        badge.provenance && badge.provenance.available === true

    readonly property string identity:
        badge.resolved ? String(badge.provenance.identity) : ""

    // A managed-looking surface without valid host provenance is a finding,
    // not an absence; it reads Unknown with its reason in the accessible
    // name and in Diagnostics.
    readonly property bool unresolved:
        badge.provenance && badge.provenance.state === "unresolved"

    readonly property string kind:
        badge.machine ? String(badge.machine.kind) : "unknown"

    readonly property string stateWords:
        badge.kind === "machine" && !focusSphere.knownState
        ? (focusSphere.state.length > 0 ? focusSphere.state : "state not confirmed")
        : ""

    readonly property string words:
        badge.kind === "host" || badge.kind === "machine"
        ? String(badge.machine.words) + (badge.stateWords.length > 0 ? " · " + badge.stateWords : "")
        : "Unknown"

    readonly property string reason:
        badge.machine && badge.machine.reason ? String(badge.machine.reason) : ""

    flat: true

    accessibleName:
        badge.kind === "host"
        ? "Focus: host"
        : (badge.kind === "machine"
            ? "Focus: " + badge.machine.name + ", " + badge.machine.identity
              + ", " + (badge.machine.machineState.length > 0
                  ? badge.machine.machineState
                  : "state not confirmed")
            : "Focus unknown" + (badge.reason.length > 0 ? ": " + badge.reason : ""))

    content: [
        MachineSphere {
            id: focusSphere

            objectName: "focus-sphere"
            anchors.verticalCenter: parent.verticalCenter
            theme: badge.theme
            tokens: badge.tokens
            size: badge.tokens.iconBar
            isHost: badge.kind === "host"
            machineName: badge.kind === "machine" ? String(badge.machine.name) : ""
            domain:
                badge.kind === "host"
                ? "host"
                : (badge.kind === "machine" ? String(badge.machine.identity) : "")
            state:
                badge.kind === "host" || badge.kind === "machine"
                ? String(badge.machine.machineState)
                : "unclassified"
        },

        ShellLabel {
            objectName: "focus-words"
            anchors.verticalCenter: parent.verticalCenter
            tokens: badge.tokens
            role: "bar"
            font.weight: badge.kind === "unknown" ? Font.Normal : Font.Medium
            width: Math.min(implicitWidth, badge.tokens.navigationWidth)
            elide: Text.ElideMiddle
            text: badge.words
            color: badge.theme.textPrimary
        }
    ]

    onActivated: badge.detailsRequested()
}
