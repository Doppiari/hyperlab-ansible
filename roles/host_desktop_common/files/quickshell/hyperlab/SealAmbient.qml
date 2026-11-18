// The Sfere seal's atmosphere: its turning rings and ticks, dust and the
// host's light rays (ADR 0069).
//
// It carries no state. Its only inputs are the seal's geometry and one
// clock, so nothing about a network or a Machine can reach it: the motion is
// the same everywhere, never faster, brighter or denser near anything. A
// full turn takes minutes and the contrast stays low. While `active` is false
// nothing moves: the rings and rays stay where they are and the dust is not
// drawn. The caller stops `time` with reduced motion, a hidden view or the
// Ambient motion setting off. The component runs no timer of its own.

import QtQuick
import QtQuick.Shapes

Item {
    id: ambient

    required property var tokens
    required property var theme
    required property bool active
    // Seconds of ambient clock, advanced by the caller only while active.
    required property real time
    // The seal on the floor: its centre, radius and tilt (vertical squash).
    required property real centreX
    required property real floorY
    required property real radius
    required property real tilt
    // The host keystone, where the rays start.
    required property real hostX
    required property real hostY
    required property real hostRadius

    // One turn of the rings every four minutes; the rays every three and a
    // half. Both are the same for the whole seal.
    readonly property real ringTurnSeconds: 240
    readonly property real rayTurnSeconds: 210
    readonly property real ringAngle: (ambient.time / ambient.ringTurnSeconds) * 360 % 360
    readonly property real rayAngle: (ambient.time / ambient.rayTurnSeconds) * 360 % 360

    readonly property int moteCount: 36
    readonly property int tickCount: 90
    readonly property int rayCount: 14
    readonly property color tone: ambient.theme.textSecondary
    readonly property color clear: ambient.theme.alpha(ambient.theme.textSecondary, 0)

    // A fixed pseudo-random number in [0, 1) for a mote and a slot: the same
    // on every run, so a still frame is reproducible.
    function seed(index, slot) {
        const value = Math.sin(index * 12.9898 + slot * 78.233) * 43758.5453;
        return value - Math.floor(value);
    }

    // Where a mote is at a time, and how bright: it drifts round the seal
    // and rises from the floor, fading in and out. Speed comes from the
    // mote's own seed only.
    function moteAt(index, time) {
        const turn = ambient.seed(index, 1) * Math.PI * 2;
        const reach = 0.08 + 0.95 * Math.sqrt(ambient.seed(index, 2));
        const speed = 0.5 + ambient.seed(index, 3);
        const rise = 220;
        const height = (time * 12 * speed + ambient.seed(index, 4) * rise) % rise;
        const angle = turn + time * 0.05 * speed;

        return {
            "x": ambient.centreX + Math.cos(angle) * ambient.radius * reach,
            "y": ambient.floorY + Math.sin(angle) * ambient.radius * reach * ambient.tilt - height,
            "alpha": 0.28 * Math.sin(height / rise * Math.PI)
        };
    }

    Accessible.ignored: true

    // The host's light rays, turning slowly.
    Item {
        objectName: "sfere-ambient-rays"
        x: ambient.hostX
        y: ambient.hostY
        rotation: ambient.rayAngle

        Repeater {
            model: ambient.rayCount

            Shape {
                required property int index

                readonly property real angle: index * 360 / ambient.rayCount

                antialiasing: true

                ShapePath {
                    strokeWidth: -1
                    strokeColor: ambient.clear
                    fillGradient: RadialGradient {
                        centerX: 0
                        centerY: 0
                        centerRadius: ambient.hostRadius * 3
                        focalX: 0
                        focalY: 0
                        focalRadius: 0
                        GradientStop { position: 0; color: ambient.theme.alpha(ambient.tone, 0.10) }
                        GradientStop { position: 1; color: ambient.clear }
                    }
                    startX: 0
                    startY: 0

                    PathAngleArc {
                        centerX: 0
                        centerY: 0
                        radiusX: ambient.hostRadius * 3
                        radiusY: ambient.hostRadius * 3
                        startAngle: angle - 2
                        sweepAngle: 4
                        moveToStart: false
                    }
                }
            }
        }
    }

    // The turning rings and ticks of the seal, seen at the floor's tilt.
    Item {
        x: ambient.centreX
        y: ambient.floorY
        transform: Scale { yScale: ambient.tilt }

        Item {
            objectName: "sfere-ambient-rings"
            rotation: ambient.ringAngle

            Shape {
                antialiasing: true

                ShapePath {
                    strokeColor: ambient.theme.alpha(ambient.tone, 0.16)
                    strokeWidth: 1
                    fillColor: ambient.clear
                    strokeStyle: ShapePath.DashLine
                    dashPattern: [2, 6]

                    PathAngleArc {
                        centerX: 0; centerY: 0
                        radiusX: ambient.radius; radiusY: ambient.radius
                        startAngle: 0; sweepAngle: 360
                    }
                }

                ShapePath {
                    strokeColor: ambient.theme.alpha(ambient.tone, 0.22)
                    strokeWidth: 1
                    fillColor: ambient.clear

                    PathMultiline {
                        paths: {
                            const out = [];

                            for (let tick = 0; tick < ambient.tickCount; tick++) {
                                const angle = tick * 2 * Math.PI / ambient.tickCount;
                                const long = tick % 15 === 0;
                                const outer = ambient.radius * 1.06;
                                const inner = outer - ambient.radius * (long ? 0.035 : 0.015);

                                out.push([Qt.point(Math.cos(angle) * outer, Math.sin(angle) * outer),
                                          Qt.point(Math.cos(angle) * inner, Math.sin(angle) * inner)]);
                            }

                            return out;
                        }
                    }
                }
            }
        }

        // The inner dashed ring turns the other way, at the same speed.
        Item {
            rotation: -ambient.ringAngle

            Shape {
                antialiasing: true

                ShapePath {
                    strokeColor: ambient.theme.alpha(ambient.tone, 0.12)
                    strokeWidth: 1
                    fillColor: ambient.clear
                    strokeStyle: ShapePath.DashLine
                    dashPattern: [14, 10, 2, 10]

                    PathAngleArc {
                        centerX: 0; centerY: 0
                        radiusX: ambient.radius * 0.7; radiusY: ambient.radius * 0.7
                        startAngle: 0; sweepAngle: 360
                    }
                }
            }
        }
    }

    // Dust, only while the atmosphere moves.
    Repeater {
        objectName: "sfere-ambient-motes"
        model: ambient.active ? ambient.moteCount : 0

        Rectangle {
            required property int index

            readonly property var mote: ambient.moteAt(index, ambient.time)

            x: mote.x
            y: mote.y
            width: 1.5
            height: 1.5
            color: ambient.tone
            opacity: Math.max(0, mote.alpha)
        }
    }
}
