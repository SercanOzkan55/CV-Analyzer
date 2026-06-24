import QtQuick
import QtQuick.Shapes
import "../theme"

// Animated circular score/progress ring. value 0..100. Uses Shape (Qt 6) for
// crisp anti-aliased arcs instead of Canvas repaint loops.
Item {
    id: root
    property real value: 0
    property color tint: Theme.primary
    property int thickness: 10
    property string caption: ""

    implicitWidth: 150
    implicitHeight: 150

    // Animated value so the arc + number fill smoothly.
    property real animatedValue: 0
    Behavior on animatedValue {
        enabled: !Theme.reducedMotion
        NumberAnimation { duration: Theme.durData; easing.type: Easing.OutCubic }
    }
    onValueChanged: animatedValue = value
    Component.onCompleted: animatedValue = value

    readonly property real _radius: Math.min(width, height) / 2 - thickness / 2 - 2
    readonly property real _cx: width / 2
    readonly property real _cy: height / 2

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer

        // Track
        ShapePath {
            strokeColor: Theme.surfaceMuted
            strokeWidth: root.thickness
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            PathAngleArc {
                centerX: root._cx; centerY: root._cy
                radiusX: root._radius; radiusY: root._radius
                startAngle: -90; sweepAngle: 360
            }
        }
        // Progress
        ShapePath {
            strokeColor: root.tint
            strokeWidth: root.thickness
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            PathAngleArc {
                centerX: root._cx; centerY: root._cy
                radiusX: root._radius; radiusY: root._radius
                startAngle: -90
                sweepAngle: 360 * Math.max(0, Math.min(100, root.animatedValue)) / 100
            }
        }
    }

    Column {
        anchors.centerIn: parent
        spacing: 0
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: Math.round(root.animatedValue) + "%"
            color: Theme.textPrimary
            font.pixelSize: Typography.titleSize
            font.weight: Typography.weightBlack
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            visible: root.caption.length > 0
            text: root.caption
            color: Theme.textMuted
            font.pixelSize: Typography.captionSize
        }
    }
}
