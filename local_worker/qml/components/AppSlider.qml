import QtQuick
import QtQuick.Controls
import "../theme"

// Themed horizontal slider (0–100 by default) with a gradient fill.
Slider {
    id: control
    from: 0
    to: 100
    stepSize: 1
    property color tint: Theme.primary
    implicitHeight: 24

    background: Rectangle {
        x: control.leftPadding
        y: control.topPadding + control.availableHeight / 2 - height / 2
        width: control.availableWidth
        height: 6
        radius: 3
        color: Theme.surfaceMuted

        Rectangle {
            width: control.visualPosition * parent.width
            height: parent.height
            radius: 3
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: control.tint }
                GradientStop { position: 1; color: Qt.lighter(control.tint, 1.25) }
            }
        }
    }

    handle: Rectangle {
        x: control.leftPadding + control.visualPosition * (control.availableWidth - width)
        y: control.topPadding + control.availableHeight / 2 - height / 2
        width: 18
        height: 18
        radius: 9
        color: Theme.textInverse
        border.color: control.tint
        border.width: 2
        scale: control.pressed ? 1.12 : 1.0
        Behavior on scale { NumberAnimation { duration: Theme.durHover; easing.type: Easing.OutCubic } }
    }
}
