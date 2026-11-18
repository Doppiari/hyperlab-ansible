// One network, drawn as a glass sphere with an energy core.
//
// The sphere is a presentation of its inputs. Its colour is the network's
// palette colour, passed by the caller and never written here; `character`
// names the core's texture: 0 host (a silver core), 1 calm (clean),
// 2 swirling (dev), 3 banded (services), 4 flickering (dirty), 5 lattice
// (lab). `lit` (0..1) is how much runs inside it; `time` is the caller's
// clock and moves the core and the engraving only while the sphere is lit.
// The component runs no timer and no animation of its own.
//
// Where Qt renders through RHI it runs shaders/sphere.frag.qsb, compiled in
// the repository (tools/build-shaders.sh), so the host needs no shader
// compiler. It draws its still form instead (SphereStill.qml) under the
// software backend, when the effect reports an error (a missing or broken
// .qsb), for a character outside the six, and when `forceStill` is set. The
// still form is complete and keeps the character readable.
//
// The item is a square about 2.4 sphere radii wide, so the halo fits.
// `textureScale` 0.5 renders the effect into a half-size layer for crowded
// views; any other value is full size.

import QtQuick

Item {
    id: sphere

    required property color colour
    property int character: 1
    property real lit: 0
    property bool selected: false
    // Where the light comes from, in the sphere's plane: x to the right,
    // y upward. The default lights it from the upper left.
    property point lightDirection: Qt.point(-0.55, 0.55)
    property real time: 0
    // A fixed turn of the engraving, so neighbouring spheres differ.
    property real turn: 0
    property bool forceStill: false
    property real textureScale: 1

    // Sphere radius as a share of half the item.
    readonly property real radiusShare: 1 / 1.2
    readonly property real litLevel: sphere.lit > 0 ? Math.min(1, sphere.lit) : 0
    readonly property bool knownCharacter: sphere.character >= 0 && sphere.character <= 5
    readonly property real layerScale: sphere.textureScale === 0.5 ? 0.5 : 1
    property bool shaderFailed: false

    // Why the still form is drawn; empty while the shader runs.
    readonly property string stillReason:
        !sphere.knownCharacter ? "unknown-character"
        : sphere.forceStill ? "forced"
        : sphere.GraphicsInfo.api === GraphicsInfo.Software ? "software"
        : sphere.shaderFailed ? "shader-error"
        : ""
    readonly property bool stillForm: sphere.stillReason.length > 0

    implicitWidth: 96
    implicitHeight: 96
    Accessible.ignored: true

    Loader {
        anchors.fill: parent
        sourceComponent: sphere.stillForm ? stillComponent : shaderComponent
    }

    Component {
        id: shaderComponent

        ShaderEffect {
            readonly property real time: sphere.time
            readonly property real lit: sphere.litLevel
            readonly property real character: sphere.character
            readonly property real turn: sphere.turn
            readonly property real selected: sphere.selected ? 1 : 0
            readonly property real radiusShare: sphere.radiusShare
            readonly property real pixelRadius:
                Math.min(width, height) / 2 * sphere.radiusShare * sphere.layerScale
            readonly property color colour: sphere.colour
            readonly property point light: sphere.lightDirection

            fragmentShader: Qt.resolvedUrl("shaders/sphere.frag.qsb")
            layer.enabled: sphere.layerScale < 1
            layer.smooth: true
            layer.textureSize: Qt.size(Math.ceil(width * sphere.layerScale),
                                       Math.ceil(height * sphere.layerScale))

            onStatusChanged: {
                if (status === ShaderEffect.Error)
                    sphere.shaderFailed = true;
            }
            Component.onCompleted: {
                if (status === ShaderEffect.Error)
                    sphere.shaderFailed = true;
            }
        }
    }

    Component {
        id: stillComponent

        SphereStill {
            colour: sphere.colour
            character: sphere.knownCharacter ? sphere.character : -1
            lit: sphere.knownCharacter ? sphere.litLevel : 0
            selected: sphere.selected
            lightDirection: sphere.lightDirection
            radiusShare: sphere.radiusShare
        }
    }
}
