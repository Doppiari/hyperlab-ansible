// The panel under the Sfere seal (ADR 0069): the selected network on the
// left, its Machines on the right as the Machines view's cards, without
// their spheres. Every word is passed in by the view, which derives it from
// the sources; the panel draws and routes, nothing else. A card opens the
// existing Machine pane.

import QtQuick

Rectangle {
    id: panel

    required property var tokens
    required property var theme
    required property var icons
    // title, colour, subnet, summary, facts ([label, value]), rule, empty
    // words; null when no network can be shown.
    required property var detail
    required property var machines
    property string highlighted: ""
    // Shown instead of a network when the seal has none to show.
    property string absence: ""
    property bool offerCreate: false

    signal machineRequested(string identifier)
    signal createRequested()

    readonly property real factsWidth: Math.min(420, panel.width * 0.32)
    // The height the network's facts need, which the view gives the panel.
    readonly property real neededHeight: facts.height + panel.tokens.spaceLg * 2

    objectName: "sfere-panel"
    color: panel.theme.recess
    border.width: panel.tokens.borderSize
    border.color: panel.theme.hairline
    radius: panel.tokens.radiusSurface
    clip: true

    // The network.
    Column {
        id: facts

        objectName: "sfere-panel-network"
        x: panel.tokens.spaceXl
        y: panel.tokens.spaceLg
        width: panel.factsWidth - panel.tokens.spaceXl * 2
        spacing: panel.tokens.spaceXs
        visible: panel.detail !== null

        Row {
            spacing: panel.tokens.spaceSm

            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: panel.tokens.markerSize
                height: panel.tokens.spaceXl
                radius: 2
                color: panel.detail ? panel.detail.colour : panel.theme.textSecondary
            }

            ShellLabel {
                objectName: "sfere-panel-title"
                tokens: panel.tokens
                role: "heading"
                text: panel.detail ? panel.detail.title : ""
                color: panel.theme.textPrimary
            }
        }

        ShellLabel {
            objectName: "sfere-panel-subnet"
            tokens: panel.tokens
            role: "value"
            text: panel.detail ? panel.detail.subnet : ""
            color: panel.theme.textPrimary
        }

        ShellLabel {
            objectName: "sfere-panel-summary"
            width: parent.width
            tokens: panel.tokens
            role: "body"
            wrapMode: Text.Wrap
            text: panel.detail ? panel.detail.summary : ""
            color: panel.theme.textSecondary
        }

        Grid {
            columns: 2
            columnSpacing: panel.tokens.spaceXl
            rowSpacing: panel.tokens.spaceSm
            topPadding: panel.tokens.spaceSm

            Repeater {
                model: panel.detail ? panel.detail.facts : []

                Column {
                    required property var modelData

                    spacing: 2

                    ShellLabel {
                        tokens: panel.tokens
                        role: "meta"
                        text: modelData[0]
                        color: panel.theme.textQuiet
                    }

                    ShellLabel {
                        objectName: "sfere-fact-" + modelData[0]
                        tokens: panel.tokens
                        role: "mono"
                        text: modelData[1]
                        color: panel.theme.textPrimary
                    }
                }
            }
        }

        ShellDivider {
            width: parent.width
            vertical: false
            tokens: panel.tokens
            theme: panel.theme
        }

        // Three lines are kept for every rule, so selecting another network
        // never resizes the panel and the seal above it.
        ShellLabel {
            objectName: "sfere-panel-rule"
            width: parent.width
            height: Math.max(implicitHeight, contentHeight / Math.max(1, lineCount) * 3)
            tokens: panel.tokens
            role: "meta"
            wrapMode: Text.Wrap
            text: panel.detail ? panel.detail.rule : ""
            color: panel.theme.textSecondary
        }
    }

    ShellLabel {
        objectName: "sfere-panel-absence"
        x: panel.tokens.spaceXl
        y: panel.tokens.spaceLg
        width: panel.factsWidth - panel.tokens.spaceXl * 2
        visible: panel.detail === null
        tokens: panel.tokens
        role: "body"
        wrapMode: Text.Wrap
        text: panel.absence
        color: panel.theme.textSecondary
    }

    Rectangle {
        x: panel.factsWidth
        y: 0
        width: panel.tokens.borderSize
        height: panel.height
        color: panel.theme.hairline
    }

    // Its Machines.
    Flickable {
        id: cards

        objectName: "sfere-panel-cards"
        x: panel.factsWidth + panel.tokens.spaceXl
        y: panel.tokens.spaceLg
        width: panel.width - x - panel.tokens.spaceXl
        height: panel.height - panel.tokens.spaceLg * 2
        contentWidth: width
        contentHeight: flow.height
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Flow {
            id: flow

            width: cards.width
            spacing: panel.tokens.cardGap

            Repeater {
                model: panel.machines

                MachineTile {
                    required property var modelData

                    width: Math.max(panel.tokens.cardMinWidth,
                        Math.min(panel.tokens.cardMaxWidth,
                            (cards.width - panel.tokens.cardGap * 2) / 3))
                    tokens: panel.tokens
                    theme: panel.theme
                    icons: panel.icons
                    machine: modelData
                    sphereVisible: false
                    selected: String(modelData.name) === panel.highlighted
                    onActivated: panel.machineRequested(String(modelData.name))
                }
            }
        }

        // An empty network says so, in the network's own terms.
        ShellLabel {
            objectName: "sfere-panel-empty"
            width: cards.width
            visible: panel.detail !== null && panel.machines.length === 0
            tokens: panel.tokens
            role: "body"
            wrapMode: Text.Wrap
            text: panel.detail ? panel.detail.empty : ""
            color: panel.theme.textSecondary
        }
    }

    // No Machines at all: the one thing to do next.
    ShellControl {
        objectName: "sfere-create"
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: panel.tokens.spaceLg
        visible: panel.offerCreate
        tokens: panel.tokens
        theme: panel.theme
        accessibleName: "Create a Machine"

        content: [
            ShellLabel {
                anchors.verticalCenter: parent.verticalCenter
                tokens: panel.tokens
                role: "label"
                text: "Create a Machine"
                color: panel.theme.textPrimary
            }
        ]

        onActivated: panel.createRequested()
    }
}
