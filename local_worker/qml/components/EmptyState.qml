import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

// Friendly empty / first-run placeholder: title, explanation, optional action.
ColumnLayout {
    id: root
    property string title: "Nothing here yet"
    property string message: ""
    property string actionText: ""
    signal actionTriggered()

    spacing: Theme.space3

    // Simple decorative mark (no emoji, theme-driven).
    Rectangle {
        Layout.alignment: Qt.AlignHCenter
        width: 56; height: 56; radius: 16
        color: Theme.primarySoft
        border.width: 1
        border.color: Qt.rgba(Theme.primary.r, Theme.primary.g, Theme.primary.b, 0.4)
        Rectangle {
            anchors.centerIn: parent
            width: 22; height: 16; radius: 4
            color: "transparent"
            border.width: 2
            border.color: Theme.primary
        }
    }

    Text {
        Layout.alignment: Qt.AlignHCenter
        text: root.title
        color: Theme.textPrimary
        font.pixelSize: Typography.subheadingSize
        font.weight: Typography.weightSemiBold
    }
    Text {
        Layout.alignment: Qt.AlignHCenter
        Layout.maximumWidth: 380
        visible: root.message.length > 0
        text: root.message
        color: Theme.textSecondary
        font.pixelSize: Typography.labelSize
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
    }

    Button {
        Layout.alignment: Qt.AlignHCenter
        Layout.topMargin: 4
        visible: root.actionText.length > 0
        text: root.actionText
        onClicked: root.actionTriggered()
    }
}
