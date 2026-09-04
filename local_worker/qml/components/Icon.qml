import QtQuick
import "../theme"

// Centralized icon renderer: takes a semantic `name` and paints a small,
// consistent vector glyph via Canvas. Single reusable component instead of
// hand-painted Canvas cases duplicated per call site (was embedded directly
// in NavButton.qml). Add a new `case` here to support another icon name.
Canvas {
    id: root

    property string name: ""
    property color tint: Theme.textSecondary
    property int size: 20

    width: size
    height: size
    antialiasing: true

    onPaint: {
        var ctx = getContext("2d")
        ctx.clearRect(0, 0, width, height)
        ctx.strokeStyle = root.tint
        ctx.fillStyle = root.tint
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

        switch (root.name) {
        case "dashboard":
            rect(3, 3, 5, 5, 1.5); rect(12, 3, 5, 5, 1.5); rect(3, 12, 5, 5, 1.5); rect(12, 12, 5, 5, 1.5)
            break
        case "analyze":
            ctx.beginPath(); ctx.arc(9, 9, 5.5, 0, Math.PI * 2); ctx.stroke()
            ctx.beginPath(); ctx.moveTo(13.5, 13.5); ctx.lineTo(17, 17); ctx.stroke()
            break
        case "results":
            rect(4, 3, 12, 14, 2)
            ctx.beginPath(); ctx.moveTo(7, 7); ctx.lineTo(13, 7); ctx.moveTo(7, 10.5); ctx.lineTo(14, 10.5); ctx.moveTo(7, 14); ctx.lineTo(11, 14); ctx.stroke()
            break
        case "compare":
            ctx.beginPath(); ctx.moveTo(3, 16.5); ctx.lineTo(17, 16.5); ctx.stroke()
            ctx.beginPath(); ctx.moveTo(6, 16.5); ctx.lineTo(6, 9); ctx.stroke()
            ctx.beginPath(); ctx.moveTo(10, 16.5); ctx.lineTo(10, 4); ctx.stroke()
            ctx.beginPath(); ctx.moveTo(14, 16.5); ctx.lineTo(14, 11); ctx.stroke()
            break
        case "history":
            ctx.beginPath(); ctx.arc(10, 10, 7, 0.15, Math.PI * 1.85); ctx.stroke()
            ctx.beginPath(); ctx.moveTo(4, 5); ctx.lineTo(4, 1.8); ctx.moveTo(10, 6); ctx.lineTo(10, 10); ctx.lineTo(13.5, 12); ctx.stroke()
            break
        case "templates":
            rect(3, 5, 14, 10, 2)
            ctx.beginPath(); ctx.moveTo(4, 6); ctx.lineTo(10, 11); ctx.lineTo(16, 6); ctx.stroke()
            break
        case "sync":
            ctx.beginPath(); ctx.arc(10, 10, 6.5, 0.25, Math.PI * 1.15); ctx.stroke()
            ctx.beginPath(); ctx.moveTo(4, 12); ctx.lineTo(2, 12); ctx.lineTo(2, 15); ctx.moveTo(16, 8); ctx.lineTo(18, 8); ctx.lineTo(18, 5); ctx.stroke()
            break
        case "inbox":
            ctx.beginPath()
            ctx.moveTo(3, 11); ctx.lineTo(7, 11); ctx.lineTo(8.5, 14); ctx.lineTo(11.5, 14); ctx.lineTo(13, 11); ctx.lineTo(17, 11)
            ctx.lineTo(15, 4); ctx.lineTo(5, 4); ctx.closePath(); ctx.stroke()
            break
        case "settings":
            ctx.beginPath(); ctx.arc(10, 10, 3, 0, Math.PI * 2); ctx.stroke()
            for (var i = 0; i < 8; i++) {
                var a = i * Math.PI / 4
                ctx.beginPath()
                ctx.moveTo(10 + Math.cos(a) * 6, 10 + Math.sin(a) * 6)
                ctx.lineTo(10 + Math.cos(a) * 8, 10 + Math.sin(a) * 8)
                ctx.stroke()
            }
            break
        default:
            ctx.beginPath(); ctx.arc(10, 10, 5, 0, Math.PI * 2); ctx.stroke()
        }
    }

    onTintChanged: requestPaint()
    onNameChanged: requestPaint()
    onWidthChanged: requestPaint()
    Component.onCompleted: requestPaint()
}
