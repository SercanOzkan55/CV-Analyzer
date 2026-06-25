import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"

// Inbox & Audit — owner notifications + the local decision audit trail the
// worker writes to the SQLite workspace. The shell already renders the page
// title/subtitle, so this page leads with the action bar (no duplicate header).
// All data comes from the global `backend` context object; stays on device.
ScrollView {
    id: page
    clip: true

    readonly property int gutter: Theme.space6
    readonly property int maxWidth: 1100
    function contentW() { return Math.max(0, Math.min(availableWidth - gutter * 2, maxWidth)) }

    function typeTint(t) {
        if (t === "accepted" || t === "success") return Theme.success
        if (t === "rejected" || t === "error") return Theme.danger
        if (t === "needs_manual_review" || t === "warning") return Theme.warning
        return Theme.primary
    }

    Component.onCompleted: backend.refreshInbox()

    ColumnLayout {
        x: Math.max(page.gutter, (page.availableWidth - page.contentW()) / 2)
        y: page.gutter
        width: page.contentW()
        spacing: Theme.space4

        // ── Action bar ──
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.space2

            AppBadge {
                visible: backend.unreadNotificationCount > 0
                text: backend.unreadNotificationCount + " new"
                tint: Theme.danger
            }
            Item { Layout.fillWidth: true }

            AppButton {
                text: "Mark all read"
                enabled: backend.unreadNotificationCount > 0
                fill: Theme.surfaceElevated; fillHover: Theme.surfaceMuted
                fillPressed: Theme.surfaceMuted; stroke: Theme.border
                textColor: Theme.textPrimary
                onClicked: backend.markAllNotificationsRead()
            }
            AppButton {
                text: "Refresh"
                fill: Theme.surfaceElevated; fillHover: Theme.surfaceMuted
                fillPressed: Theme.surfaceMuted; stroke: Theme.border
                textColor: Theme.textPrimary
                onClicked: backend.refreshInbox()
            }
        }

        // ── Notifications ──
        Text {
            text: "Notifications (" + backend.notificationCount + ")"
            color: Theme.textPrimary
            font.pixelSize: Typography.subheadingSize
            font.weight: Typography.weightSemiBold
            Layout.topMargin: 2
        }

        AppCard {
            Layout.fillWidth: true
            visible: backend.notificationCount === 0
            Layout.preferredHeight: 88
            Text {
                anchors.centerIn: parent
                width: parent.width - Theme.space5 * 2
                horizontalAlignment: Text.AlignHCenter
                text: "No notifications yet. Run a local analysis to generate candidate decisions."
                color: Theme.textMuted
                font.pixelSize: Typography.labelSize
                wrapMode: Text.WordWrap
            }
        }

        Repeater {
            model: backend.notificationsModel
            delegate: AppCard {
                id: notifCard
                required property int index
                required property string title
                required property string message
                required property string candidateName
                required property string type
                required property bool isRead
                required property string createdAt

                Layout.fillWidth: true
                pad: Theme.space4
                Layout.preferredHeight: notifRow.implicitHeight + notifCard.pad * 2
                color: isRead ? Theme.surface : Theme.surfaceElevated
                border.color: isRead ? Theme.border : page.typeTint(type)
                border.width: isRead ? 1 : 2

                // Staggered entrance
                opacity: 0
                transform: Translate { id: notifShift; x: 18 }
                Component.onCompleted: {
                    if (typeof backend !== "undefined" && !backend.motionEnabled) {
                        opacity = 1; notifShift.x = 0; return
                    }
                    notifIn.start()
                }
                SequentialAnimation {
                    id: notifIn
                    PauseAnimation { duration: Math.max(0, Math.min(notifCard.index, 10)) * 45 }
                    ParallelAnimation {
                        NumberAnimation { target: notifCard; property: "opacity"; to: 1; duration: 340; easing.type: Easing.OutCubic }
                        NumberAnimation { target: notifShift; property: "x"; to: 0; duration: 380; easing.type: Easing.OutCubic }
                    }
                }

                RowLayout {
                    id: notifRow
                    width: parent.width
                    spacing: Theme.space3

                    Rectangle {
                        Layout.alignment: Qt.AlignTop
                        Layout.topMargin: 3
                        width: 10; height: 10; radius: 5
                        color: page.typeTint(notifCard.type)
                        opacity: notifCard.isRead ? 0.35 : 1.0
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 3
                        Text {
                            Layout.fillWidth: true
                            text: notifCard.title || "Notification"
                            color: Theme.textPrimary
                            font.pixelSize: Typography.labelSize
                            font.weight: notifCard.isRead ? Typography.weightMedium : Typography.weightBold
                            wrapMode: Text.WordWrap
                        }
                        Text {
                            Layout.fillWidth: true
                            visible: notifCard.message.length > 0
                            text: notifCard.message
                            color: Theme.textSecondary
                            font.pixelSize: Typography.captionSize
                            wrapMode: Text.WordWrap
                        }
                        Text {
                            text: (notifCard.candidateName ? notifCard.candidateName + "  ·  " : "") + notifCard.createdAt
                            color: Theme.textMuted
                            font.pixelSize: Typography.captionSize
                        }
                    }
                }
            }
        }

        // ── Audit log ──
        Text {
            text: "Audit log (" + backend.auditCount + ")"
            color: Theme.textPrimary
            font.pixelSize: Typography.subheadingSize
            font.weight: Typography.weightSemiBold
            Layout.topMargin: Theme.space2
        }

        AppCard {
            Layout.fillWidth: true
            visible: backend.auditCount === 0
            Layout.preferredHeight: 88
            Text {
                anchors.centerIn: parent
                text: "No audit entries yet."
                color: Theme.textMuted
                font.pixelSize: Typography.labelSize
            }
        }

        Repeater {
            model: backend.auditModel
            delegate: AppCard {
                id: auditCard
                required property int index
                required property string action
                required property string module
                required property string description
                required property string status
                required property string createdAt

                Layout.fillWidth: true
                pad: Theme.space4
                Layout.preferredHeight: auditRow.implicitHeight + auditCard.pad * 2

                // Staggered entrance
                opacity: 0
                transform: Translate { id: auditShift; x: 18 }
                Component.onCompleted: {
                    if (typeof backend !== "undefined" && !backend.motionEnabled) {
                        opacity = 1; auditShift.x = 0; return
                    }
                    auditIn.start()
                }
                SequentialAnimation {
                    id: auditIn
                    PauseAnimation { duration: Math.max(0, Math.min(auditCard.index, 10)) * 40 }
                    ParallelAnimation {
                        NumberAnimation { target: auditCard; property: "opacity"; to: 1; duration: 320; easing.type: Easing.OutCubic }
                        NumberAnimation { target: auditShift; property: "x"; to: 0; duration: 360; easing.type: Easing.OutCubic }
                    }
                }

                RowLayout {
                    id: auditRow
                    width: parent.width
                    spacing: Theme.space3

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            Layout.fillWidth: true
                            text: auditCard.action + (auditCard.module ? "  ·  " + auditCard.module : "")
                            color: Theme.textPrimary
                            font.pixelSize: Typography.labelSize
                            font.weight: Typography.weightSemiBold
                            wrapMode: Text.WordWrap
                        }
                        Text {
                            Layout.fillWidth: true
                            visible: auditCard.description.length > 0
                            text: auditCard.description
                            color: Theme.textSecondary
                            font.pixelSize: Typography.captionSize
                            wrapMode: Text.WordWrap
                        }
                        Text {
                            text: auditCard.createdAt
                            color: Theme.textMuted
                            font.pixelSize: Typography.captionSize
                        }
                    }
                    StatusBadge {
                        Layout.alignment: Qt.AlignVCenter
                        visible: auditCard.status.length > 0
                        status: auditCard.status
                    }
                }
            }
        }

        Item { Layout.preferredHeight: Theme.space5 }
    }
}
