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

    // Count-up animation properties
    property real animatedValue: 0.0

    onValueChanged: {
        if (value === undefined || value === null) return;
        var cleanVal = value.toString().replace(/[^\d\.]/g, '') // remove non-numeric chars except dot
        var num = parseFloat(cleanVal)
        if (!isNaN(num) && (typeof backend === 'undefined' || backend.motionEnabled)) {
            valAnim.stop()
            valAnim.from = animatedValue
            valAnim.to = num
            valAnim.start()
        } else if (!isNaN(num)) {
            animatedValue = num
        }
    }

    NumberAnimation {
        id: valAnim
        target: card
        property: "animatedValue"
        duration: 800
        easing.type: Easing.OutExpo
    }

    Component.onCompleted: {
        if (value !== undefined && value !== null) {
            var cleanVal = value.toString().replace(/[^\d\.]/g, '')
            var num = parseFloat(cleanVal)
            if (!isNaN(num)) {
                animatedValue = num
            }
        }
    }

    Layout.fillWidth: true
    implicitHeight: 92
    radius: 16
    color: (typeof root !== 'undefined' && root.darkTheme) ?
           Qt.rgba(18/255, 24/255, 43/255, 0.76) :
           Qt.rgba(255/255, 255/255, 255/255, 0.82)
    border.width: 1
    border.color: hoverArea.containsMouse ? card.accent : card.stroke
    y: hoverArea.containsMouse ? -3 : 0

    Behavior on y { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
    Behavior on color { ColorAnimation { duration: 180 } }
    Behavior on border.color { ColorAnimation { duration: 180 } }

    // Frosted glass highlight border
    Rectangle {
        anchors.fill: parent
        radius: parent.radius
        color: "transparent"
        border.width: 1
        border.color: (typeof root !== 'undefined' && root.darkTheme) ?
                       Qt.rgba(255, 255, 255, 0.05) :
                       Qt.rgba(255, 255, 255, 0.3)
    }

    // Side accent colored gradient strip
    Rectangle {
        anchors.fill: parent
        anchors.margins: 1
        radius: parent.radius - 1
        opacity: hoverArea.containsMouse ? 0.12 : 0.065
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: card.accent }
            GradientStop { position: 0.75; color: "transparent" }
        }
        Behavior on opacity { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
    }

    // Left thick accent border indicator
    Rectangle {
        x: 1
        y: 16
        width: 3
        height: parent.height - 32
        radius: 1.5
        color: card.accent
        opacity: 0.8
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        anchors.leftMargin: 22 // extra margin for left accent border
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
                text: {
                    if (card.value === undefined || card.value === null) return "";
                    var rawStr = card.value.toString()
                    var cleanVal = rawStr.replace(/[^\d\.]/g, '')
                    var num = parseFloat(cleanVal)
                    if (!isNaN(num)) {
                        var displayNum = card.animatedValue
                        // If it is integer, format as integer
                        if (rawStr.indexOf('%') !== -1) {
                            return Math.round(displayNum) + "%"
                        }
                        if (rawStr.indexOf('s') !== -1 && rawStr.indexOf('.') !== -1) {
                            return displayNum.toFixed(1) + "s"
                        }
                        if (rawStr.indexOf('.') !== -1) {
                            return displayNum.toFixed(1)
                        }
                        // preserve non-digits like suffix
                        var suffix = rawStr.replace(/[\d\.]/g, '')
                        if (suffix.length > 0) {
                            return Math.round(displayNum) + suffix
                        }
                        return Math.round(displayNum).toString()
                    }
                    return card.value
                }
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
                radius: 10
                color: Qt.rgba(card.accent.r, card.accent.g, card.accent.b, hoverArea.containsMouse ? 0.22 : 0.12)
                border.width: 1
                border.color: Qt.rgba(card.accent.r, card.accent.g, card.accent.b, hoverArea.containsMouse ? 0.55 : 0.32)
                Behavior on color { ColorAnimation { duration: 180 } }
                Behavior on border.color { ColorAnimation { duration: 180 } }

                // Small center glowing dot
                Rectangle {
                    anchors.centerIn: parent
                    width: 6
                    height: 6
                    radius: 3
                    color: card.accent
                    opacity: hoverArea.containsMouse ? 1.0 : 0.65
                    Behavior on opacity { NumberAnimation { duration: 180 } }
                }
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
