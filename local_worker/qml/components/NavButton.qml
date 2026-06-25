import QtQuick
import QtQuick.Controls

Button {
    id: control

    property bool active: false
    property bool collapsed: false
    property string glyph: ""
    property color activeColor: "#7c5cff"
    property color activeText: "#ffffff"
    property color textColor: "#9aa8c7"
    property color hoverText: "#f4f7ff"
    property color activeBg: "#18152f"
    property color hoverBg: "#111827"
    property color activeIcon: "#a78bfa"
    property color mutedIcon: "#8e9abf"
    readonly property bool motionOn: typeof backend === "undefined" || backend.motionEnabled
    signal navClicked()

    height: 44
    implicitWidth: 208
    hoverEnabled: true
    onClicked: navClicked()

    // Tooltip with the label when collapsed to an icon-only rail.
    ToolTip.visible: control.collapsed && control.hovered
    ToolTip.text: control.text
    ToolTip.delay: 350

    // Press contracts the whole item ("kapanma"); hover lifts it slightly.
    scale: down ? 0.95 : (hovered ? 1.015 : 1)
    Behavior on scale { NumberAnimation { duration: down ? 110 : 200; easing.type: Easing.OutCubic } }

    contentItem: Row {
        spacing: 12
        anchors.verticalCenter: parent.verticalCenter
        leftPadding: control.collapsed ? Math.max(0, (control.width - 20) / 2) : 14
        rightPadding: control.collapsed ? 0 : 12

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
            visible: !control.collapsed
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

        // Hover "hallucination": a soft accent glow blooms over the item on
        // hover (a preview, distinct from the solid active state), contracts on
        // press, and is hidden once the item is actually active. Full activation
        // only happens on click — hover never fully "opens" the item.
        Rectangle {
            id: halo
            anchors.fill: parent
            radius: parent.radius
            visible: opacity > 0.001
            opacity: control.motionOn
                     ? (control.active ? 0 : (control.down ? 0.05 : (control.hovered ? 0.18 : 0)))
                     : 0
            transformOrigin: Item.Center
            scale: (control.hovered && !control.down) ? 1.0 : 0.85
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: Qt.rgba(control.activeColor.r, control.activeColor.g, control.activeColor.b, 0.9) }
                GradientStop { position: 0.55; color: Qt.rgba(control.activeColor.r, control.activeColor.g, control.activeColor.b, 0.22) }
                GradientStop { position: 1.0; color: Qt.rgba(control.activeColor.r, control.activeColor.g, control.activeColor.b, 0.0) }
            }
            Behavior on opacity { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
            Behavior on scale { NumberAnimation { duration: 280; easing.type: Easing.OutBack; easing.overshoot: 0.7 } }
        }

        // Animated active accent bar on the left edge — grows in with a small
        // overshoot when the item becomes active.
        Rectangle {
            anchors.left: parent.left
            anchors.leftMargin: 3
            anchors.verticalCenter: parent.verticalCenter
            width: 3
            radius: 2
            color: control.activeColor
            height: control.active ? parent.height * 0.52 : 0
            opacity: control.active ? 1 : 0
            Behavior on height { NumberAnimation { duration: 240; easing.type: Easing.OutBack; easing.overshoot: 1.2 } }
            Behavior on opacity { NumberAnimation { duration: 160 } }
        }
    }
}
