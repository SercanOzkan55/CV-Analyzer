import QtQuick
import "../theme"

// Small pill label. `tint` sets the accent; soft background derived from it.
Rectangle {
    id: badge
    property string text: ""
    property color tint: Theme.primary
    property bool solid: false

    implicitHeight: 22
    implicitWidth: label.implicitWidth + 20
    radius: height / 2
    color: solid ? tint : Qt.rgba(tint.r, tint.g, tint.b, Theme.darkMode ? 0.18 : 0.14)
    border.width: solid ? 0 : 1
    border.color: Qt.rgba(tint.r, tint.g, tint.b, 0.45)

    Text {
        id: label
        anchors.centerIn: parent
        text: badge.text
        color: badge.solid ? Theme.textInverse : badge.tint
        font.pixelSize: Typography.captionSize
        font.weight: Typography.weightSemiBold
    }
}
