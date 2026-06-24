import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"

// Run history over the existing PySide6 backend. Opening a run loads it and
// routes to Results. Only backend-supported actions are surfaced (load +
// refresh) — no placeholder buttons.
ScrollView {
    id: page
    clip: true

    signal requestPage(int index)

    readonly property int gutter: Theme.space6
    readonly property int maxWidth: 1100
    function contentW() { return Math.max(0, Math.min(availableWidth - gutter * 2, maxWidth)) }
    readonly property bool hasRuns: backend.historyRunCount > 0

    ColumnLayout {
        x: Math.max(page.gutter, (page.availableWidth - page.contentW()) / 2)
        y: page.gutter
        width: page.contentW()
        spacing: Theme.space4

        // ── Header ──
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.space3
            Text {
                Layout.fillWidth: true
                text: backend.historyRunCount + " local run" + (backend.historyRunCount === 1 ? "" : "s") + " in this workspace"
                color: Theme.textSecondary
                font.pixelSize: Typography.subheadingSize
                font.weight: Typography.weightMedium
            }
            AppButton {
                text: "Refresh"
                fill: Theme.surfaceElevated; fillHover: Theme.surfaceMuted
                fillPressed: Theme.surfaceMuted; stroke: Theme.border
                textColor: Theme.textPrimary
                onClicked: backend.refreshHistory()
            }
        }

        // ── Run comparison (only when summaries exist) ──
        GridLayout {
            Layout.fillWidth: true
            visible: page.hasRuns && backend.currentRunSummary.length > 0
            columns: width < 760 ? 1 : 3
            columnSpacing: Theme.space4
            rowSpacing: Theme.space4

            AppCard {
                id: curCard
                Layout.fillWidth: true
                Layout.preferredHeight: curCol.implicitHeight + curCard.pad * 2
                ColumnLayout {
                    id: curCol; width: parent.width; spacing: 4
                    Text { text: "Latest run"; color: Theme.textMuted; font.pixelSize: Typography.captionSize; font.weight: Typography.weightSemiBold }
                    Text { Layout.fillWidth: true; text: backend.currentRunSummary; color: Theme.textPrimary; font.pixelSize: Typography.labelSize; wrapMode: Text.WordWrap }
                }
            }
            AppCard {
                id: prevCard
                Layout.fillWidth: true
                visible: backend.previousRunSummary.length > 0
                Layout.preferredHeight: prevCol.implicitHeight + prevCard.pad * 2
                ColumnLayout {
                    id: prevCol; width: parent.width; spacing: 4
                    Text { text: "Previous run"; color: Theme.textMuted; font.pixelSize: Typography.captionSize; font.weight: Typography.weightSemiBold }
                    Text { Layout.fillWidth: true; text: backend.previousRunSummary; color: Theme.textSecondary; font.pixelSize: Typography.labelSize; wrapMode: Text.WordWrap }
                }
            }
            AppCard {
                id: deltaCard
                Layout.fillWidth: true
                visible: backend.runDeltaSummary.length > 0
                Layout.preferredHeight: deltaCol.implicitHeight + deltaCard.pad * 2
                ColumnLayout {
                    id: deltaCol; width: parent.width; spacing: 4
                    Text { text: "Change"; color: Theme.textMuted; font.pixelSize: Typography.captionSize; font.weight: Typography.weightSemiBold }
                    Text { Layout.fillWidth: true; text: backend.runDeltaSummary; color: Theme.accent; font.pixelSize: Typography.labelSize; wrapMode: Text.WordWrap }
                }
            }
        }

        // ── Empty state ──
        EmptyState {
            Layout.fillWidth: true
            Layout.topMargin: Theme.space6
            visible: !page.hasRuns
            title: "No analyses yet"
            message: "Run a local analysis from the Analyze tab. Past runs are stored on this device and reloadable here."
            actionText: "Go to Analyze"
            onActionTriggered: page.requestPage(1)
        }

        // ── Run list ──
        Repeater {
            model: page.hasRuns ? backend.historyModel : null
            delegate: AppCard {
                id: runCard
                required property int runId
                required property string jobName
                required property string createdAt
                required property int totalFiles
                required property string cvFolder

                Layout.fillWidth: true
                hoverable: true
                Layout.preferredHeight: runRow.implicitHeight + runCard.pad * 2

                RowLayout {
                    id: runRow
                    width: parent.width
                    spacing: Theme.space4

                    Rectangle {
                        Layout.alignment: Qt.AlignVCenter
                        width: 42; height: 42; radius: Theme.radiusMd
                        color: Theme.primarySoft
                        Text {
                            anchors.centerIn: parent
                            text: runCard.totalFiles
                            color: Theme.primary
                            font.pixelSize: Typography.subheadingSize
                            font.weight: Typography.weightBold
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            Layout.fillWidth: true
                            text: runCard.jobName
                            color: Theme.textPrimary
                            font.pixelSize: Typography.subheadingSize
                            font.weight: Typography.weightSemiBold
                            elide: Text.ElideRight
                        }
                        Text {
                            Layout.fillWidth: true
                            text: runCard.createdAt + "  ·  " + runCard.totalFiles + " file(s)"
                            color: Theme.textMuted
                            font.pixelSize: Typography.captionSize
                        }
                        Text {
                            Layout.fillWidth: true
                            visible: runCard.cvFolder.length > 0
                            text: runCard.cvFolder
                            color: Theme.textMuted
                            font.pixelSize: Typography.captionSize
                            elide: Text.ElideMiddle
                        }
                    }

                    AppButton {
                        text: "Open"
                        strong: true
                        fill: Theme.primary; fillHover: Theme.primaryHover
                        fillPressed: Qt.darker(Theme.primary, 1.15); stroke: Theme.primary
                        textColor: "#ffffff"
                        onClicked: {
                            backend.loadRun(runCard.runId)
                            page.requestPage(2)
                        }
                    }
                }
            }
        }

        Item { Layout.preferredHeight: Theme.space5 }
    }
}
