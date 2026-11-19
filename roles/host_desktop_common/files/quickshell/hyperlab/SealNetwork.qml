// One network of the Sfere seal: its glass sphere, its Machines on their
// tilted rings and its words (ADR 0069, ADR 0070).
//
// The sphere takes the network's palette colour and character from the
// caller. Its core is lit when a managed Machine in the network runs, and
// only a lit core follows `time`. Each managed Machine is an electron on a
// ring: bright while running, hollow otherwise, on a dashed ring when it is
// disposable. Past eight Machines the last ring stands for the rest and says
// how many.
//
// The live layer, each mark a fact that is true now:
//
//   motion   a running electron travels its ring at `orbitRate`, the same
//            for every Machine whatever its load; any other stands still
//   trail    behind a running electron with a load reading, a tapering
//            trail 0.4 + 1.8 x load radians long; no reading, no trail
//   GPU      a white token beside the electron of the Machine holding it
//   focus    a white ring round the electron of the Machine with the
//            foreground window, and two rings widening round the sphere
//
// Everything moves only with `liveTime`, which the view advances on its one
// clock and holds still with reduced motion.

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
    // Seconds of live motion, and the one angular speed of a running electron.
    property real liveTime: 0
    property real orbitRate: 0
    // The Machine with the foreground window is in this network.
    property bool focusWave: false
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

    // Where electron `index` is on its ring, as an angle: its own place, and
    // for a running Machine the distance travelled at the one shared speed.
    // The load never enters.
    function angleOf(index) {
        const row = net.network.rings[index];
        const base = index * 2.3 + net.place;

        return row && row.running === true ? base + net.liveTime * net.orbitRate : base;
    }

    // A point at `angle` on ring `index`, relative to the centre, and whether
    // it is on the near half.
    function ringPoint(index, angle) {
        const tilt = net.tiltOf(index) * Math.PI / 180;
        const ex = Math.cos(angle) * net.ringX;
        const ey = Math.sin(angle) * net.ringY;

        return {
            "x": ex * Math.cos(tilt) - ey * Math.sin(tilt),
            "y": ex * Math.sin(tilt) + ey * Math.cos(tilt),
            "front": Math.sin(angle) > 0
        };
    }

    function electronAt(index) {
        return net.ringPoint(index, net.angleOf(index));
    }

    // The trail's angular length: only for a running Machine with a load.
    function trailSpan(index) {
        const row = net.network.rings[index];

        return row && row.running === true && typeof row.load === "number" ? 0.4 + 1.8 * row.load : 0;
    }

    // The trail behind electron `index` as two closed outlines, the part on
    // the near half and the part on the far half: a ribbon that narrows from
    // the electron's width to nothing.
    function trailOf(index) {
        const span = net.trailSpan(index);
        const out = { "front": [], "back": [] };

        if (span <= 0)
            return out;

        const head = net.angleOf(index);
        const steps = 16;
        const runs = [];

        for (let step = 0; step <= steps; step++) {
            const angle = head - span * step / steps;
            const point = net.ringPoint(index, angle);
            const ahead = net.ringPoint(index, angle + 0.01);
            const length = Math.hypot(ahead.x - point.x, ahead.y - point.y) || 1;
            const half = net.electron * 0.8 * (1 - step / steps);
            const sample = {
                "front": point.front,
                "left": Qt.point(point.x - (ahead.y - point.y) / length * half,
                                 point.y + (ahead.x - point.x) / length * half),
                "right": Qt.point(point.x + (ahead.y - point.y) / length * half,
                                  point.y - (ahead.x - point.x) / length * half)
            };

            if (runs.length === 0 || runs[runs.length - 1].front !== sample.front)
                runs.push({ "front": sample.front, "samples": runs.length > 0
                    ? [runs[runs.length - 1].samples[runs[runs.length - 1].samples.length - 1]] : [] });

            runs[runs.length - 1].samples.push(sample);
        }

        for (const run of runs) {
            const outline = run.samples.map(sample => sample.left)
                .concat(run.samples.slice().reverse().map(sample => sample.right));

            if (outline.length > 2)
                out[run.front ? "front" : "back"] = outline.concat([outline[0]]);
        }

        return out;
    }

    // One Machine: bright while running, hollow otherwise, with the GPU
    // token and the focus ring where they are true, and its words on hover or
    // under the keyboard.
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

        // The foreground window is this Machine's.
        Rectangle {
            objectName: dot.machine.focused === true ? "sfere-focus-ring-" + dot.machine.name : ""
            anchors.centerIn: parent
            visible: dot.machine.focused === true
            width: parent.width + 14
            height: width
            radius: width / 2
            color: net.clear
            border.width: 1.2
            border.color: net.theme.alpha(net.theme.textPrimary, 0.9)
        }

        // The GPU is lent to this Machine.
        Rectangle {
            objectName: dot.machine.gpu === true ? "sfere-gpu-token-" + dot.machine.name : ""
            visible: dot.machine.gpu === true
            x: parent.width + 3
            y: -height - 1
            width: 7
            height: 7
            rotation: 45
            color: net.theme.textPrimary
        }

        HoverHandler {
            id: hover

            margin: 6
        }

        Rectangle {
            objectName: "sfere-tip-" + dot.machine.name
            visible: hover.hovered || net.machineCursor === dot.machine.name
            x: parent.width + 8
            y: -height / 2 + parent.height / 2
            z: 10
            width: tipWords.width + net.tokens.spaceSm * 2
            height: tipWords.height + net.tokens.spaceXs * 2
            radius: net.tokens.radiusControl
            color: net.theme.alpha(net.theme.base, 0.9)
            border.width: 1
            border.color: net.theme.alpha(net.colour, 0.5)

            ShellLabel {
                id: tipWords

                x: net.tokens.spaceSm
                y: net.tokens.spaceXs
                tokens: net.tokens
                role: "meta"
                text: String(dot.machine.words || "")
                color: net.theme.textPrimary
            }
        }
    }

    // A running Machine's trail with a load reading, on one half of its ring.
    component Trail: Shape {
        id: trail

        property var outline: []
        property string machine: ""

        antialiasing: true

        ShapePath {
            objectName: "sfere-path-trail"
            strokeWidth: -1
            strokeColor: net.clear
            fillColor: trail.outline.length > 0 ? net.theme.alpha(net.colour, 0.55) : net.clear

            PathPolyline { path: trail.outline }
        }
    }

    // The foreground window's network: two rings widening round the sphere,
    // still with reduced motion.
    Repeater {
        model: net.focusWave ? 2 : 0

        Rectangle {
            required property int index

            readonly property real phase: (net.liveTime * 0.55 + index * 0.5) % 1

            objectName: "sfere-wave-" + net.network.name
            x: (net.width - width) / 2
            y: (net.height - height) / 2
            z: 2
            width: net.radius * 2 * (1.25 + phase)
            height: width
            radius: width / 2
            color: net.clear
            border.width: 1.5
            border.color: net.theme.alpha(net.colour, (1 - phase) * 0.6 + 0.1)
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
            readonly property var trail: back.modelData.more > 0 ? { "front": [], "back": [] }
                : net.trailOf(back.index)

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

            Trail {
                machine: String(back.modelData.name)
                outline: back.trail.back
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
            readonly property var trail: ring.more ? { "front": [], "back": [] } : net.trailOf(ring.index)
            // For the contract: where this electron is on its ring.
            readonly property real angle: net.angleOf(ring.index)
            readonly property real trailSpan: ring.more ? 0 : net.trailSpan(ring.index)
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

            Trail {
                machine: String(ring.modelData.name)
                outline: ring.trail.front
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
