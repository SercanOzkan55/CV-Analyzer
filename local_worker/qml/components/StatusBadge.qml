import QtQuick
import "../theme"

// Status pill that maps a semantic status string to color + label, with a
// leading dot. Covers candidate + sync + analysis states.
Rectangle {
    id: root
    property string status: "new"

    function _tint(s) {
        switch (s) {
        case "shortlisted":
        case "hired":
        case "connected":
        case "up_to_date":
        case "completed":
        case "success": return Theme.success
        case "interview":
        case "reviewed":
        case "syncing":
        case "running": return Theme.secondary
        case "rejected":
        case "error":
        case "failed": return Theme.danger
        case "needs_review":
        case "authentication_required":
        case "warning": return Theme.warning
        case "disabled": return Theme.textMuted
        default: return Theme.info
        }
    }
    function _label(s) {
        return s.replace(/_/g, " ").replace(/\b\w/g, function (c) { return c.toUpperCase() })
    }

    readonly property color tint: _tint(status)
    implicitHeight: 24
    implicitWidth: row.implicitWidth + 22
    radius: height / 2
    color: Qt.rgba(tint.r, tint.g, tint.b, Theme.darkMode ? 0.16 : 0.12)
    border.width: 1
    border.color: Qt.rgba(tint.r, tint.g, tint.b, 0.4)

    Row {
        id: row
        anchors.centerIn: parent
        spacing: 7
        Rectangle {
            width: 7; height: 7; radius: 3.5
            anchors.verticalCenter: parent.verticalCenter
            color: root.tint
        }
        Text {
            text: root._label(root.status)
            color: root.tint
            font.pixelSize: Typography.captionSize
            font.weight: Typography.weightSemiBold
        }
    }
}
