// One network of the Sfere seal: its glass sphere, its Machines on their
// tilted rings and its words (ADR 0069).
//
// The sphere takes the network's palette colour and character from the
// caller. Its core is lit when a managed Machine in the network runs, and
// only a lit core follows `time`. Each managed Machine is an electron on a
// ring, still in this view: bright while running, hollow otherwise, on a
// dashed ring when it is disposable. Past eight Machines the last ring
// stands for the rest and says how many. Nothing here moves on its own.

import QtQuick
import QtQuick.Shapes

Item {
    id: net

    required property var tokens
    required property var theme
    // name, title, colour, character, lit, rings, words
    required property var network
    required property int place
    // The sphere's radius in pixels.
    required property real radius
    required property real time
    property real textureScale: 1
    property bool selected: false
    property string machineCursor: ""
    property bool labelBelow: false
    // How far under the sphere's centre its words start, when below.
    property real labelDrop: net.radius * 1.62 + net.tokens.spaceXs

    readonly property color colour: net.network.colour
    readonly property color clear: net.theme.alpha(net.network.colour, 0)
    readonly property real ringX: net.radius * 1.62
    readonly property real ringY: net.radius * 0.5
    readonly property real electron: Math.max(3.5, net.radius * 0.085)
    readonly property real labelTop: net.labelBelow
        ? net.height / 2 + net.labelDrop
        : net.height / 2 - net.radius * 1.62 - words.height - net.tokens.spaceXs

    width: net.radius * 2.4
    height: net.radius * 2.4
    Accessible.ignored: true

    function tiltOf(index) {
        return index / Math.max(1, net.network.rings.length) * 180 + 180 / 7;
    }

    // Where electron `index` sits on its ring, relative to the centre, and
    // whether it is on the near half.
    function electronAt(index) {
        const angle = index * 2.3 + net.place;
        const tilt = net.tiltOf(index) * Math.PI / 180;
        const ex = Math.cos(angle) * net.ringX;
        const ey = Math.sin(angle) * net.ringY;

        return {
            "x": ex * Math.cos(tilt) - ey * Math.sin(tilt),
            "y": ex * Math.sin(tilt) + ey * Math.cos(tilt),
            "front": Math.sin(angle) > 0
        };
    }

    // One Machine, still: bright while running, hollow otherwise.
    component Electron: Rectangle {
        id: dot

        property var machine: ({})
        property var spot: ({ "x": 0, "y": 0, "front": true })

        objectName: "sfere-electron-" + dot.machine.name
        x: dot.spot.x - width / 2
        y: dot.spot.y - height / 2
        width: net.electron * 2
        height: width
        radius: width / 2
        color: dot.machine.running === true
            ? net.theme.mix(net.colour, net.theme.textPrimary, 0.7) : net.theme.workspace
        border.width: dot.machine.running === true ? 0 : 1.2
        border.color: net.colour
        opacity: dot.spot.front ? 1 : 0.55

        // The keyboard's Machine inside an entered network.
        Rectangle {
            anchors.centerIn: parent
            visible: net.machineCursor === dot.machine.name
            width: parent.width + 10
            height: width
            radius: width / 2
            color: net.clear
            border.width: net.tokens.focusOutline
            border.color: net.theme.focusRing
        }
    }

    // The far half of every ring and the electrons on it, behind the sphere.
    Repeater {
        model: net.network.rings

        Item {
            id: back

            required property var modelData
            required property int index

            readonly property var spot: net.electronAt(back.index)

            x: net.width / 2
            y: net.height / 2
            z: -1

            Item {
                rotation: net.tiltOf(back.index)

                Shape {
                    antialiasing: true

                    ShapePath {
                        strokeColor: net.theme.alpha(net.colour, 0.18 + 0.17 * (back.modelData.running ? 1 : 0))
                        strokeWidth: 1
                        fillColor: net.clear
                        strokeStyle: back.modelData.disposable ? ShapePath.DashLine : ShapePath.SolidLine
                        dashPattern: [3, 4]

                        PathAngleArc {
                            centerX: 0; centerY: 0
                            radiusX: net.ringX; radiusY: net.ringY
                            startAngle: 180; sweepAngle: 180
                        }
                    }
                }
            }

            Electron {
                visible: !(back.modelData.more > 0) && !back.spot.front
                machine: back.modelData
                spot: back.spot
            }
        }
    }

    NetworkSphere {
        id: sphere

        objectName: "sfere-sphere-" + net.network.name
        anchors.fill: parent
        colour: net.colour
        character: net.network.character
        lit: net.network.lit ? 1 : 0
        selected: net.selected
        time: net.time
        turn: net.place * 1.3
        textureScale: net.textureScale
    }

    // The near half of every ring, the electrons on it and, on the last ring
    // of a crowded network, the count of the Machines it stands for.
    Repeater {
        model: net.network.rings

        Item {
            id: ring

            required property var modelData
            required property int index

            readonly property var spot: net.electronAt(ring.index)
            readonly property bool running: ring.modelData.running === true
            readonly property bool more: ring.modelData.more > 0

            objectName: "sfere-ring-" + net.network.name + "-" + ring.index
            x: net.width / 2
            y: net.height / 2
            z: 1

            Item {
                rotation: net.tiltOf(ring.index)

                Shape {
                    antialiasing: true

                    ShapePath {
                        strokeColor: net.theme.alpha(net.colour, 0.3 + 0.3 * (ring.running ? 1 : 0))
                        strokeWidth: 1
                        fillColor: net.clear
                        strokeStyle: ring.modelData.disposable ? ShapePath.DashLine : ShapePath.SolidLine
                        dashPattern: [3, 4]

                        PathAngleArc {
                            centerX: 0; centerY: 0
                            radiusX: net.ringX; radiusY: net.ringY
                            startAngle: 0; sweepAngle: 180
                        }
                    }
                }
            }

            Electron {
                visible: !ring.more && ring.spot.front
                machine: ring.modelData
                spot: ring.spot
            }

            ShellLabel {
                objectName: ring.more ? "sfere-more-" + net.network.name : ""
                visible: ring.more
                x: ring.spot.x - width / 2
                y: ring.spot.y - height / 2
                tokens: net.tokens
                role: "label"
                text: "+" + ring.modelData.more
                color: net.theme.textPrimary
            }
        }
    }

    Column {
        id: words

        objectName: "sfere-words-" + net.network.name
        x: (net.width - width) / 2
        y: net.labelTop
        z: 3
        spacing: 2

        ShellLabel {
            anchors.horizontalCenter: parent.horizontalCenter
            tokens: net.tokens
            role: "section"
            text: net.network.title
            color: net.theme.textPrimary
        }

        ShellLabel {
            objectName: "sfere-state-" + net.network.name
            anchors.horizontalCenter: parent.horizontalCenter
            tokens: net.tokens
            role: "meta"
            text: net.network.words
            color: net.network.isolated ? net.colour : net.theme.textSecondary
        }
    }
}
