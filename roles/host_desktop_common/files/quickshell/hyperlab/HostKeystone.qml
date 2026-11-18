// The host at the centre of the Sfere seal (ADR 0056, ADR 0069).
//
// Geometry B, drawn by IsolationGlyph itself: the two blades and the
// containment ring keep their named proportions, nothing here retypes them.
// The glyph's core is left empty and a glass NetworkSphere of character 0
// (the host's silver core) sits in its place, at the core's radius. The ring
// carries one port per network the caller passes, at the angle of that
// network's spoke: an open port, or a sealed one (a circle with a slash) for
// an isolated network. Each blade is engraved with one line of words that
// are true of the host, read clockwise and centred on the blade; letters
// that would reach the cut are left out.
//
// `beat` is the core's light, 0..1, which the caller derives from the
// freshness of its sources; the core itself never moves on its own.

import QtQuick
import QtQuick.Shapes

Item {
    id: keystone

    required property var tokens
    required property var theme
    // R, the outer radius of the blades.
    required property real radius
    // name, angle (radians, screen coordinates), sealed, colour, lit
    required property var ports
    required property real beat
    // The left blade's words, then the right blade's.
    required property var engravings
    property real textureScale: 1

    readonly property color metal: keystone.theme.provenanceColor("host")
    readonly property color clear: keystone.theme.alpha(keystone.theme.textPrimary, 0)

    // The glyph's own measures, for the ports, the core and the contract.
    readonly property real outerRadius: glyph.outerRadius
    readonly property real innerRadius: glyph.innerRadius
    readonly property real cutOffset: glyph.cutOffset
    readonly property real ringRadius: glyph.outerRadius * glyph.ringRadiusRatio
    readonly property real ringStroke: glyph.strokeWidth
    readonly property real coreRadius: glyph.coreRadius
    readonly property real portSize: Math.max(keystone.tokens.markerSize + 3, keystone.radius * 0.1)

    width: keystone.radius * 2
    height: keystone.radius * 2
    Accessible.ignored: true

    IsolationGlyph {
        id: glyph

        objectName: "sfere-host-glyph"
        anchors.centerIn: parent
        size: Math.round(keystone.radius / glyph.radiusRatio)
        stroke: keystone.metal
        core: keystone.clear
    }

    // The engraving: one letter at a time along the middle of the annulus,
    // centred on its blade (the left one at 180 degrees, the right at 0).
    // A blade's words close up to fit its arc, so no letter reaches the cut.
    readonly property real engravingRadius: (glyph.innerRadius + glyph.outerRadius) / 2
    readonly property real letterStep:
        Math.max(letterProbe.width, glyph.outerRadius * 0.08) / keystone.engravingRadius
    readonly property real bladeArc: 2 * Math.acos(Math.min(1,
        (glyph.cutOffset + letterProbe.height * 0.6) / keystone.engravingRadius))
    readonly property var letters: {
        const out = [];

        for (let blade = 0; blade < 2; blade++) {
            const words = String(keystone.engravings[blade] || "");
            const middle = blade === 0 ? Math.PI : 0;
            const step = Math.min(keystone.letterStep, keystone.bladeArc / Math.max(1, words.length));

            for (let index = 0; index < words.length; index++)
                out.push({
                    "letter": words.charAt(index),
                    "angle": middle + (index - (words.length - 1) / 2) * step
                });
        }

        return out;
    }

    ShellLabel {
        id: letterProbe

        opacity: 0
        tokens: keystone.tokens
        role: "label"
        text: "M"
        Accessible.ignored: true
    }

    Repeater {
        objectName: "sfere-host-engraving"
        model: keystone.letters

        ShellLabel {
            required property var modelData

            readonly property real along: Math.cos(modelData.angle) * keystone.engravingRadius

            x: keystone.width / 2 + along - width / 2
            y: keystone.height / 2 + Math.sin(modelData.angle) * keystone.engravingRadius - height / 2
            rotation: modelData.angle * 180 / Math.PI + 90
            tokens: keystone.tokens
            role: "label"
            text: modelData.letter
            color: keystone.theme.alpha(keystone.theme.textPrimary, 0.35)
            Accessible.ignored: true
        }
    }

    NetworkSphere {
        id: core

        objectName: "sfere-host-core"
        anchors.centerIn: parent
        width: glyph.coreRadius * 2 / core.radiusShare
        height: width
        colour: keystone.metal
        character: 0
        lit: keystone.beat
        time: 0
        textureScale: keystone.textureScale
    }

    // One port per network on the ring.
    Repeater {
        model: keystone.ports

        Item {
            id: port

            required property var modelData

            readonly property string network: port.modelData.name
            readonly property bool sealed: port.modelData.sealed === true

            objectName: "sfere-port-" + port.network
            x: keystone.width / 2 + Math.cos(port.modelData.angle) * keystone.ringRadius - width / 2
            y: keystone.height / 2 + Math.sin(port.modelData.angle) * keystone.ringRadius - height / 2
            width: keystone.portSize
            height: keystone.portSize

            Shape {
                anchors.fill: parent
                antialiasing: true

                // An open port: a lit point in the network's colour.
                ShapePath {
                    strokeWidth: -1
                    strokeColor: keystone.clear
                    fillColor: port.sealed ? keystone.clear
                        : keystone.theme.mix(port.modelData.colour, keystone.theme.textPrimary, 0.5)

                    PathAngleArc {
                        centerX: port.width / 2; centerY: port.height / 2
                        radiusX: port.width * 0.22; radiusY: port.width * 0.22
                        startAngle: 0; sweepAngle: 360
                    }
                }

                ShapePath {
                    strokeColor: port.modelData.colour
                    strokeWidth: 1.3
                    fillColor: keystone.clear

                    PathAngleArc {
                        centerX: port.width / 2; centerY: port.height / 2
                        radiusX: port.width / 2 - 1; radiusY: port.width / 2 - 1
                        startAngle: 0; sweepAngle: 360
                    }
                }

                // A sealed port: the slash across it.
                ShapePath {
                    strokeColor: port.sealed ? port.modelData.colour : keystone.clear
                    strokeWidth: 1.3
                    fillColor: keystone.clear
                    startX: port.width * 0.18
                    startY: port.height * 0.82

                    PathLine { x: port.width * 0.82; y: port.height * 0.18 }
                }
            }
        }
    }
}
