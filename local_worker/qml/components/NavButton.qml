import QtQuick
import QtQuick.Controls

Button {
    id: control

    property bool active: false
    property string glyph: ""
    property color activeColor: "#7c5cff"
    property color activeText: "#ffffff"
    property color textColor: "#9aa8c7"
    property color hoverText: "#f4f7ff"
    property color activeBg: "#18152f"
    property color hoverBg: "#111827"
    property color activeIcon: "#a78bfa"
    property color mutedIcon: "#8e9abf"
    signal navClicked()

    height: 44
    implicitWidth: 208
    hoverEnabled: true
    onClicked: navClicked()

    scale: down ? 0.985 : (hovered ? 1.02 : 1)
    Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }

    contentItem: Row {
        spacing: 12
        anchors.verticalCenter: parent.verticalCenter
        leftPadding: 14
        rightPadding: 12

        Canvas {
            id: navIcon
            width: 20
            height: 20
            antialiasing: true

            onPaint: {
                var ctx = getContext("2d")
                var color = control.active ? control.activeIcon : (control.hovered ? control.hoverText : control.mutedIcon)
                ctx.clearRect(0, 0, width, height)
                ctx.strokeStyle = color
                ctx.fillStyle = color
                ctx.lineWidth = 1.7
                ctx.lineCap = "round"
                ctx.lineJoin = "round"

                function rect(x, y, w, h, r) {
                    ctx.beginPath()
                    ctx.moveTo(x + r, y)
                    ctx.lineTo(x + w - r, y)
                    ctx.quadraticCurveTo(x + w, y, x + w, y + r)
                    ctx.lineTo(x + w, y + h - r)
                    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h)
                    ctx.lineTo(x + r, y + h)
                    ctx.quadraticCurveTo(x, y + h, x, y + h - r)
                    ctx.lineTo(x, y + r)
                    ctx.quadraticCurveTo(x, y, x + r, y)
                    ctx.stroke()
                }

                if (control.glyph === "dashboard") {
                    rect(3, 3, 5, 5, 1.5); rect(12, 3, 5, 5, 1.5); rect(3, 12, 5, 5, 1.5); rect(12, 12, 5, 5, 1.5)
                } else if (control.glyph === "analyze") {
                    ctx.beginPath(); ctx.arc(9, 9, 5.5, 0, Math.PI * 2); ctx.stroke()
                    ctx.beginPath(); ctx.moveTo(13.5, 13.5); ctx.lineTo(17, 17); ctx.stroke()
                } else if (control.glyph === "results") {
                    rect(4, 3, 12, 14, 2)
                    ctx.beginPath(); ctx.moveTo(7, 7); ctx.lineTo(13, 7); ctx.moveTo(7, 10.5); ctx.lineTo(14, 10.5); ctx.moveTo(7, 14); ctx.lineTo(11, 14); ctx.stroke()
                } else if (control.glyph === "history") {
                    ctx.beginPath(); ctx.arc(10, 10, 7, 0.15, Math.PI * 1.85); ctx.stroke()
                    ctx.beginPath(); ctx.moveTo(4, 5); ctx.lineTo(4, 1.8); ctx.moveTo(10, 6); ctx.lineTo(10, 10); ctx.lineTo(13.5, 12); ctx.stroke()
                } else if (control.glyph === "sync") {
                    ctx.beginPath(); ctx.arc(10, 10, 6.5, 0.25, Math.PI * 1.15); ctx.stroke()
                    ctx.beginPath(); ctx.moveTo(4, 12); ctx.lineTo(2, 12); ctx.lineTo(2, 15); ctx.moveTo(16, 8); ctx.lineTo(18, 8); ctx.lineTo(18, 5); ctx.stroke()
                } else if (control.glyph === "reports") {
                    ctx.beginPath(); ctx.moveTo(5, 4); ctx.lineTo(12, 4); ctx.lineTo(16, 8); ctx.lineTo(16, 16); ctx.lineTo(5, 16); ctx.closePath(); ctx.stroke()
                    ctx.beginPath(); ctx.moveTo(12, 4); ctx.lineTo(12, 8); ctx.lineTo(16, 8); ctx.moveTo(8, 12); ctx.lineTo(13, 12); ctx.stroke()
                } else if (control.glyph === "templates") {
                    rect(3, 5, 14, 10, 2)
                    ctx.beginPath(); ctx.moveTo(4, 6); ctx.lineTo(10, 11); ctx.lineTo(16, 6); ctx.stroke()
                } else if (control.glyph === "inbox") {
                    ctx.beginPath()
                    ctx.moveTo(3, 11); ctx.lineTo(7, 11); ctx.lineTo(8.5, 14); ctx.lineTo(11.5, 14); ctx.lineTo(13, 11); ctx.lineTo(17, 11)
                    ctx.lineTo(15, 4); ctx.lineTo(5, 4); ctx.closePath(); ctx.stroke()
                } else {
                    ctx.beginPath(); ctx.arc(10, 10, 3, 0, Math.PI * 2); ctx.stroke()
                    for (var i = 0; i < 8; i++) {
                        var a = i * Math.PI / 4
                        ctx.beginPath()
                        ctx.moveTo(10 + Math.cos(a) * 6, 10 + Math.sin(a) * 6)
                        ctx.lineTo(10 + Math.cos(a) * 8, 10 + Math.sin(a) * 8)
                        ctx.stroke()
                    }
                }
            }

            Connections {
                target: control
                function onHoveredChanged() { navIcon.requestPaint() }
                function onActiveChanged() { navIcon.requestPaint() }
                function onGlyphChanged() { navIcon.requestPaint() }
            }
            Component.onCompleted: requestPaint()
        }

        Text {
            text: control.text
            color: control.active ? control.activeText : (control.hovered ? control.hoverText : control.textColor)
            font.pixelSize: 14
            font.weight: control.active ? Font.DemiBold : Font.Medium
            verticalAlignment: Text.AlignVCenter
        }
    }

    background: Rectangle {
        radius: 12
        color: control.active ? control.activeBg : (control.hovered ? control.hoverBg : "transparent")
        border.width: control.active ? 1 : 0
        border.color: control.active ? Qt.rgba(control.activeColor.r, control.activeColor.g, control.activeColor.b, 0.45) : "transparent"
        Behavior on color { ColorAnimation { duration: 180 } }
        Behavior on border.color { ColorAnimation { duration: 180 } }
    }
}
