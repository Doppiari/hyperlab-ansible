// The engraved seal on the floor of the Sfere view (ADR 0069).
//
// A still drawing seen in perspective: concentric rings, tick marks, a faint
// chord between every pair of network places, a pool of light under each
// network (stronger under a lit one) and each network's name, subnet and
// mode engraved along the outer ring. Nothing here moves; the turning rings
// belong to SealAmbient. Every tone comes from the theme or from the place's
// palette colour, passed by the caller.

import QtQuick
import QtQuick.Shapes

Item {
    id: floor

    required property var tokens
    required property var theme
    required property real centreX
    required property real floorY
    required property real radius
    required property real tilt
    // One entry per network: name, x and y of its place on the floor, angle
    // (radians), colour, lit, size (its sphere's radius) and words.
    required property var places

    readonly property color tone: floor.theme.textSecondary
    readonly property color clear: floor.theme.alpha(floor.theme.textSecondary, 0)

    Accessible.ignored: true

    // The seal's rings and still ticks.
    Item {
        x: floor.centreX
        y: floor.floorY
        transform: Scale { yScale: floor.tilt }

        Shape {
            antialiasing: true

            ShapePath {
                strokeWidth: -1
                strokeColor: floor.clear
                fillGradient: RadialGradient {
                    centerX: 0; centerY: 0
                    centerRadius: floor.radius * 1.15
                    focalX: 0; focalY: 0; focalRadius: 0
                    GradientStop { position: 0; color: floor.theme.alpha(floor.tone, 0.10) }
                    GradientStop { position: 1; color: floor.clear }
                }

                PathAngleArc {
                    centerX: 0; centerY: 0
                    radiusX: floor.radius * 1.15; radiusY: floor.radius * 1.15
                    startAngle: 0; sweepAngle: 360
                }
            }

            ShapePath {
                strokeColor: floor.theme.alpha(floor.tone, 0.30)
                strokeWidth: 1
                fillColor: floor.clear

                PathAngleArc {
                    centerX: 0; centerY: 0
                    radiusX: floor.radius * 1.06; radiusY: floor.radius * 1.06
                    startAngle: 0; sweepAngle: 360
                }
            }

            ShapePath {
                strokeColor: floor.theme.alpha(floor.tone, 0.18)
                strokeWidth: 1
                fillColor: floor.clear

                PathAngleArc {
                    centerX: 0; centerY: 0
                    radiusX: floor.radius * 0.74; radiusY: floor.radius * 0.74
                    startAngle: 0; sweepAngle: 360
                }
                PathAngleArc {
                    centerX: 0; centerY: 0
                    radiusX: floor.radius * 0.36; radiusY: floor.radius * 0.36
                    startAngle: 0; sweepAngle: 360
                    moveToStart: true
                }
            }

            ShapePath {
                strokeColor: floor.theme.alpha(floor.tone, 0.12)
                strokeWidth: 1
                fillColor: floor.clear
                strokeStyle: ShapePath.DashLine
                dashPattern: [3, 5]

                PathAngleArc {
                    centerX: 0; centerY: 0
                    radiusX: floor.radius * 0.32; radiusY: floor.radius * 0.32
                    startAngle: 0; sweepAngle: 360
                }
            }
        }
    }

    // A faint chord between every pair of network places.
    Shape {
        objectName: "sfere-floor-chords"
        antialiasing: true

        ShapePath {
            strokeColor: floor.theme.alpha(floor.tone, 0.10)
            strokeWidth: 1
            fillColor: floor.clear

            PathMultiline {
                paths: {
                    const out = [];

                    for (let a = 0; a < floor.places.length; a++) {
                        for (let b = a + 1; b < floor.places.length; b++)
                            out.push([Qt.point(floor.places[a].x, floor.places[a].y),
                                      Qt.point(floor.places[b].x, floor.places[b].y)]);
                    }

                    return out;
                }
            }
        }
    }

    // Under each network: its pool of light and two engraved rings.
    Repeater {
        model: floor.places

        Item {
            id: place

            required property var modelData

            objectName: "sfere-pool-" + modelData.name
            x: modelData.x
            y: modelData.y
            transform: Scale { yScale: floor.tilt }

            readonly property real reach: place.modelData.size * 2.4
            // The pool is the only mark here that follows state: brighter
            // under a lit network.
            readonly property real strength: 0.10 + 0.22 * place.modelData.lit

            Shape {
                antialiasing: true

                ShapePath {
                    strokeWidth: -1
                    strokeColor: floor.clear
                    fillGradient: RadialGradient {
                        centerX: 0; centerY: 0
                        centerRadius: place.reach
                        focalX: 0; focalY: 0; focalRadius: 0
                        GradientStop { position: 0; color: floor.theme.alpha(place.modelData.colour, place.strength) }
                        GradientStop { position: 1; color: floor.theme.alpha(place.modelData.colour, 0) }
                    }

                    PathAngleArc {
                        centerX: 0; centerY: 0
                        radiusX: place.reach; radiusY: place.reach
                        startAngle: 0; sweepAngle: 360
                    }
                }

                ShapePath {
                    strokeColor: floor.theme.alpha(place.modelData.colour, 0.5)
                    strokeWidth: 1
                    fillColor: floor.clear

                    PathAngleArc {
                        centerX: 0; centerY: 0
                        radiusX: place.modelData.size * 0.9; radiusY: place.modelData.size * 0.9
                        startAngle: 0; sweepAngle: 360
                    }
                }

                ShapePath {
                    strokeColor: floor.theme.alpha(place.modelData.colour, 0.25)
                    strokeWidth: 1
                    fillColor: floor.clear

                    PathAngleArc {
                        centerX: 0; centerY: 0
                        radiusX: place.modelData.size * 1.25; radiusY: place.modelData.size * 1.25
                        startAngle: 0; sweepAngle: 360
                    }
                }
            }
        }
    }

    // Each network's name, subnet and mode engraved along the outer ring,
    // read from left to right on both halves.
    Repeater {
        model: floor.places

        Item {
            id: engraving

            required property var modelData

            readonly property string words: engraving.modelData.words
            readonly property bool lower: Math.sin(engraving.modelData.angle) > 0
            // The angle one letter takes on the ring.
            readonly property real step: 0.0105

            objectName: "sfere-engraving-" + modelData.name

            Repeater {
                model: engraving.words.length

                ShellLabel {
                    required property int index

                    readonly property int place: engraving.lower
                        ? engraving.words.length - 1 - index : index
                    readonly property real angle: engraving.modelData.angle
                        - engraving.step * (engraving.words.length - 1) / 2
                        + engraving.step * place

                    x: floor.centreX + Math.cos(angle) * floor.radius * 1.13 - width / 2
                    y: floor.floorY + Math.sin(angle) * floor.radius * 1.13 * floor.tilt - height / 2
                    rotation: angle * 180 / Math.PI + (engraving.lower ? -90 : 90)
                    transform: Scale {
                        origin.x: width / 2
                        origin.y: height / 2
                        yScale: 0.6 + 0.4 * Math.abs(Math.sin(angle))
                    }
                    tokens: floor.tokens
                    role: "label"
                    text: engraving.words.charAt(index)
                    color: floor.theme.alpha(engraving.modelData.colour, 0.6)
                    Accessible.ignored: true
                }
            }
        }
    }
}
