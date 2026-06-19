import QtQuick
import QtQuick.Layouts

Rectangle {
    id: card

    property string label: ""
    property var value: ""
    property string detail: ""
    property color accent: "#6366f1"
    property color surface: "#101624"
    property color stroke: "#26314d"
    property color primaryText: "#f8fbff"
    property color mutedText: "#8e9abf"
    property color subtleText: "#66708f"

    Layout.fillWidth: true
    implicitHeight: 92
    radius: 16
    color: surface
    border.width: 1
    border.color: stroke
    y: hoverArea.containsMouse ? -2 : 0

    Behavior on y { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
    Behavior on color { ColorAnimation { duration: 160 } }
    Behavior on border.color { ColorAnimation { duration: 160 } }

    Rectangle {
        anchors.fill: parent
        anchors.margins: 1
        radius: parent.radius - 1
        opacity: hoverArea.containsMouse ? 0.1 : 0.055
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: card.accent }
            GradientStop { position: 1; color: "transparent" }
        }
        Behavior on opacity { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 4

        Text {
            text: card.label
            color: card.mutedText
            font.pixelSize: 12
            font.weight: Font.DemiBold
            elide: Text.ElideRight
            Layout.fillWidth: true
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Text {
                text: card.value
                color: card.primaryText
                font.pixelSize: 26
                font.weight: Font.Bold
                elide: Text.ElideRight
                Layout.fillWidth: true
            }

            Rectangle {
                Layout.alignment: Qt.AlignVCenter
                width: 30
                height: 30
                radius: 12
                color: Qt.rgba(card.accent.r, card.accent.g, card.accent.b, 0.14)
                border.width: 1
                border.color: Qt.rgba(card.accent.r, card.accent.g, card.accent.b, 0.35)
            }
        }

        Text {
            text: card.detail
            color: card.subtleText
            font.pixelSize: 10
            elide: Text.ElideRight
            Layout.fillWidth: true
        }
    }

    MouseArea {
        id: hoverArea
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.NoButton
    }
}
