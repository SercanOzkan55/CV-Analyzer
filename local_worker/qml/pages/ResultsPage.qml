import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"

// Ranked results: master list of candidates + detail panel for the selection.
// Pure presentation over the existing PySide6 backend (`backend`).
Item {
    id: page

    property string query: ""
    readonly property bool hasData: backend.totalCandidates > 0

    function _chips(text) {
        if (!text) return []
        return text.split(/[,\n;]+/).map(function (s) { return s.trim() }).filter(function (s) { return s.length > 0 })
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.space6
        spacing: Theme.space4

        // ── Header ──
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.space3
            Text {
                text: backend.totalCandidates + " candidate" + (backend.totalCandidates === 1 ? "" : "s") + " in this run"
                color: Theme.textSecondary
                font.pixelSize: Typography.subheadingSize
                font.weight: Typography.weightMedium
            }
            Item { Layout.fillWidth: true }
            SearchField {
                Layout.preferredWidth: 260
                visible: page.hasData
                placeholder: "Search candidates…"
                onTextChanged: page.query = text
            }
            AppButton {
                text: "Export CSV"
                visible: page.hasData
                fill: Theme.surfaceElevated; fillHover: Theme.surfaceMuted
                fillPressed: Theme.surfaceMuted; stroke: Theme.border
                textColor: Theme.textPrimary
                onClicked: backend.exportCurrentCsv()
            }
            AppButton {
                text: "Open Folder"
                fill: Theme.surfaceElevated; fillHover: Theme.surfaceMuted
                fillPressed: Theme.surfaceMuted; stroke: Theme.border
                textColor: Theme.textPrimary
                onClicked: backend.openOutputFolder()
            }
        }

        // ── Empty state (no run yet) ──
        EmptyState {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !page.hasData
            title: "No results yet"
            message: "Run a local analysis from the Analyze tab to rank candidates here."
        }

        // ── Master / detail ──
        RowLayout {
            visible: page.hasData
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Theme.space4

            // Candidate list
            AppCard {
                Layout.preferredWidth: 380
                Layout.minimumWidth: 300
                Layout.fillHeight: true
                pad: Theme.space3
                ListView {
                    id: list
                    anchors.fill: parent
                    clip: true
                    spacing: 4
                    model: backend.resultsModel
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar {}

                    delegate: ItemDelegate {
                        id: row
                        required property int index
                        required property string fileName
                        required property int score
                        required property string decisionLabel
                        required property color accent
                        required property string syncStatus

                        readonly property bool matches: page.query === ""
                            || fileName.toLowerCase().indexOf(page.query.toLowerCase()) !== -1
                        width: list.width
                        height: matches ? 66 : 0
                        visible: matches
                        padding: 0

                        background: Rectangle {
                            radius: Theme.radiusMd
                            color: backend.selectedIndex === row.index ? Theme.primarySoft
                                   : (row.hovered ? Theme.surfaceMuted : "transparent")
                            border.width: backend.selectedIndex === row.index ? 1 : 0
                            border.color: Qt.rgba(Theme.primary.r, Theme.primary.g, Theme.primary.b, 0.5)
                            Behavior on color { ColorAnimation { duration: Theme.durHover } }
                        }
                        onClicked: backend.selectResult(row.index)

                        contentItem: RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: Theme.space3
                            anchors.rightMargin: Theme.space3
                            spacing: Theme.space3
                            Rectangle {
                                width: 8; height: 8; radius: 4
                                color: row.accent
                                Layout.alignment: Qt.AlignVCenter
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 1
                                Text {
                                    text: row.fileName
                                    color: Theme.textPrimary
                                    font.pixelSize: Typography.labelSize
                                    font.weight: Typography.weightSemiBold
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                                Text {
                                    text: row.decisionLabel
                                    color: Theme.textMuted
                                    font.pixelSize: Typography.captionSize
                                }
                            }
                            Text {
                                text: row.score + "%"
                                color: row.accent
                                font.pixelSize: Typography.subheadingSize
                                font.weight: Typography.weightBold
                            }
                        }
                    }
                }
            }

            // Detail panel
            AppCard {
                Layout.fillWidth: true
                Layout.fillHeight: true

                EmptyState {
                    anchors.centerIn: parent
                    width: Math.min(parent.width - Theme.space5 * 2, 360)
                    visible: backend.selectedIndex < 0
                    title: "Select a candidate"
                    message: "Pick a candidate from the list to see their score breakdown, matched and missing skills, and risk flags."
                }

                ScrollView {
                    anchors.fill: parent
                    clip: true
                    visible: backend.selectedIndex >= 0
                    contentWidth: availableWidth

                    ColumnLayout {
                        width: parent.parent.availableWidth
                        spacing: Theme.space4

                        // Header: ring + identity + decision
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Theme.space4
                            ProgressRing {
                                implicitWidth: 96; implicitHeight: 96
                                thickness: 8
                                value: backend.selectedScoreValue
                                tint: backend.selectedScoreValue >= backend.acceptThreshold ? Theme.success : Theme.primary
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 3
                                Text {
                                    text: backend.selectedCandidateName || backend.selectedFileName
                                    color: Theme.textPrimary
                                    font.pixelSize: Typography.headingSize
                                    font.weight: Typography.weightBold
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                                Text {
                                    text: backend.selectedFileName
                                    color: Theme.textSecondary
                                    font.pixelSize: Typography.captionSize
                                    elide: Text.ElideMiddle
                                    Layout.fillWidth: true
                                }
                                Text {
                                    visible: backend.selectedEmail.length > 0
                                    text: backend.selectedEmail
                                    color: Theme.textMuted
                                    font.pixelSize: Typography.captionSize
                                }
                                RowLayout {
                                    spacing: Theme.space2
                                    Layout.topMargin: 2
                                    AppBadge { text: backend.selectedDecisionLabel; tint: Theme.primary }
                                    StatusBadge { visible: backend.selectedSyncStatus.length > 0; status: backend.selectedSyncStatus }
                                    AppBadge {
                                        visible: backend.selectedDuplicateStatus.length > 0
                                        text: backend.selectedDuplicateStatus; tint: Theme.warning
                                    }
                                }
                            }
                        }

                        // Decision actions
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Theme.space2
                            AppButton {
                                text: "Shortlist"; strong: true
                                fill: Theme.success; fillHover: Qt.lighter(Theme.success, 1.1)
                                fillPressed: Qt.darker(Theme.success, 1.1); stroke: Theme.success
                                textColor: "#04130C"
                                onClicked: backend.setSelectedDecision("accept")
                            }
                            AppButton {
                                text: "Review"
                                fill: Theme.surfaceElevated; fillHover: Theme.surfaceMuted
                                fillPressed: Theme.surfaceMuted; stroke: Theme.border
                                textColor: Theme.textPrimary
                                onClicked: backend.setSelectedDecision("review")
                            }
                            AppButton {
                                text: "Reject"
                                fill: Theme.surfaceElevated; fillHover: Theme.surfaceMuted
                                fillPressed: Theme.surfaceMuted; stroke: Theme.danger
                                textColor: Theme.danger
                                onClicked: backend.setSelectedDecision("reject")
                            }
                            Item { Layout.fillWidth: true }
                            Text {
                                visible: backend.selectedConfidence.length > 0
                                text: "Confidence: " + backend.selectedConfidence
                                color: Theme.textMuted
                                font.pixelSize: Typography.captionSize
                            }
                        }

                        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }

                        // Summary
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            visible: backend.selectedSummary.length > 0
                            Text { text: "Summary"; color: Theme.textPrimary; font.pixelSize: Typography.subheadingSize; font.weight: Typography.weightSemiBold }
                            Text {
                                Layout.fillWidth: true
                                text: backend.selectedSummary
                                color: Theme.textSecondary
                                font.pixelSize: Typography.labelSize
                                wrapMode: Text.WordWrap
                                lineHeight: Typography.lineNormal
                            }
                        }

                        // Matched skills
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            visible: page._chips(backend.selectedMatchedSkills).length > 0
                            Text { text: "Matched skills"; color: Theme.textPrimary; font.pixelSize: Typography.subheadingSize; font.weight: Typography.weightSemiBold }
                            Flow {
                                Layout.fillWidth: true
                                spacing: 6
                                Repeater {
                                    model: page._chips(backend.selectedMatchedSkills)
                                    delegate: AppBadge { required property string modelData; text: modelData; tint: Theme.success }
                                }
                            }
                        }

                        // Missing skills
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            visible: page._chips(backend.selectedMissingSkills).length > 0
                            Text { text: "Missing required skills"; color: Theme.textPrimary; font.pixelSize: Typography.subheadingSize; font.weight: Typography.weightSemiBold }
                            Flow {
                                Layout.fillWidth: true
                                spacing: 6
                                Repeater {
                                    model: page._chips(backend.selectedMissingSkills)
                                    delegate: AppBadge { required property string modelData; text: modelData; tint: Theme.danger }
                                }
                            }
                        }

                        // Risk flags
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            visible: page._chips(backend.selectedRiskFlags).length > 0
                            Text { text: "Risk flags"; color: Theme.textPrimary; font.pixelSize: Typography.subheadingSize; font.weight: Typography.weightSemiBold }
                            Flow {
                                Layout.fillWidth: true
                                spacing: 6
                                Repeater {
                                    model: page._chips(backend.selectedRiskFlags)
                                    delegate: AppBadge { required property string modelData; text: modelData; tint: Theme.warning }
                                }
                            }
                        }

                        // Explanation
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            visible: backend.selectedExplanation.length > 0
                            Text { text: "Why this score"; color: Theme.textPrimary; font.pixelSize: Typography.subheadingSize; font.weight: Typography.weightSemiBold }
                            Text {
                                Layout.fillWidth: true
                                text: backend.selectedExplanation
                                color: Theme.textSecondary
                                font.pixelSize: Typography.labelSize
                                wrapMode: Text.WordWrap
                                lineHeight: Typography.lineNormal
                            }
                        }

                        Item { Layout.preferredHeight: Theme.space4 }
                    }
                }
            }
        }
    }
}
