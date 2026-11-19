// One spoke of the Sfere seal: from a network's port on the host ring to its
// sphere (ADR 0069). Machines talk only through the host, so every network
// has exactly one. An isolated network's spoke is broken: two dashed ends, a
// gap and a seal (a circle with a slash) in the middle. A spoke is drawn,
// never animated, and it is not a proof of reachability.

import QtQuick
import QtQuick.Shapes

Shape {
    id: spoke

    required property var theme
    required property string network
    required property real fromX
    required property real fromY
    required property real toX
    required property real toY
    required property color colour
    required property bool broken
    property bool selected: false
    property real lit: 0

    readonly property color clear: spoke.theme.alpha(spoke.colour, 0)
    readonly property real sealRadius: 7

    function along(share) {
        return Qt.point(spoke.fromX + (spoke.toX - spoke.fromX) * share,
                        spoke.fromY + (spoke.toY - spoke.fromY) * share);
    }

    objectName: "sfere-spoke-" + spoke.network
    antialiasing: true
    Accessible.ignored: true

    // A whole spoke: a soft band and the line itself.
    ShapePath {
        objectName: "sfere-path-whole"
        strokeColor: spoke.broken ? spoke.clear : spoke.theme.alpha(spoke.colour, 0.05 + 0.08 * spoke.lit)
        strokeWidth: 10
        fillColor: spoke.clear
        startX: spoke.fromX
        startY: spoke.fromY

        PathLine { x: spoke.toX; y: spoke.toY }
    }

    ShapePath {
        objectName: "sfere-path-whole"
        strokeColor: spoke.broken ? spoke.clear
            : spoke.theme.alpha(spoke.colour, spoke.selected ? 0.9 : 0.55)
        strokeWidth: spoke.selected ? 2 : 1.3
        fillColor: spoke.clear
        startX: spoke.fromX
        startY: spoke.fromY

        PathLine { x: spoke.toX; y: spoke.toY }
    }

    // A broken spoke: two dashed ends with a gap between them...
    ShapePath {
        objectName: "sfere-path-broken"
        strokeColor: spoke.broken ? spoke.theme.alpha(spoke.colour, 0.45) : spoke.clear
        strokeWidth: 1.2
        fillColor: spoke.clear
        strokeStyle: ShapePath.DashLine
        dashPattern: [3, 5]

        PathMultiline {
            paths: [[Qt.point(spoke.fromX, spoke.fromY), spoke.along(0.42)],
                    [spoke.along(0.58), Qt.point(spoke.toX, spoke.toY)]]
        }
    }

    // ...and the seal in the gap.
    ShapePath {
        objectName: "sfere-path-broken"
        strokeColor: spoke.broken ? spoke.theme.alpha(spoke.colour, 0.9) : spoke.clear
        strokeWidth: 1.4
        fillColor: spoke.clear

        PathAngleArc {
            centerX: spoke.along(0.5).x; centerY: spoke.along(0.5).y
            radiusX: spoke.sealRadius; radiusY: spoke.sealRadius
            startAngle: 0; sweepAngle: 360
        }
        PathMove { x: spoke.along(0.5).x - spoke.sealRadius * 0.7; y: spoke.along(0.5).y + spoke.sealRadius * 0.7 }
        PathLine { x: spoke.along(0.5).x + spoke.sealRadius * 0.7; y: spoke.along(0.5).y - spoke.sealRadius * 0.7 }
    }
}
