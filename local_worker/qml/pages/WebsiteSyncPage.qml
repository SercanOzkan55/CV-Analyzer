import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"

// Optional bridge that pushes ranked result metadata to a Website worker job.
// Off by default; CV files never leave the device. Only backend-supported
// actions are surfaced (save key, test connection, sync, refresh) — no
// placeholder buttons.
ScrollView {
    id: page
    clip: true

    signal requestPage(int index)

    readonly property int gutter: Theme.space6
    readonly property int maxWidth: 1180
    function contentW() { return Math.max(0, Math.min(availableWidth - gutter * 2, maxWidth)) }

    readonly property string syncState: backend.syncRunning ? "syncing"
                                       : (backend.syncConnected ? "connected" : "disabled")

    ColumnLayout {
        x: Math.max(page.gutter, (page.availableWidth - page.contentW()) / 2)
        y: page.gutter
        width: page.contentW()
        spacing: Theme.space5

        // ── Header ──
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.space3
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    text: "Website Sync"
                    color: Theme.textPrimary
                    font.pixelSize: Typography.titleSize
                    font.weight: Typography.weightBold
                }
                Text {
                    Layout.fillWidth: true
                    text: backend.syncDetail
                    color: Theme.textSecondary
                    font.pixelSize: Typography.labelSize
                    wrapMode: Text.WordWrap
                }
            }
            StatusBadge { Layout.alignment: Qt.AlignTop; status: page.syncState }
        }

        // ── Privacy banner ──
        AppCard {
            id: bannerCard
            Layout.fillWidth: true
            Layout.preferredHeight: bannerRow.implicitHeight + bannerCard.pad * 2
            RowLayout {
                id: bannerRow
                width: parent.width
                spacing: Theme.space4
                Rectangle {
                    Layout.alignment: Qt.AlignVCenter
                    width: 44; height: 44; radius: Theme.radiusMd
                    color: Qt.rgba(Theme.success.r, Theme.success.g, Theme.success.b, 0.14)
                    Text { anchors.centerIn: parent; text: "✓"; color: Theme.success; font.pixelSize: 22; font.weight: Typography.weightBold }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.space2
                        Text { text: "Sync is off by default"; color: Theme.textPrimary; font.pixelSize: Typography.subheadingSize; font.weight: Typography.weightSemiBold }
                        AppBadge { text: "LOCAL-ONLY"; tint: Theme.success }
                    }
                    Text {
                        Layout.fillWidth: true
                        text: "CV files stay on this device. Only scores, decisions and analysis metadata are uploaded — and only when you sync explicitly."
                        color: Theme.textSecondary
                        font.pixelSize: Typography.labelSize
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }

        // ── Metrics ──
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.space4
            StatCard {
                Layout.fillWidth: true
                label: "Pending"
                value: backend.syncPendingCount
                tint: Theme.warning
            }
            StatCard {
                Layout.fillWidth: true
                label: "Last upload"
                value: backend.syncLastSyncedCount
                tint: Theme.secondary
            }
            // Quota can be "-" when disconnected, so it is shown verbatim.
            StatCard {
                Layout.fillWidth: true
                label: "Quota"
                displayText: backend.syncConnected ? String(backend.syncQuotaRemaining) : "—"
                tint: Theme.success
            }
        }

        // ── Connection + queue ──
        GridLayout {
            Layout.fillWidth: true
            columns: width < 880 ? 1 : 2
            columnSpacing: Theme.space5
            rowSpacing: Theme.space5

            // Connection
            AppCard {
                id: connCard
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                Layout.preferredHeight: connCol.implicitHeight + connCard.pad * 2
                ColumnLayout {
                    id: connCol
                    width: parent.width
                    spacing: Theme.space3

                    SectionHeader { Layout.fillWidth: true; title: "Connection"; subtitle: "Paste the worker key issued by your Website workspace." }

                    Text { text: "WORKER API URL"; color: Theme.textMuted; font.pixelSize: Typography.captionSize; font.weight: Typography.weightSemiBold }
                    AppTextField {
                        Layout.fillWidth: true
                        text: backend.syncApiUrl
                        placeholder: "http://127.0.0.1:8001/api/worker"
                        onTextChanged: if (backend.syncApiUrl !== text) backend.syncApiUrl = text
                    }

                    Text { text: "WORKER KEY"; color: Theme.textMuted; font.pixelSize: Typography.captionSize; font.weight: Typography.weightSemiBold; Layout.topMargin: 4 }
                    AppTextField {
                        Layout.fillWidth: true
                        password: true
                        text: backend.syncApiKey
                        placeholder: "Paste worker key from Website"
                        onTextChanged: if (backend.syncApiKey !== text) backend.syncApiKey = text
                    }

                    Text { text: "TARGET WEBSITE JOB ID"; color: Theme.textMuted; font.pixelSize: Typography.captionSize; font.weight: Typography.weightSemiBold; Layout.topMargin: 4 }
                    AppTextField {
                        Layout.fillWidth: true
                        text: backend.syncJobId
                        placeholder: backend.syncAllowedJobs === "-" ? "Enter job id…" : "Allowed: " + backend.syncAllowedJobs
                        onTextChanged: if (backend.syncJobId !== text) backend.syncJobId = text
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.topMargin: 4
                        spacing: Theme.space2
                        AppButton {
                            Layout.fillWidth: true
                            text: "Save key"
                            fill: Theme.surfaceElevated; fillHover: Theme.surfaceMuted
                            fillPressed: Theme.surfaceMuted; stroke: Theme.border
                            textColor: Theme.textPrimary
                            onClicked: backend.saveWorkerKey()
                        }
                        AppButton {
                            Layout.fillWidth: true
                            text: backend.syncRunning ? "Testing…" : "Test connection"
                            strong: true
                            enabled: !backend.syncRunning
                            fill: Theme.primary; fillHover: Theme.primaryHover
                            fillPressed: Qt.darker(Theme.primary, 1.15); stroke: Theme.primary
                            textColor: "#ffffff"
                            onClicked: backend.testWebsiteSync()
                        }
                    }

                    // Status box
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.topMargin: 4
                        Layout.preferredHeight: statusCol.implicitHeight + 28
                        radius: Theme.radiusMd
                        color: Theme.surfaceMuted
                        border.width: 1
                        border.color: backend.syncConnected ? Theme.success : Theme.border
                        Behavior on border.color { ColorAnimation { duration: Theme.durHover } }
                        ColumnLayout {
                            id: statusCol
                            anchors.left: parent.left; anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.margins: 14
                            spacing: 4
                            Text {
                                Layout.fillWidth: true
                                text: backend.syncStatus
                                color: backend.syncConnected ? Theme.success : Theme.textPrimary
                                font.pixelSize: Typography.labelSize
                                font.weight: Typography.weightSemiBold
                                elide: Text.ElideRight
                            }
                            Text {
                                Layout.fillWidth: true
                                text: "Company: " + backend.syncCompanyId + "   ·   Jobs: " + backend.syncAllowedJobs
                                color: Theme.textSecondary
                                font.pixelSize: Typography.captionSize
                                elide: Text.ElideRight
                            }
                            Text {
                                Layout.fillWidth: true
                                text: "Access scope: " + backend.syncPermissionSummary
                                color: backend.syncConnected ? Theme.success : Theme.textMuted
                                font.pixelSize: Typography.captionSize
                                wrapMode: Text.WordWrap
                                maximumLineCount: 2
                                elide: Text.ElideRight
                            }
                        }
                    }
                }
            }

            // Sync queue
            AppCard {
                id: queueCard
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                Layout.preferredHeight: queueCol.implicitHeight + queueCard.pad * 2
                ColumnLayout {
                    id: queueCol
                    width: parent.width
                    spacing: Theme.space3

                    RowLayout {
                        Layout.fillWidth: true
                        SectionHeader { Layout.fillWidth: true; title: "Sync Queue"; subtitle: "Review results, pick a job id, then upload when ready." }
                        AppButton {
                            text: "Refresh"
                            fill: Theme.surfaceElevated; fillHover: Theme.surfaceMuted
                            fillPressed: Theme.surfaceMuted; stroke: Theme.border
                            textColor: Theme.textPrimary
                            onClicked: backend.refreshSyncQueue()
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: queueInner.implicitHeight + 36
                        radius: Theme.radiusMd
                        color: Theme.surfaceMuted
                        border.width: 1; border.color: Theme.border
                        ColumnLayout {
                            id: queueInner
                            anchors.centerIn: parent
                            width: Math.min(parent.width - 36, 420)
                            spacing: Theme.space2
                            Text {
                                Layout.fillWidth: true
                                text: backend.syncPendingCount > 0 ? backend.syncPendingCount + " local result(s) waiting" : "Queue is clean"
                                color: Theme.textPrimary
                                font.pixelSize: Typography.subheadingSize
                                font.weight: Typography.weightBold
                                horizontalAlignment: Text.AlignHCenter
                            }
                            Text {
                                Layout.fillWidth: true
                                text: backend.syncPendingCount > 0
                                      ? "Choose a Website job id above, then upload when ready."
                                      : "Run an analysis or change a decision to create a sync queue."
                                color: Theme.textSecondary
                                font.pixelSize: Typography.captionSize
                                wrapMode: Text.WordWrap
                                horizontalAlignment: Text.AlignHCenter
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.space2
                        AppButton {
                            Layout.fillWidth: true
                            text: "Open Results"
                            fill: Theme.surfaceElevated; fillHover: Theme.surfaceMuted
                            fillPressed: Theme.surfaceMuted; stroke: Theme.border
                            textColor: Theme.textPrimary
                            onClicked: page.requestPage(2)
                        }
                        AppButton {
                            Layout.fillWidth: true
                            text: backend.syncRunning ? "Syncing…" : "Sync pending"
                            strong: true
                            enabled: !backend.syncRunning && backend.syncPendingCount > 0
                            fill: Theme.primary; fillHover: Theme.primaryHover
                            fillPressed: Qt.darker(Theme.primary, 1.15); stroke: Theme.primary
                            textColor: "#ffffff"
                            onClicked: backend.syncPendingResults()
                        }
                    }

                    // Sync safety
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.topMargin: 4
                        Layout.preferredHeight: safetyCol.implicitHeight + 28
                        radius: Theme.radiusMd
                        color: Theme.surfaceMuted
                        border.width: 1; border.color: Theme.border
                        ColumnLayout {
                            id: safetyCol
                            anchors.left: parent.left; anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.margins: 14
                            spacing: Theme.space2
                            Text { text: "Sync safety"; color: Theme.textPrimary; font.pixelSize: Typography.labelSize; font.weight: Typography.weightSemiBold }
                            Text {
                                Layout.fillWidth: true
                                text: "1.  CV files stay local unless you use website upload flows.\n2.  This bridge sends ranked result metadata to the selected job.\n3.  Changed decisions are re-queued so the website can be updated."
                                color: Theme.textSecondary
                                font.pixelSize: Typography.captionSize
                                wrapMode: Text.WordWrap
                                lineHeight: 1.25
                            }
                        }
                    }
                }
            }
        }

        Item { Layout.preferredHeight: Theme.space5 }
    }
}
