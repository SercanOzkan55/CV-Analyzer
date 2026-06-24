import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"

// Flagship dashboard. Pure presentation over the existing PySide6 backend
// (global `backend` context object). Navigation + folder picking are raised as
// signals so the app shell owns routing and dialogs.
ScrollView {
    id: page
    clip: true

    signal requestPage(int index)
    signal requestBrowse()

    readonly property int gutter: Theme.space6
    readonly property int maxWidth: 1280
    function contentW() { return Math.max(0, Math.min(availableWidth - gutter * 2, maxWidth)) }

    readonly property bool hasData: backend.totalCandidates > 0 || backend.historyRunCount > 0

    ColumnLayout {
        x: Math.max(page.gutter, (page.availableWidth - page.contentW()) / 2)
        y: page.gutter
        width: page.contentW()
        spacing: Theme.space5

        // ── Header ──
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.space4
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    text: "Welcome back, Sercan"
                    color: Theme.textPrimary
                    font.pixelSize: Typography.displaySize
                    font.weight: Typography.weightBlack
                }
                Text {
                    text: "Find the perfect match from your local CV folders."
                    color: Theme.textSecondary
                    font.pixelSize: Typography.subheadingSize
                }
            }
            AppButton {
                text: "New Analysis"
                strong: true
                fill: Theme.primary
                fillHover: Theme.primaryHover
                fillPressed: Qt.darker(Theme.primary, 1.15)
                stroke: Theme.primary
                textColor: "#ffffff"
                onClicked: page.requestPage(1)
            }
        }

        // ── Folder + Overall score ──
        GridLayout {
            Layout.fillWidth: true
            columns: width < 880 ? 1 : 2
            columnSpacing: Theme.space4
            rowSpacing: Theme.space4

            // Folder / privacy card
            AppCard {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 2
                Layout.minimumHeight: 280
                ColumnLayout {
                    anchors.fill: parent
                    spacing: Theme.space3
                    RowLayout {
                        Layout.fillWidth: true
                        AppBadge { text: "PRIVATE & LOCAL"; tint: Theme.success }
                        Item { Layout.fillWidth: true }
                        StatusBadge { status: backend.isRunning ? "running" : "completed" }
                    }
                    Text {
                        text: "CV source folder"
                        color: Theme.textPrimary
                        font.pixelSize: Typography.headingSize
                        font.weight: Typography.weightBold
                    }
                    Text {
                        Layout.fillWidth: true
                        text: backend.cvFolder && backend.cvFolder.length > 0 ? backend.cvFolder : "No folder selected yet. Files never leave this device."
                        color: backend.cvFolder && backend.cvFolder.length > 0 ? Theme.textSecondary : Theme.textMuted
                        font.pixelSize: Typography.labelSize
                        elide: Text.ElideMiddle
                        maximumLineCount: 2
                        wrapMode: Text.WrapAnywhere
                    }
                    Item { Layout.fillHeight: true }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.space2
                        AppButton {
                            text: "Browse Folder"
                            strong: true
                            fill: Theme.primary; fillHover: Theme.primaryHover
                            fillPressed: Qt.darker(Theme.primary, 1.15); stroke: Theme.primary
                            textColor: "#ffffff"
                            onClicked: page.requestBrowse()
                        }
                        AppButton {
                            text: "Analysis Setup"
                            fill: Theme.surfaceElevated; fillHover: Theme.surfaceMuted
                            fillPressed: Theme.surfaceMuted; stroke: Theme.border
                            textColor: Theme.textPrimary
                            onClicked: page.requestPage(1)
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: "PDF · DOCX · TXT"
                            color: Theme.textMuted
                            font.pixelSize: Typography.captionSize
                        }
                    }
                }
            }

            // Overall match score
            AppCard {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 280
                Layout.preferredWidth: 1
                ColumnLayout {
                    anchors.fill: parent
                    spacing: Theme.space2
                    Text {
                        text: "Overall Match Score"
                        color: Theme.textPrimary
                        font.pixelSize: Typography.headingSize
                        font.weight: Typography.weightBold
                    }
                    Item { Layout.fillHeight: true }
                    ProgressRing {
                        Layout.alignment: Qt.AlignHCenter
                        implicitWidth: 130; implicitHeight: 130
                        value: backend.averageScoreValue
                        caption: page.hasData ? "average fit" : "no score yet"
                        tint: backend.averageScoreValue >= backend.acceptThreshold ? Theme.success : Theme.primary
                    }
                    Item { Layout.fillHeight: true }
                    AppButton {
                        Layout.fillWidth: true
                        text: "View Top Candidates"
                        fill: Theme.surfaceElevated; fillHover: Theme.surfaceMuted
                        fillPressed: Theme.surfaceMuted; stroke: Theme.border
                        textColor: Theme.textPrimary
                        enabled: page.hasData
                        onClicked: page.requestPage(2)
                    }
                }
            }
        }

        // ── Stat cards ──
        GridLayout {
            Layout.fillWidth: true
            columns: width < 720 ? 2 : 4
            columnSpacing: Theme.space4
            rowSpacing: Theme.space4
            StatCard { Layout.fillWidth: true; tilt3d: true; label: "Total Analyses"; value: backend.historyRunCount; tint: Theme.secondary }
            StatCard { Layout.fillWidth: true; tilt3d: true; label: "Candidate Pool"; value: backend.totalCandidates; tint: Theme.primary }
            StatCard { Layout.fillWidth: true; tilt3d: true; label: "Average Score"; value: backend.averageScoreValue; suffix: "%"; tint: Theme.accent }
            StatCard { Layout.fillWidth: true; tilt3d: true; label: "Shortlisted"; value: backend.shortlistedCount; tint: Theme.success }
        }

        // ── Distribution + Recent ──
        GridLayout {
            Layout.fillWidth: true
            columns: width < 880 ? 1 : 2
            columnSpacing: Theme.space4
            rowSpacing: Theme.space4

            // Score distribution
            AppCard {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 230
                ColumnLayout {
                    anchors.fill: parent
                    spacing: Theme.space3
                    SectionHeader { Layout.fillWidth: true; title: "Score Distribution" }
                    ScoreBar {
                        Layout.fillWidth: true; label: "Top match (≥ accept)"; tint: Theme.success
                        value: backend.totalCandidates > 0 ? backend.topScoreCount * 100 / backend.totalCandidates : 0
                        showValue: false
                    }
                    ScoreBar {
                        Layout.fillWidth: true; label: "Review"; tint: Theme.warning
                        value: backend.totalCandidates > 0 ? backend.reviewScoreCount * 100 / backend.totalCandidates : 0
                        showValue: false
                    }
                    ScoreBar {
                        Layout.fillWidth: true; label: "Low"; tint: Theme.danger
                        value: backend.totalCandidates > 0 ? backend.lowScoreCount * 100 / backend.totalCandidates : 0
                        showValue: false
                    }
                    Item { Layout.fillHeight: true }
                    Text {
                        text: backend.duplicateCount > 0 ? (backend.duplicateCount + " possible duplicate(s) detected") : "No duplicates detected"
                        color: Theme.textMuted
                        font.pixelSize: Typography.captionSize
                    }
                }
            }

            // Recent analyses
            AppCard {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 230
                ColumnLayout {
                    anchors.fill: parent
                    spacing: Theme.space3
                    SectionHeader {
                        Layout.fillWidth: true
                        title: "Recent Analyses"
                        AppButton {
                            text: "View All"; radius: 8
                            implicitHeight: 32
                            fill: "transparent"; fillHover: Theme.surfaceMuted; fillPressed: Theme.surfaceMuted
                            stroke: Theme.border; textColor: Theme.textSecondary
                            onClicked: page.requestPage(3)
                        }
                    }
                    // Empty state — centered in the remaining space; no button
                    // here (the top folder card already offers "Browse Folder").
                    Item {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        visible: backend.historyRunCount === 0
                        EmptyState {
                            anchors.centerIn: parent
                            width: Math.min(parent.width, 360)
                            title: "No analyses yet"
                            message: "Pick a CV folder and run your first local match."
                        }
                    }
                    Repeater {
                        model: backend.historyRunCount > 0 ? backend.historyModel : null
                        delegate: Rectangle {
                            required property string jobName
                            required property string createdAt
                            required property int totalFiles
                            Layout.fillWidth: true
                            implicitHeight: 52
                            radius: Theme.radiusMd
                            color: hov.hovered ? Theme.surfaceMuted : "transparent"
                            Behavior on color { ColorAnimation { duration: Theme.durHover } }
                            HoverHandler { id: hov }
                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: Theme.space3
                                anchors.rightMargin: Theme.space3
                                spacing: Theme.space3
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 1
                                    Text {
                                        text: jobName; color: Theme.textPrimary
                                        font.pixelSize: Typography.labelSize
                                        font.weight: Typography.weightSemiBold
                                        elide: Text.ElideRight; Layout.fillWidth: true
                                    }
                                    Text {
                                        text: createdAt; color: Theme.textMuted
                                        font.pixelSize: Typography.captionSize
                                    }
                                }
                                AppBadge { text: totalFiles + " files"; tint: Theme.secondary }
                            }
                        }
                    }
                }
            }
        }

        Item { Layout.preferredHeight: Theme.space5 }
    }
}
