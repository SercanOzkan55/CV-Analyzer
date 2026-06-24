import QtQuick
import QtQuick3D
import "../theme"

// Contained QtQuick3D hero accent: a slowly rotating brand-colored rounded
// cube with controlled neon lighting. Uses only a built-in primitive (#Cube),
// transparent background so it blends into any surface. Rotation stops under
// reduced motion. Kept small and self-contained so it can't destabilise the
// rest of the (2D) UI.
Item {
    id: root
    implicitWidth: 120
    implicitHeight: 120

    property color tint: Theme.primary
    property color glow: Theme.accent

    View3D {
        anchors.fill: parent
        renderMode: View3D.Offscreen
        camera: cam

        environment: SceneEnvironment {
            clearColor: "transparent"
            backgroundMode: SceneEnvironment.Transparent
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.High
        }

        PerspectiveCamera {
            id: cam
            position: Qt.vector3d(0, 0, 360)
            fieldOfView: 45
        }

        DirectionalLight {
            eulerRotation: Qt.vector3d(-25, -25, 0)
            brightness: 1.3
        }
        DirectionalLight {
            eulerRotation: Qt.vector3d(130, 45, 0)
            color: root.glow
            brightness: 0.6
        }

        Model {
            id: shape
            source: "#Cube"
            scale: Qt.vector3d(0.95, 0.95, 0.95)
            eulerRotation: Qt.vector3d(18, 0, 0)

            materials: PrincipledMaterial {
                baseColor: root.tint
                metalness: 0.55
                roughness: 0.28
                emissiveFactor: Qt.vector3d(root.tint.r * 0.18, root.tint.g * 0.12, root.tint.b * 0.42)
            }

            NumberAnimation on eulerRotation.y {
                running: !Theme.reducedMotion
                from: 0; to: 360
                duration: 9000
                loops: Animation.Infinite
            }
            SequentialAnimation on eulerRotation.x {
                running: !Theme.reducedMotion
                loops: Animation.Infinite
                NumberAnimation { from: 12; to: 26; duration: 4200; easing.type: Easing.InOutSine }
                NumberAnimation { from: 26; to: 12; duration: 4200; easing.type: Easing.InOutSine }
            }
        }
    }
}
