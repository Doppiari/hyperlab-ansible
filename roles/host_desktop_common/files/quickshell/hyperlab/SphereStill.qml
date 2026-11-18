// The still form of NetworkSphere: the same glass sphere without the shader.
//
// Drawn with QtQuick Shapes and gradients, so it renders under every Qt
// backend: a soft halo, a dark glass body brightening toward its rim,
// engraved latitude and longitude, the rim, the core and a specular
// highlight. A lit core is bright in the network's colour; a dark one is
// desaturated and dim; the host's core is silver. The character is a small
// fixed pattern in the core, so the network stays recognisable with no
// motion at all: 0 a heart, 1 one ring, 2 a swirl, 3 three bands, 4 sparks,
// 5 a lattice. Any other character draws no pattern.
//
// Every tone derives from `colour`; nothing here names a colour.

import QtQuick
import QtQuick.Shapes

Item {
    id: still

    required property color colour
    required property int character
    required property real lit
    required property bool selected
    required property point lightDirection
    required property real radiusShare

    readonly property real cx: still.width / 2
    readonly property real cy: still.height / 2
    readonly property real radius: Math.min(still.width, still.height) / 2 * still.radiusShare
    readonly property real edge: Math.min(still.width, still.height) / 2
    readonly property bool host: still.character === 0
    readonly property real coreRadius: still.radius * (still.host ? 0.56 : 0.5)
    readonly property real line: Math.max(1, still.radius * 0.022)
    readonly property bool bright: still.lit >= 0.5
    readonly property real lightLength: Math.sqrt(still.lightDirection.x * still.lightDirection.x
                                                  + still.lightDirection.y * still.lightDirection.y)
    readonly property real lightX: still.lightLength > 0 ? still.lightDirection.x / still.lightLength : -0.7071
    readonly property real lightY: still.lightLength > 0 ? still.lightDirection.y / still.lightLength : 0.7071

    // Tones. `muted` darkens the colour and keeps a share of its saturation;
    // the host's silver keeps none.
    function muted(factor, saturation) {
        const tone = Qt.darker(still.colour, factor);
        tone.hslSaturation = tone.hslSaturation * (still.host ? 0 : saturation);
        return tone;
    }
    function lifted(factor) {
        const tone = Qt.lighter(still.colour, factor);
        if (still.host)
            tone.hslSaturation = 0;
        return tone;
    }

    readonly property color clear: Qt.alpha(still.colour, 0)
    readonly property color glassDeep: still.muted(10, 0.6)
    readonly property color glassMid: Qt.darker(still.colour, 5 + 2 * (1 - still.lit))
    readonly property color glassEdge: Qt.darker(still.colour, 1.8 + 1.4 * (1 - still.lit))
    readonly property color rimTone: still.selected ? Qt.lighter(still.colour, 1.45)
        : still.bright ? still.colour : Qt.darker(still.colour, 1.7)
    readonly property color engraveTone: Qt.alpha(Qt.lighter(still.colour, 1.2), 0.2 + 0.2 * still.lit)
    readonly property color coreHot: still.lifted(1.75)
    readonly property color coreBody: still.host ? still.lifted(1.0) : still.colour
    readonly property color coreCool: still.muted(1.6, 1)
    readonly property color coreDarkInner: still.muted(2.2, 0.45)
    readonly property color coreDarkOuter: still.muted(4.2, 0.45)
    readonly property color patternTone: still.bright ? still.muted(2.4, 1) : still.muted(1.15, 0.5)

    Accessible.ignored: true

    // Halo, fading to nothing at the item's edge.
    Shape {
        anchors.fill: parent
        antialiasing: true

        ShapePath {
            strokeWidth: -1
            strokeColor: still.clear
            fillGradient: RadialGradient {
                centerX: still.cx
                centerY: still.cy
                centerRadius: still.edge
                focalX: still.cx
                focalY: still.cy
                focalRadius: still.radius * 0.96
                GradientStop { position: 0; color: Qt.alpha(still.colour, 0.08 + 0.3 * still.lit) }
                GradientStop { position: 1; color: still.clear }
            }

            PathAngleArc {
                centerX: still.cx
                centerY: still.cy
                radiusX: still.edge
                radiusY: still.edge
                startAngle: 0
                sweepAngle: 360
            }
        }
    }

    // Glass body: deep in the middle, brighter toward the rim (fresnel).
    Shape {
        anchors.fill: parent
        antialiasing: true

        ShapePath {
            strokeWidth: still.selected ? still.line * 2.2 : still.line * 1.4
            strokeColor: still.rimTone
            fillGradient: RadialGradient {
                centerX: still.cx
                centerY: still.cy
                centerRadius: still.radius
                focalX: still.cx
                focalY: still.cy
                focalRadius: 0
                GradientStop { position: 0; color: still.glassDeep }
                GradientStop { position: 0.7; color: still.glassMid }
                GradientStop { position: 0.94; color: still.glassEdge }
                GradientStop { position: 1; color: still.rimTone }
            }

            PathAngleArc {
                centerX: still.cx
                centerY: still.cy
                radiusX: still.radius - still.line
                radiusY: still.radius - still.line
                startAngle: 0
                sweepAngle: 360
            }
        }
    }

    // Engraving: three meridians, two parallels and the equator, seen from
    // slightly above.
    Shape {
        anchors.fill: parent
        antialiasing: true

        ShapePath {
            strokeWidth: still.line
            strokeColor: still.engraveTone
            fillColor: still.clear

            PathAngleArc {
                centerX: still.cx; centerY: still.cy
                radiusX: still.radius * 0.966; radiusY: still.radius * 0.97
                startAngle: 0; sweepAngle: 360
            }
            PathAngleArc {
                centerX: still.cx; centerY: still.cy
                radiusX: still.radius * 0.259; radiusY: still.radius * 0.97
                startAngle: 0; sweepAngle: 360
            }
            PathAngleArc {
                centerX: still.cx; centerY: still.cy
                radiusX: still.radius * 0.707; radiusY: still.radius * 0.97
                startAngle: 0; sweepAngle: 360
            }
            PathAngleArc {
                centerX: still.cx; centerY: still.cy - still.radius * 0.664
                radiusX: still.radius * 0.707; radiusY: still.radius * 0.243
                startAngle: 0; sweepAngle: 360
            }
            PathAngleArc {
                centerX: still.cx; centerY: still.cy + still.radius * 0.664
                radiusX: still.radius * 0.707; radiusY: still.radius * 0.243
                startAngle: 0; sweepAngle: 360
            }
        }

        ShapePath {
            strokeWidth: still.line * 1.6
            strokeColor: still.engraveTone
            fillColor: still.clear

            PathAngleArc {
                centerX: still.cx; centerY: still.cy
                radiusX: still.radius * 0.97; radiusY: still.radius * 0.343
                startAngle: 0; sweepAngle: 360
            }
        }
    }

    // Core glow and the dark core, always drawn.
    Shape {
        anchors.fill: parent
        antialiasing: true

        ShapePath {
            strokeWidth: -1
            strokeColor: still.clear
            fillGradient: RadialGradient {
                centerX: still.cx
                centerY: still.cy
                centerRadius: still.coreRadius * 1.5
                focalX: still.cx
                focalY: still.cy
                focalRadius: still.coreRadius
                GradientStop { position: 0; color: Qt.alpha(still.colour, 0.12 + 0.4 * still.lit) }
                GradientStop { position: 1; color: still.clear }
            }

            PathAngleArc {
                centerX: still.cx; centerY: still.cy
                radiusX: still.coreRadius * 1.5; radiusY: still.coreRadius * 1.5
                startAngle: 0; sweepAngle: 360
            }
        }

        ShapePath {
            strokeWidth: -1
            strokeColor: still.clear
            fillGradient: RadialGradient {
                centerX: still.cx
                centerY: still.cy
                centerRadius: still.coreRadius
                focalX: still.cx - still.coreRadius * 0.25
                focalY: still.cy - still.coreRadius * 0.25
                focalRadius: 0
                GradientStop { position: 0; color: still.coreDarkInner }
                GradientStop { position: 1; color: still.coreDarkOuter }
            }

            PathAngleArc {
                centerX: still.cx; centerY: still.cy
                radiusX: still.coreRadius; radiusY: still.coreRadius
                startAngle: 0; sweepAngle: 360
            }
        }
    }

    // The lit core over it, as bright as the sphere is lit.
    Shape {
        anchors.fill: parent
        antialiasing: true
        opacity: still.lit

        ShapePath {
            strokeWidth: -1
            strokeColor: still.clear
            fillGradient: RadialGradient {
                centerX: still.cx
                centerY: still.cy
                centerRadius: still.coreRadius
                focalX: still.cx - still.coreRadius * 0.2
                focalY: still.cy - still.coreRadius * 0.2
                focalRadius: 0
                GradientStop { position: 0; color: still.coreHot }
                GradientStop { position: 0.55; color: still.coreBody }
                GradientStop { position: 1; color: still.coreCool }
            }

            PathAngleArc {
                centerX: still.cx; centerY: still.cy
                radiusX: still.coreRadius; radiusY: still.coreRadius
                startAngle: 0; sweepAngle: 360
            }
        }
    }

    // 0 host: a heart.
    Shape {
        anchors.fill: parent
        antialiasing: true
        visible: still.character === 0

        ShapePath {
            strokeWidth: -1
            strokeColor: still.clear
            fillColor: still.patternTone

            PathAngleArc {
                centerX: still.cx; centerY: still.cy
                radiusX: still.coreRadius * 0.26; radiusY: still.coreRadius * 0.26
                startAngle: 0; sweepAngle: 360
            }
        }
    }

    // 1 calm: one ring.
    Shape {
        anchors.fill: parent
        antialiasing: true
        visible: still.character === 1

        ShapePath {
            strokeWidth: still.line * 1.4
            strokeColor: still.patternTone
            fillColor: still.clear

            PathAngleArc {
                centerX: still.cx; centerY: still.cy
                radiusX: still.coreRadius * 0.58; radiusY: still.coreRadius * 0.58
                startAngle: 0; sweepAngle: 360
            }
        }
    }

    // 2 swirling: an S through the middle.
    Shape {
        anchors.fill: parent
        antialiasing: true
        visible: still.character === 2

        ShapePath {
            strokeWidth: still.line * 1.4
            strokeColor: still.patternTone
            fillColor: still.clear
            capStyle: ShapePath.RoundCap
            startX: still.cx
            startY: still.cy - still.coreRadius * 0.72

            PathArc {
                x: still.cx; y: still.cy
                radiusX: still.coreRadius * 0.36; radiusY: still.coreRadius * 0.36
                direction: PathArc.Clockwise
            }
            PathArc {
                x: still.cx; y: still.cy + still.coreRadius * 0.72
                radiusX: still.coreRadius * 0.36; radiusY: still.coreRadius * 0.36
                direction: PathArc.Counterclockwise
            }
        }
    }

    // 3 banded: three bands.
    Shape {
        anchors.fill: parent
        antialiasing: true
        visible: still.character === 3

        ShapePath {
            strokeWidth: still.line * 1.4
            strokeColor: still.patternTone
            fillColor: still.clear
            capStyle: ShapePath.RoundCap

            PathMove { x: still.cx - still.coreRadius * 0.71; y: still.cy - still.coreRadius * 0.5 }
            PathLine { x: still.cx + still.coreRadius * 0.71; y: still.cy - still.coreRadius * 0.5 }
            PathMove { x: still.cx - still.coreRadius * 0.82; y: still.cy }
            PathLine { x: still.cx + still.coreRadius * 0.82; y: still.cy }
            PathMove { x: still.cx - still.coreRadius * 0.71; y: still.cy + still.coreRadius * 0.5 }
            PathLine { x: still.cx + still.coreRadius * 0.71; y: still.cy + still.coreRadius * 0.5 }
        }
    }

    // 4 flickering: five sparks.
    Shape {
        anchors.fill: parent
        antialiasing: true
        visible: still.character === 4

        ShapePath {
            strokeWidth: -1
            strokeColor: still.clear
            fillColor: still.patternTone

            PathAngleArc {
                centerX: still.cx - still.coreRadius * 0.45; centerY: still.cy - still.coreRadius * 0.35
                radiusX: still.coreRadius * 0.11; radiusY: still.coreRadius * 0.11
                startAngle: 0; sweepAngle: 360
            }
            PathAngleArc {
                centerX: still.cx + still.coreRadius * 0.4; centerY: still.cy - still.coreRadius * 0.5
                radiusX: still.coreRadius * 0.11; radiusY: still.coreRadius * 0.11
                startAngle: 0; sweepAngle: 360
            }
            PathAngleArc {
                centerX: still.cx + still.coreRadius * 0.05; centerY: still.cy + still.coreRadius * 0.1
                radiusX: still.coreRadius * 0.11; radiusY: still.coreRadius * 0.11
                startAngle: 0; sweepAngle: 360
            }
            PathAngleArc {
                centerX: still.cx - still.coreRadius * 0.3; centerY: still.cy + still.coreRadius * 0.5
                radiusX: still.coreRadius * 0.11; radiusY: still.coreRadius * 0.11
                startAngle: 0; sweepAngle: 360
            }
            PathAngleArc {
                centerX: still.cx + still.coreRadius * 0.5; centerY: still.cy + still.coreRadius * 0.35
                radiusX: still.coreRadius * 0.11; radiusY: still.coreRadius * 0.11
                startAngle: 0; sweepAngle: 360
            }
        }
    }

    // 5 lattice: a grid of four lines.
    Shape {
        anchors.fill: parent
        antialiasing: true
        visible: still.character === 5

        ShapePath {
            strokeWidth: still.line * 1.2
            strokeColor: still.patternTone
            fillColor: still.clear

            PathMove { x: still.cx - still.coreRadius * 0.78; y: still.cy - still.coreRadius * 0.4 }
            PathLine { x: still.cx + still.coreRadius * 0.78; y: still.cy - still.coreRadius * 0.4 }
            PathMove { x: still.cx - still.coreRadius * 0.78; y: still.cy + still.coreRadius * 0.4 }
            PathLine { x: still.cx + still.coreRadius * 0.78; y: still.cy + still.coreRadius * 0.4 }
            PathMove { x: still.cx - still.coreRadius * 0.4; y: still.cy - still.coreRadius * 0.78 }
            PathLine { x: still.cx - still.coreRadius * 0.4; y: still.cy + still.coreRadius * 0.78 }
            PathMove { x: still.cx + still.coreRadius * 0.4; y: still.cy - still.coreRadius * 0.78 }
            PathLine { x: still.cx + still.coreRadius * 0.4; y: still.cy + still.coreRadius * 0.78 }
        }
    }

    // Specular highlight, toward the light.
    Shape {
        anchors.fill: parent
        antialiasing: true

        ShapePath {
            strokeWidth: -1
            strokeColor: still.clear
            fillGradient: RadialGradient {
                centerX: still.cx + still.lightX * still.radius * 0.42
                centerY: still.cy - still.lightY * still.radius * 0.42
                centerRadius: still.radius * 0.17
                focalX: still.cx + still.lightX * still.radius * 0.42
                focalY: still.cy - still.lightY * still.radius * 0.42
                focalRadius: 0
                GradientStop { position: 0; color: Qt.alpha(Qt.lighter(still.colour, 2.6), still.bright ? 0.95 : 0.5) }
                GradientStop { position: 0.45; color: Qt.alpha(Qt.lighter(still.colour, 2.0), still.bright ? 0.4 : 0.18) }
                GradientStop { position: 1; color: still.clear }
            }

            PathAngleArc {
                centerX: still.cx + still.lightX * still.radius * 0.42
                centerY: still.cy - still.lightY * still.radius * 0.42
                radiusX: still.radius * 0.17
                radiusY: still.radius * 0.17
                startAngle: 0
                sweepAngle: 360
            }
        }
    }
}
