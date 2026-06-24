import QtQuick
import QtQuick.Layouts
import "../theme"

// Labeled horizontal score bar with animated fill. value 0..100.
ColumnLayout {
    id: root
    property string label: ""
    property real value: 0
    property color tint: Theme.primary
    property bool showValue: true

    spacing: 6

    RowLayout {
        Layout.fillWidth: true
        Text {
            Layout.fillWidth: true
            text: root.label
            color: Theme.textSecondary
            font.pixelSize: Typography.labelSize
            font.weight: Typography.weightMedium
            elide: Text.ElideRight
        }
        Text {
            visible: root.showValue
            text: Math.round(root.value) + "%"
            color: Theme.textPrimary
            font.pixelSize: Typography.labelSize
            font.weight: Typography.weightSemiBold
        }
    }

    Rectangle {
        Layout.fillWidth: true
        implicitHeight: 8
        radius: 4
        color: Theme.surfaceMuted

        Rectangle {
            height: parent.height
            radius: parent.radius
            width: parent.width * Math.max(0, Math.min(100, root.value)) / 100
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: root.tint }
                GradientStop { position: 1; color: Qt.lighter(root.tint, 1.25) }
            }
            Behavior on width {
                enabled: !Theme.reducedMotion
                NumberAnimation { duration: Theme.durData; easing.type: Easing.OutCubic }
            }
        }
    }
}
