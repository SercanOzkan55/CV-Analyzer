import QtQuick

Item {
    id: card

    property color cardColor: "#101624"
    property color strokeColor: "#26314d"
    property color glowColor: "#7c5cff"
    property bool liftEnabled: true
    property real radius: 16
    property bool tiltEnabled: false
    property bool hovered: hoverHandler.hovered

    implicitWidth: 200
    implicitHeight: 200
    clip: true

    Rectangle {
        id: softShadow
        anchors.fill: parent
        anchors.margins: 0
        radius: card.radius
        color: (typeof root !== 'undefined' && root.darkTheme) ?
               Qt.rgba(0, 0, 0, card.hovered ? 0.14 : 0.08) :
               Qt.rgba(15, 23, 42, card.hovered ? 0.08 : 0.04)
        opacity: card.liftEnabled ? 1 : 0

        Behavior on color { ColorAnimation { duration: 200 } }
    }

    Rectangle {
        id: glowShadow
        anchors.fill: parent
        anchors.margins: 1
        radius: Math.max(0, card.radius - 1)
        color: Qt.rgba(card.glowColor.r, card.glowColor.g, card.glowColor.b, card.hovered ? 0.08 : 0.02)
        opacity: card.liftEnabled ? 1 : 0

        Behavior on color { ColorAnimation { duration: 200 } }
    }

    // Visual content item
    Rectangle {
        id: visualContent
        anchors.fill: parent
        anchors.margins: 1
        radius: card.radius
        color: (typeof root !== 'undefined' && root.darkTheme) ?
               Qt.rgba(18/255, 24/255, 43/255, 0.76) :
               Qt.rgba(255/255, 255/255, 255/255, 0.82)

        // Gradient border container
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: "transparent"
            border.width: 1
            border.color: card.hovered ? card.glowColor : card.strokeColor
            Behavior on border.color { ColorAnimation { duration: 200 } }
        }

        // Frosted shine inner gradient
        Rectangle {
            anchors.fill: parent
            anchors.margins: 1
            radius: parent.radius - 1
            color: "transparent"
            gradient: Gradient {
                GradientStop {
                    position: 0
                    color: (typeof root !== 'undefined' && root.darkTheme) ?
                           Qt.rgba(255, 255, 255, 0.08) :
                           Qt.rgba(255, 255, 255, 0.4)
                }
                GradientStop { position: 0.35; color: "transparent" }
                GradientStop {
                    position: 1
                    color: card.hovered ?
                           Qt.rgba(card.glowColor.r, card.glowColor.g, card.glowColor.b, 0.04) :
                           "transparent"
                }
            }
        }

        // Hover glow accent highlight (radial-like glow)
        Rectangle {
            anchors.fill: parent
            anchors.margins: 1
            radius: parent.radius - 1
            opacity: (card.hovered && card.liftEnabled) ? 0.08 : 0.04
            gradient: Gradient {
                GradientStop { position: 0; color: card.glowColor }
                GradientStop { position: 0.5; color: "transparent" }
                GradientStop { position: 1; color: "#8b5cf6" }
            }
            Behavior on opacity { NumberAnimation { duration: 200 } }
        }
    }

    HoverHandler {
        id: hoverHandler
        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
    }
}
