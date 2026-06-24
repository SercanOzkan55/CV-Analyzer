import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Inbox & Audit page — surfaces owner notifications and the local audit trail
// that the worker already writes to the SQLite workspace. Theme colors are
// passed in by Main.qml; data comes from the global `backend` context object.
ScrollView {
    id: inboxPage
    clip: true

    // ── Theme (bound from Main.qml) ──
    property int pageMargin: 28
    property int maxWidth: 1100
    property color surface: "#101624"
    property color surfaceAlt: "#151b2e"
    property color border: "#27314a"
    property color textColor: "#f5f7ff"
    property color textMuted: "#a6b0cf"
    property color subtle: "#66708f"
    property color primary: "#7c5cff"
    property color success: "#22c55e"
    property color warning: "#f59e0b"
    property color danger: "#ef4444"

    function availableContentWidth() {
        return Math.max(0, Math.min(availableWidth - pageMargin * 2, maxWidth))
    }

    function typeColor(t) {
        if (t === "accepted" || t === "success") return success
        if (t === "rejected" || t === "error") return danger
        if (t === "needs_manual_review" || t === "warning") return warning
        return primary
    }

    Component.onCompleted: backend.refreshInbox()

    ColumnLayout {
        x: Math.max(inboxPage.pageMargin, (inboxPage.availableWidth - inboxPage.availableContentWidth()) / 2)
        y: 28
        width: inboxPage.availableContentWidth()
        spacing: 16

        // ── Header ──
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    text: "Inbox & Audit"
                    color: inboxPage.textColor
                    font.pixelSize: 22
                    font.bold: true
                }
                Text {
                    text: "Owner notifications and the local decision audit trail. Stays on this device."
                    color: inboxPage.textMuted
                    font.pixelSize: 13
                }
            }

            Rectangle {
                visible: backend.unreadNotificationCount > 0
                radius: 11
                color: inboxPage.danger
                implicitHeight: 22
                implicitWidth: Math.max(22, unreadLabel.implicitWidth + 16)
                Text {
                    id: unreadLabel
                    anchors.centerIn: parent
                    text: backend.unreadNotificationCount + " new"
                    color: "#ffffff"
                    font.pixelSize: 12
                    font.bold: true
                }
            }

            Button {
                text: "Mark all read"
                enabled: backend.unreadNotificationCount > 0
                onClicked: backend.markAllNotificationsRead()
            }

            Button {
                text: "Refresh"
                onClicked: backend.refreshInbox()
            }
        }

        // ── Notifications ──
        Text {
            text: "Notifications (" + backend.notificationCount + ")"
            color: inboxPage.textColor
            font.pixelSize: 15
            font.bold: true
            Layout.topMargin: 4
        }

        Rectangle {
            Layout.fillWidth: true
            visible: backend.notificationCount === 0
            radius: 12
            color: inboxPage.surface
            border.color: inboxPage.border
            implicitHeight: 70
            Text {
                anchors.centerIn: parent
                text: "No notifications yet. Run a local analysis to generate candidate decisions."
                color: inboxPage.subtle
                font.pixelSize: 13
            }
        }

        Repeater {
            model: backend.notificationsModel
            delegate: Rectangle {
                required property string title
                required property string message
                required property string candidateName
                required property string type
                required property bool isRead
                required property string createdAt

                Layout.fillWidth: true
                radius: 12
                color: isRead ? inboxPage.surface : inboxPage.surfaceAlt
                border.color: isRead ? inboxPage.border : inboxPage.typeColor(type)
                border.width: isRead ? 1 : 2
                implicitHeight: notifCol.implicitHeight + 24

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 12

                    Rectangle {
                        Layout.alignment: Qt.AlignTop
                        width: 10
                        height: 10
                        radius: 5
                        color: inboxPage.typeColor(type)
                        opacity: isRead ? 0.35 : 1.0
                    }

                    ColumnLayout {
                        id: notifCol
                        Layout.fillWidth: true
                        spacing: 3
                        Text {
                            Layout.fillWidth: true
                            text: title || "Notification"
                            color: inboxPage.textColor
                            font.pixelSize: 14
                            font.bold: !isRead
                            wrapMode: Text.WordWrap
                        }
                        Text {
                            Layout.fillWidth: true
                            text: message
                            color: inboxPage.textMuted
                            font.pixelSize: 13
                            wrapMode: Text.WordWrap
                            visible: message.length > 0
                        }
                        Text {
                            text: (candidateName ? candidateName + "  •  " : "") + createdAt
                            color: inboxPage.subtle
                            font.pixelSize: 11
                        }
                    }
                }
            }
        }

        // ── Audit log ──
        Text {
            text: "Audit log (" + backend.auditCount + ")"
            color: inboxPage.textColor
            font.pixelSize: 15
            font.bold: true
            Layout.topMargin: 10
        }

        Rectangle {
            Layout.fillWidth: true
            visible: backend.auditCount === 0
            radius: 12
            color: inboxPage.surface
            border.color: inboxPage.border
            implicitHeight: 70
            Text {
                anchors.centerIn: parent
                text: "No audit entries yet."
                color: inboxPage.subtle
                font.pixelSize: 13
            }
        }

        Repeater {
            model: backend.auditModel
            delegate: Rectangle {
                required property string action
                required property string module
                required property string description
                required property string status
                required property string createdAt

                Layout.fillWidth: true
                radius: 10
                color: inboxPage.surface
                border.color: inboxPage.border
                implicitHeight: auditCol.implicitHeight + 20

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 11
                    spacing: 12

                    ColumnLayout {
                        id: auditCol
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            Layout.fillWidth: true
                            text: action + (module ? "  •  " + module : "")
                            color: inboxPage.textColor
                            font.pixelSize: 13
                            font.bold: true
                            wrapMode: Text.WordWrap
                        }
                        Text {
                            Layout.fillWidth: true
                            text: description
                            color: inboxPage.textMuted
                            font.pixelSize: 12
                            wrapMode: Text.WordWrap
                            visible: description.length > 0
                        }
                        Text {
                            text: createdAt
                            color: inboxPage.subtle
                            font.pixelSize: 11
                        }
                    }

                    Rectangle {
                        Layout.alignment: Qt.AlignVCenter
                        visible: status.length > 0
                        radius: 9
                        color: status === "success" ? inboxPage.success : (status === "error" ? inboxPage.danger : inboxPage.subtle)
                        implicitHeight: 18
                        implicitWidth: statusLabel.implicitWidth + 14
                        Text {
                            id: statusLabel
                            anchors.centerIn: parent
                            text: status
                            color: "#ffffff"
                            font.pixelSize: 10
                            font.bold: true
                        }
                    }
                }
            }
        }

        Item { Layout.preferredHeight: 24 }
    }
}
