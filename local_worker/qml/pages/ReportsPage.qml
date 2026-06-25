import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"

// Read-only view over the local result package the worker writes to disk
// (CSV/JSON/HTML/manifest). Surfaces only backend-supported actions: export
// CSV, open the output folder, and jump to Website Sync.
ScrollView {
    id: page
    clip: true

    signal requestPage(int index)

    readonly property int gutter: Theme.space6
    readonly property int maxWidth: 1180
    function contentW() { return Math.max(0, Math.min(availableWidth - gutter * 2, maxWidth)) }
    readonly property bool hasReport: backend.totalCandidates > 0

    ColumnLayout {
        x: Math.max(page.gutter, (page.availableWidth - page.contentW()) / 2)
        y: page.gutter
        width: page.contentW()
        spacing: Theme.space5

        // ── Header ──
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2
            Text { text: "Reports & Exports"; color: Theme.textPrimary; font.pixelSize: Typography.titleSize; font.weight: Typography.weightBold }
            Text {
                Layout.fillWidth: true
                text: "Every export is written to your local output folder. Nothing leaves the device."
                color: Theme.textSecondary
                font.pixelSize: Typography.labelSize
                wrapMode: Text.WordWrap
            }
        }

        // ── Stats ──
        GridLayout {
            Layout.fillWidth: true
            columns: width < 720 ? 2 : 4
            columnSpacing: Theme.space4
            rowSpacing: Theme.space4

            StatCard { Layout.fillWidth: true; label: "Candidates"; value: backend.totalCandidates; tint: Theme.info }
            // Average is a formatted string ("-" when no run), so shown verbatim.
            StatCard {
                Layout.fillWidth: true
                label: "Average score"
                displayText: backend.averageScoreValue > 0 ? backend.averageScore : "—"
                tint: Theme.secondary
            }
            StatCard { Layout.fillWidth: true; label: "Shortlisted"; value: backend.shortlistedCount; tint: Theme.success }
            StatCard { Layout.fillWidth: true; label: "Review"; value: backend.reviewCount; tint: Theme.warning }
        }

        // ── Output package + sync manifest ──
        GridLayout {
            Layout.fillWidth: true
            columns: width < 820 ? 1 : 2
            columnSpacing: Theme.space5
            rowSpacing: Theme.space5

            AppCard {
                id: pkgCard
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                Layout.preferredHeight: pkgCol.implicitHeight + pkgCard.pad * 2
                ColumnLayout {
                    id: pkgCol
                    width: parent.width
                    spacing: Theme.space2
                    RowLayout {
                        Layout.fillWidth: true
                        SectionHeader { Layout.fillWidth: true; title: "Output package"; subtitle: "Generated on this device." }
                        AppBadge { text: "LOCAL"; tint: Theme.success }
                    }
                    Repeater {
                        model: [
                            { name: "local_worker_results.csv", kind: "Spreadsheet of ranked candidates" },
                            { name: "local_worker_results.json", kind: "Structured result payload" },
                            { name: "local_worker_report.html", kind: "Shareable HTML report" },
                            { name: "sync_manifest.json", kind: "Pending website-sync manifest" }
                        ]
                        delegate: RowLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.topMargin: 6
                            spacing: Theme.space3
                            Rectangle { width: 8; height: 8; radius: 2; color: Theme.primary; Layout.alignment: Qt.AlignVCenter }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 0
                                Text { Layout.fillWidth: true; text: modelData.name; color: Theme.textPrimary; font.pixelSize: Typography.labelSize; font.weight: Typography.weightSemiBold; font.family: "Cascadia Mono, Consolas, monospace"; elide: Text.ElideMiddle }
                                Text { Layout.fillWidth: true; text: modelData.kind; color: Theme.textMuted; font.pixelSize: Typography.captionSize }
                            }
                        }
                    }
                    Text {
                        Layout.fillWidth: true
                        Layout.topMargin: 6
                        text: "Output folder: " + (backend.outputFolder || "Default")
                        color: Theme.textMuted
                        font.pixelSize: Typography.captionSize
                        elide: Text.ElideMiddle
                    }
                }
            }

            AppCard {
                id: manifestCard
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                Layout.preferredHeight: manifestCol.implicitHeight + manifestCard.pad * 2
                ColumnLayout {
                    id: manifestCol
                    width: parent.width
                    spacing: Theme.space3
                    SectionHeader { Layout.fillWidth: true; title: "Sync manifest"; subtitle: "Results queued for optional website sync." }
                    Text {
                        Layout.fillWidth: true
                        text: backend.syncPendingCount > 0
                              ? backend.syncPendingCount + " result(s) waiting for website sync."
                              : "Nothing is queued. Run an analysis or change a decision to build a manifest."
                        color: Theme.textSecondary
                        font.pixelSize: Typography.labelSize
                        wrapMode: Text.WordWrap
                    }
                    AppButton {
                        Layout.fillWidth: true
                        text: "Open Website Sync"
                        strong: backend.syncPendingCount > 0
                        fill: backend.syncPendingCount > 0 ? Theme.primary : Theme.surfaceElevated
                        fillHover: backend.syncPendingCount > 0 ? Theme.primaryHover : Theme.surfaceMuted
                        fillPressed: backend.syncPendingCount > 0 ? Qt.darker(Theme.primary, 1.15) : Theme.surfaceMuted
                        stroke: backend.syncPendingCount > 0 ? Theme.primary : Theme.border
                        textColor: backend.syncPendingCount > 0 ? "#ffffff" : Theme.textPrimary
                        onClicked: page.requestPage(4)
                    }
                }
            }
        }

        // ── Report preview ──
        AppCard {
            id: previewCard
            Layout.fillWidth: true
            Layout.preferredHeight: page.hasReport ? 460 : 300
            ColumnLayout {
                anchors.fill: parent
                spacing: Theme.space4

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.space2
                    SectionHeader { Layout.fillWidth: true; title: "Local report preview"; subtitle: "Read-only snapshot of the latest run." }
                    AppButton {
                        text: "Export CSV"
                        enabled: page.hasReport
                        fill: Theme.surfaceElevated; fillHover: Theme.surfaceMuted
                        fillPressed: Theme.surfaceMuted; stroke: Theme.border
                        textColor: Theme.textPrimary
                        onClicked: backend.exportCurrentCsv()
                    }
                    AppButton {
                        text: "Open output"
                        fill: Theme.surfaceElevated; fillHover: Theme.surfaceMuted
                        fillPressed: Theme.surfaceMuted; stroke: Theme.border
                        textColor: Theme.textPrimary
                        onClicked: backend.openOutputFolder()
                    }
                }

                AppTextArea {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: page.hasReport
                    readOnlyField: true
                    mono: true
                    text: backend.reportPreview
                }

                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: !page.hasReport
                    EmptyState {
                        anchors.centerIn: parent
                        width: Math.min(parent.width, 460)
                        title: "No report yet"
                        message: "Run a local analysis to generate CSV, JSON, an HTML report and a sync manifest. They will appear here and in your output folder."
                        actionText: "Start analysis"
                        onActionTriggered: page.requestPage(1)
                    }
                }
            }
        }

        Item { Layout.preferredHeight: Theme.space5 }
    }
}
