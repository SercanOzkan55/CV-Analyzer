import QtQuick

Rectangle {
    id: card

    property color cardColor: "#101624"
    property color strokeColor: "#26314d"
    property color glowColor: "#7c5cff"
    property bool liftEnabled: true

    radius: 16
    color: cardColor
    border.width: 1
    border.color: strokeColor
    y: hoverArea.containsMouse && liftEnabled ? -2 : 0
    opacity: 0.995

    Behavior on y { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
    Behavior on color { ColorAnimation { duration: 160 } }
    Behavior on border.color { ColorAnimation { duration: 160 } }

    Rectangle {
        anchors.fill: parent
        anchors.margins: 1
        radius: parent.radius - 1
        opacity: hoverArea.containsMouse && card.liftEnabled ? 0.08 : 0.045
        gradient: Gradient {
            GradientStop { position: 0; color: card.glowColor }
            GradientStop { position: 0.5; color: "transparent" }
            GradientStop { position: 1; color: "#8b5cf6" }
        }
        Behavior on opacity { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
    }

    MouseArea {
        id: hoverArea
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.NoButton
    }
}
