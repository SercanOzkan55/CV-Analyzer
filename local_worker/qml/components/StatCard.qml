import QtQuick
import QtQuick.Layouts
import "../theme"

// Dashboard statistic card: big animated number, label, optional delta + accent
// dot. Hover-elevates. value is numeric; suffix appends a unit ("%").
AppCard {
    id: root
    property string label: ""
    property real value: 0
    property string suffix: ""
    // When set, shown verbatim instead of the count-up number (for non-numeric
    // values like "—" or formatted strings).
    property string displayText: ""
    property string delta: ""
    property bool deltaPositive: true
    property color tint: Theme.primary

    hoverable: true
    pad: Theme.space4
    implicitWidth: 200
    implicitHeight: 116

    // Count-up animation
    property real animatedValue: 0
    Behavior on animatedValue {
        enabled: !Theme.reducedMotion
        NumberAnimation { duration: Theme.durData; easing.type: Easing.OutCubic }
    }
    onValueChanged: animatedValue = value
    Component.onCompleted: animatedValue = value

    ColumnLayout {
        anchors.fill: parent
        spacing: Theme.space2

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
            Rectangle {
                width: 9; height: 9; radius: 4.5
                color: root.tint
                Layout.alignment: Qt.AlignTop
            }
        }

        Text {
            text: root.displayText.length > 0 ? root.displayText : Math.round(root.animatedValue) + root.suffix
            color: Theme.textPrimary
            font.pixelSize: Typography.displaySize
            font.weight: Typography.weightBlack
            elide: Text.ElideRight
            Layout.fillWidth: true
        }

        Text {
            visible: root.delta.length > 0
            text: root.delta
            color: root.deltaPositive ? Theme.success : Theme.danger
            font.pixelSize: Typography.captionSize
            font.weight: Typography.weightSemiBold
        }
    }
}
