import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"

// Worker settings over the existing PySide6 backend. Theme + motion changes are
// raised as signals so the shell (which owns darkTheme) applies them; the new
// Theme singleton follows automatically.
ScrollView {
    id: page
    clip: true

    signal requestTheme(string mode)   // "light" | "dark"
    signal requestMotion(bool enabled)
    signal requestPage(int index)

    readonly property int gutter: Theme.space6
    readonly property int maxWidth: 1100
    function contentW() { return Math.max(0, Math.min(availableWidth - gutter * 2, maxWidth)) }

    ColumnLayout {
        x: Math.max(page.gutter, (page.availableWidth - page.contentW()) / 2)
        y: page.gutter
        width: page.contentW()
        spacing: Theme.space5

        // ── Appearance ──
        AppCard {
            id: appearanceCard
            Layout.fillWidth: true
            Layout.preferredHeight: appearanceCol.implicitHeight + appearanceCard.pad * 2
            ColumnLayout {
                id: appearanceCol
                width: parent.width
                spacing: Theme.space3

                SectionHeader { Layout.fillWidth: true; title: "Appearance"; subtitle: "Theme and motion for this device." }

                Text { text: "THEME"; color: Theme.textMuted; font.pixelSize: Typography.captionSize; font.weight: Typography.weightSemiBold }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.space3

                    // Light / Dark preview-cards
                    Repeater {
                        model: [
                            { key: "light", label: "Light", bg: "#F4F7FC", surface: "#FFFFFF", text: "#101828" },
                            { key: "dark", label: "Dark", bg: "#080D1C", surface: "#11182B", text: "#F7F9FF" }
                        ]
                        delegate: Rectangle {
                            id: themeOpt
                            required property var modelData
                            readonly property bool active: (modelData.key === "dark") === Theme.darkMode
                            Layout.preferredWidth: 150
                            Layout.preferredHeight: 92
                            radius: Theme.radiusMd
                            color: modelData.bg
                            border.width: themeOpt.active ? 2 : 1
                            border.color: themeOpt.active ? Theme.primary : Theme.border
                            Behavior on border.color { ColorAnimation { duration: Theme.durHover } }

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 10
                                spacing: 6
                                Rectangle { Layout.preferredWidth: 60; Layout.preferredHeight: 10; radius: 3; color: themeOpt.modelData.surface }
                                Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 8; radius: 3; color: themeOpt.modelData.surface; opacity: 0.7 }
                                Item { Layout.fillHeight: true }
                                RowLayout {
                                    Layout.fillWidth: true
                                    Text { text: themeOpt.modelData.label; color: themeOpt.modelData.text; font.pixelSize: Typography.labelSize; font.weight: Typography.weightSemiBold; Layout.fillWidth: true }
                                    Rectangle { width: 10; height: 10; radius: 5; color: Theme.primary; visible: themeOpt.active }
                                }
                            }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: page.requestTheme(themeOpt.modelData.key) }
                        }
                    }
                    Item { Layout.fillWidth: true }
                }

                Text { text: "MOTION"; color: Theme.textMuted; font.pixelSize: Typography.captionSize; font.weight: Typography.weightSemiBold; Layout.topMargin: 4 }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.space2
                    AppButton {
                        text: "Full motion"
                        strong: backend.motionEnabled
                        fill: backend.motionEnabled ? Theme.primary : Theme.surfaceElevated
                        fillHover: backend.motionEnabled ? Theme.primaryHover : Theme.surfaceMuted
                        fillPressed: Theme.surfaceMuted
                        stroke: backend.motionEnabled ? Theme.primary : Theme.border
                        textColor: backend.motionEnabled ? "#ffffff" : Theme.textPrimary
                        onClicked: page.requestMotion(true)
                    }
                    AppButton {
                        text: "Reduced motion"
                        strong: !backend.motionEnabled
                        fill: !backend.motionEnabled ? Theme.primary : Theme.surfaceElevated
                        fillHover: !backend.motionEnabled ? Theme.primaryHover : Theme.surfaceMuted
                        fillPressed: Theme.surfaceMuted
                        stroke: !backend.motionEnabled ? Theme.primary : Theme.border
                        textColor: !backend.motionEnabled ? "#ffffff" : Theme.textPrimary
                        onClicked: page.requestMotion(false)
                    }
                    Item { Layout.fillWidth: true }
                }
            }
        }

        // ── Runtime & privacy ──
        AppCard {
            id: privacyCard
            Layout.fillWidth: true
            Layout.preferredHeight: privacyCol.implicitHeight + privacyCard.pad * 2
            ColumnLayout {
                id: privacyCol
                width: parent.width
                spacing: Theme.space3

                RowLayout {
                    Layout.fillWidth: true
                    SectionHeader { Layout.fillWidth: true; title: "Runtime & Privacy"; subtitle: "CV parsing, scoring and exports run on this device." }
                    AppBadge { text: "LOCAL-ONLY"; tint: Theme.success }
                }

                Text { text: "OUTPUT FOLDER"; color: Theme.textMuted; font.pixelSize: Typography.captionSize; font.weight: Typography.weightSemiBold }
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 40
                    radius: Theme.radiusMd
                    color: Theme.surfaceMuted
                    border.width: 1; border.color: Theme.border
                    Text {
                        anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12
                        verticalAlignment: Text.AlignVCenter
                        text: backend.outputFolder && backend.outputFolder.length > 0 ? backend.outputFolder : "Default output folder"
                        color: Theme.textSecondary
                        font.pixelSize: Typography.labelSize
                        elide: Text.ElideMiddle
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.space2
                    AppButton {
                        text: "Open output folder"
                        fill: Theme.surfaceElevated; fillHover: Theme.surfaceMuted
                        fillPressed: Theme.surfaceMuted; stroke: Theme.border
                        textColor: Theme.textPrimary
                        onClicked: backend.openOutputFolder()
                    }
                    AppButton {
                        text: "Show app status"
                        fill: Theme.surfaceElevated; fillHover: Theme.surfaceMuted
                        fillPressed: Theme.surfaceMuted; stroke: Theme.border
                        textColor: Theme.textPrimary
                        onClicked: backend.showAppStatus()
                    }
                    Item { Layout.fillWidth: true }
                }
            }
        }

        // ── Website sync ──
        AppCard {
            id: syncCard
            Layout.fillWidth: true
            Layout.preferredHeight: syncCol.implicitHeight + syncCard.pad * 2
            ColumnLayout {
                id: syncCol
                width: parent.width
                spacing: Theme.space3

                RowLayout {
                    Layout.fillWidth: true
                    SectionHeader { Layout.fillWidth: true; title: "Website Sync"; subtitle: "Optional. Nothing is uploaded unless you sync explicitly." }
                    StatusBadge { status: backend.syncConnected ? "connected" : "disabled" }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.space4
                    ColumnLayout {
                        spacing: 1
                        Text { text: "API endpoint"; color: Theme.textMuted; font.pixelSize: Typography.captionSize }
                        Text { text: backend.syncApiUrl || "—"; color: Theme.textSecondary; font.pixelSize: Typography.labelSize }
                    }
                    Item { Layout.fillWidth: true }
                    ColumnLayout {
                        spacing: 1
                        Text { text: "Pending"; color: Theme.textMuted; font.pixelSize: Typography.captionSize }
                        Text { text: backend.syncPendingCount + " result(s)"; color: Theme.textPrimary; font.pixelSize: Typography.labelSize; font.weight: Typography.weightSemiBold }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.space2
                    AppButton {
                        text: "Open Website Sync"
                        strong: true
                        fill: Theme.primary; fillHover: Theme.primaryHover
                        fillPressed: Qt.darker(Theme.primary, 1.15); stroke: Theme.primary
                        textColor: "#ffffff"
                        onClicked: page.requestPage(4)
                    }
                    AppButton {
                        text: "Refresh queue"
                        fill: Theme.surfaceElevated; fillHover: Theme.surfaceMuted
                        fillPressed: Theme.surfaceMuted; stroke: Theme.border
                        textColor: Theme.textPrimary
                        onClicked: backend.refreshSyncQueue()
                    }
                    Item { Layout.fillWidth: true }
                }
            }
        }

        Item { Layout.preferredHeight: Theme.space5 }
    }
}
