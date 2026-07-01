import QtQuick
import QtQuick.Controls
import QtQuick.Shapes
import "../theme"

// Themed search input with leading magnifier glyph and a focus ring.
Rectangle {
    id: root
    property alias text: field.text
    property string placeholder: "Search…"
    signal accepted()

    implicitHeight: 38
    implicitWidth: 240
    radius: Theme.radiusMd
    color: Theme.surfaceMuted
    border.width: field.activeFocus ? 2 : 1
    border.color: field.activeFocus ? Theme.primary : Theme.border
    Behavior on border.color { ColorAnimation { duration: Theme.durHover } }

    Shape {
        id: glass
        anchors.verticalCenter: parent.verticalCenter
        anchors.left: parent.left
        anchors.leftMargin: 12
        width: 16; height: 16
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: Theme.textMuted
            strokeWidth: 1.6
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            PathAngleArc { centerX: 7; centerY: 7; radiusX: 5; radiusY: 5; startAngle: 0; sweepAngle: 360 }
        }
        ShapePath {
            strokeColor: Theme.textMuted
            strokeWidth: 1.6
            capStyle: ShapePath.RoundCap
            startX: 11; startY: 11
            PathLine { x: 15; y: 15 }
        }
    }

    TextField {
        id: field
        anchors.fill: parent
        anchors.leftMargin: 34
        anchors.rightMargin: 10
        verticalAlignment: Text.AlignVCenter
        placeholderText: root.placeholder
        placeholderTextColor: Theme.textMuted
        color: Theme.textPrimary
        font.pixelSize: Typography.labelSize
        selectionColor: Theme.primary
        selectByMouse: true
        background: null
        onAccepted: root.accepted()
    }
}
