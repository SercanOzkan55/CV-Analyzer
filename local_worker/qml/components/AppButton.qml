import QtQuick
import QtQuick.Controls

Button {
    id: control

    property color fill: "#111827"
    property color fillHover: "#151b2e"
    property color fillPressed: "#0b1020"
    property color stroke: "#26314d"
    property color textColor: "#f8fbff"
    property bool strong: false

    implicitHeight: 46
    implicitWidth: Math.max(132, contentItem.implicitWidth + 42)
    padding: 0
    hoverEnabled: true

    scale: down ? 0.982 : 1

    Behavior on scale {
        NumberAnimation { duration: 120; easing.type: Easing.OutCubic }
    }

    contentItem: Text {
        text: control.text
        color: control.enabled ? control.textColor : "#65718a"
        font.pixelSize: 14
        font.weight: Font.DemiBold
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        radius: 12
        border.width: 1
        border.color: control.enabled ? control.stroke : "#243044"
        color: control.down ? control.fillPressed : (control.hovered ? control.fillHover : control.fill)
        opacity: control.hovered ? 0.94 : 1

        Behavior on opacity { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
        Behavior on color { ColorAnimation { duration: 120 } }
        Behavior on border.color { ColorAnimation { duration: 120 } }

        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            visible: control.strong
            opacity: control.hovered ? 0.46 : 0.3
            gradient: Gradient {
                GradientStop { position: 0; color: "#7c5cff" }
                GradientStop { position: 1; color: "#4d8dff" }
            }
            Behavior on opacity {
                NumberAnimation { duration: 140; easing.type: Easing.OutCubic }
            }
        }
    }
}
