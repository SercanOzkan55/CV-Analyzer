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
    property real radius: 12

    implicitHeight: 46
    implicitWidth: Math.max(132, contentItem.implicitWidth + 42)
    padding: 0
    hoverEnabled: true

    // Disabled buttons previously looked almost identical to enabled ones —
    // only the text/border color shifted slightly, background fill didn't
    // change at all — so a correctly-disabled button (e.g. "Clear all" with
    // nothing to clear) read as broken/unresponsive rather than as
    // intentionally off. One clear, uniform dim signal fixes that.
    opacity: control.enabled ? 1 : 0.45

    scale: down ? 0.965 : (hovered ? 1.018 : 1)

    Behavior on scale {
        NumberAnimation { duration: 150; easing.type: Easing.OutCubic }
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
        id: bgRect
        radius: control.radius
        border.width: 1
        border.color: control.enabled ? (control.hovered ? Qt.lighter(control.stroke, 1.2) : control.stroke) : "#243044"
        color: control.down ? control.fillPressed : (control.hovered ? control.fillHover : control.fill)
        opacity: control.hovered ? 0.96 : 1

        Behavior on opacity { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
        Behavior on color { ColorAnimation { duration: 150 } }
        Behavior on border.color { ColorAnimation { duration: 150 } }

        // Gradient overlay for strong style buttons
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            visible: control.strong
            opacity: control.hovered ? 0.52 : 0.38
            gradient: Gradient {
                GradientStop { position: 0; color: "#7c5cff" }
                GradientStop { position: 1; color: "#4d8dff" }
            }
            Behavior on opacity {
                NumberAnimation { duration: 150; easing.type: Easing.OutCubic }
            }
        }
    }
}
