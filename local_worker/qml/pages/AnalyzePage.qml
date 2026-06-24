import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"

// Step-based analysis setup over the existing PySide6 backend. Folder pickers
// are raised as signals so the shell owns the FolderDialogs.
ScrollView {
    id: page
    clip: true

    signal requestBrowseCv()
    signal requestBrowseOutput()

    readonly property int gutter: Theme.space6
    readonly property int maxWidth: 1280
    function contentW() { return Math.max(0, Math.min(availableWidth - gutter * 2, maxWidth)) }

    function _fieldLabel(t) { return t }

    ColumnLayout {
        x: Math.max(page.gutter, (page.availableWidth - page.contentW()) / 2)
        y: page.gutter
        width: page.contentW()
        spacing: Theme.space5

        // ── Setup flow / stepper ──
        AppCard {
            Layout.fillWidth: true
            ColumnLayout {
                anchors.fill: parent
                spacing: Theme.space3
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.space3
                    AppBadge { text: "SETUP FLOW"; tint: Theme.primary }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: backend.setupCompletion + "% ready"
                        color: Theme.textPrimary
                        font.pixelSize: Typography.subheadingSize
                        font.weight: Typography.weightBold
                    }
                }
                Text {
                    text: backend.setupStepLabel
                    color: Theme.textSecondary
                    font.pixelSize: Typography.labelSize
                }
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 6
                    radius: 3
                    color: Theme.surfaceMuted
                    Rectangle {
                        height: parent.height; radius: parent.radius
                        width: parent.width * Math.max(0, Math.min(100, backend.setupCompletion)) / 100
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0; color: Theme.primary }
                            GradientStop { position: 1; color: Theme.accent }
                        }
                        Behavior on width {
                            enabled: !Theme.reducedMotion
                            NumberAnimation { duration: Theme.durData; easing.type: Easing.OutCubic }
                        }
                    }
                }
            }
        }

        // ── Two-column form ──
        GridLayout {
            Layout.fillWidth: true
            columns: width < 900 ? 1 : 2
            columnSpacing: Theme.space4
            rowSpacing: Theme.space4

            // Local job setup
            AppCard {
                Layout.fillWidth: true
                Layout.fillHeight: true
                ColumnLayout {
                    anchors.fill: parent
                    spacing: Theme.space3

                    Text { text: "Local job setup"; color: Theme.textPrimary; font.pixelSize: Typography.headingSize; font.weight: Typography.weightBold }

                    Text { text: "JOB NAME"; color: Theme.textMuted; font.pixelSize: Typography.captionSize; font.weight: Typography.weightSemiBold }
                    AppTextField {
                        Layout.fillWidth: true
                        placeholder: "New local job"
                        text: backend.jobName
                        onEditingFinished: backend.jobName = text
                    }

                    Text { text: "CV FOLDER"; color: Theme.textMuted; font.pixelSize: Typography.captionSize; font.weight: Typography.weightSemiBold }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.space2
                        AppTextField {
                            Layout.fillWidth: true
                            readOnlyField: true
                            placeholder: "No folder selected"
                            text: backend.cvFolder
                        }
                        AppButton {
                            text: "Browse"
                            fill: Theme.surfaceElevated; fillHover: Theme.surfaceMuted
                            fillPressed: Theme.surfaceMuted; stroke: Theme.border
                            textColor: Theme.textPrimary
                            onClicked: page.requestBrowseCv()
                        }
                    }

                    Text { text: "OUTPUT FOLDER"; color: Theme.textMuted; font.pixelSize: Typography.captionSize; font.weight: Typography.weightSemiBold }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.space2
                        AppTextField {
                            Layout.fillWidth: true
                            readOnlyField: true
                            text: backend.outputFolder
                        }
                        AppButton {
                            text: "Browse"
                            fill: Theme.surfaceElevated; fillHover: Theme.surfaceMuted
                            fillPressed: Theme.surfaceMuted; stroke: Theme.border
                            textColor: Theme.textPrimary
                            onClicked: page.requestBrowseOutput()
                        }
                    }

                    Text { text: "JOB DESCRIPTION"; color: Theme.textMuted; font.pixelSize: Typography.captionSize; font.weight: Typography.weightSemiBold }
                    AppTextArea {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.minimumHeight: 140
                        placeholder: "Paste the job description or role expectations…"
                        text: backend.jobDescription
                        onEditingFinished: backend.jobDescription = text
                    }
                }
            }

            // Scoring criteria
            AppCard {
                Layout.fillWidth: true
                Layout.fillHeight: true
                ColumnLayout {
                    anchors.fill: parent
                    spacing: Theme.space3

                    Text { text: "Scoring criteria"; color: Theme.textPrimary; font.pixelSize: Typography.headingSize; font.weight: Typography.weightBold }

                    Text { text: "REQUIRED SKILLS"; color: Theme.textMuted; font.pixelSize: Typography.captionSize; font.weight: Typography.weightSemiBold }
                    AppTextField {
                        Layout.fillWidth: true
                        placeholder: "Python, React, SQL…"
                        text: backend.requiredSkills
                        onEditingFinished: backend.requiredSkills = text
                    }

                    Text { text: "NICE TO HAVE"; color: Theme.textMuted; font.pixelSize: Typography.captionSize; font.weight: Typography.weightSemiBold }
                    AppTextField {
                        Layout.fillWidth: true
                        placeholder: "Docker, GraphQL, AWS…"
                        text: backend.niceToHaveSkills
                        onEditingFinished: backend.niceToHaveSkills = text
                    }

                    Text { text: "HARD REJECT CRITERIA"; color: Theme.textMuted; font.pixelSize: Typography.captionSize; font.weight: Typography.weightSemiBold }
                    AppTextField {
                        Layout.fillWidth: true
                        placeholder: "Missing work permit, wrong seniority…"
                        text: backend.hardRejectCriteria
                        onEditingFinished: backend.hardRejectCriteria = text
                    }

                    Text {
                        text: "ACCEPT THRESHOLD: " + backend.acceptThreshold + "%"
                        color: Theme.textSecondary; font.pixelSize: Typography.labelSize; font.weight: Typography.weightMedium
                        Layout.topMargin: 4
                    }
                    AppSlider {
                        Layout.fillWidth: true
                        tint: Theme.success
                        value: backend.acceptThreshold
                        onMoved: backend.acceptThreshold = Math.round(value)
                    }

                    Text {
                        text: "REVIEW THRESHOLD: " + backend.reviewThreshold + "%"
                        color: Theme.textSecondary; font.pixelSize: Typography.labelSize; font.weight: Typography.weightMedium
                    }
                    AppSlider {
                        Layout.fillWidth: true
                        tint: Theme.warning
                        value: backend.reviewThreshold
                        onMoved: backend.reviewThreshold = Math.round(value)
                    }

                    Text { text: "AI REVIEW MODE"; color: Theme.textMuted; font.pixelSize: Typography.captionSize; font.weight: Typography.weightSemiBold; Layout.topMargin: 4 }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.space2
                        AppButton {
                            Layout.fillWidth: true
                            text: "Local only"
                            strong: backend.aiMode === "none"
                            fill: backend.aiMode === "none" ? Theme.primary : Theme.surfaceElevated
                            fillHover: backend.aiMode === "none" ? Theme.primaryHover : Theme.surfaceMuted
                            fillPressed: Theme.surfaceMuted
                            stroke: backend.aiMode === "none" ? Theme.primary : Theme.border
                            textColor: backend.aiMode === "none" ? "#ffffff" : Theme.textPrimary
                            onClicked: backend.aiMode = "none"
                        }
                        AppButton {
                            Layout.fillWidth: true
                            text: "AI review (your key)"
                            strong: backend.aiMode !== "none"
                            fill: backend.aiMode !== "none" ? Theme.primary : Theme.surfaceElevated
                            fillHover: backend.aiMode !== "none" ? Theme.primaryHover : Theme.surfaceMuted
                            fillPressed: Theme.surfaceMuted
                            stroke: backend.aiMode !== "none" ? Theme.primary : Theme.border
                            textColor: backend.aiMode !== "none" ? "#ffffff" : Theme.textPrimary
                            onClicked: backend.aiMode = "customer_openai_key"
                        }
                    }
                }
            }
        }

        // ── Action bar ──
        AppCard {
            Layout.fillWidth: true
            elevated: true
            ColumnLayout {
                anchors.fill: parent
                spacing: Theme.space3
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.space3
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 1
                        Text {
                            text: backend.isRunning ? "Analyzing locally…" : "Ready for offline analysis"
                            color: Theme.textPrimary
                            font.pixelSize: Typography.subheadingSize
                            font.weight: Typography.weightSemiBold
                        }
                        Text {
                            text: backend.cvFolder && backend.cvFolder.length > 0
                                  ? "CV files never leave this device."
                                  : "Select a CV folder to enable analysis."
                            color: Theme.textMuted
                            font.pixelSize: Typography.captionSize
                        }
                    }
                    AppButton {
                        text: "Cancel"
                        visible: backend.isRunning
                        fill: Theme.surfaceElevated; fillHover: Theme.surfaceMuted
                        fillPressed: Theme.surfaceMuted; stroke: Theme.danger
                        textColor: Theme.danger
                        onClicked: backend.cancelAnalysis()
                    }
                    AppButton {
                        text: backend.isRunning ? "Running…" : "Analyze local folder"
                        strong: true
                        enabled: !backend.isRunning && backend.cvFolder && backend.cvFolder.length > 0
                        fill: Theme.primary; fillHover: Theme.primaryHover
                        fillPressed: Qt.darker(Theme.primary, 1.15); stroke: Theme.primary
                        textColor: "#ffffff"
                        onClicked: backend.startAnalysis()
                    }
                }
                // Progress (only while running)
                Rectangle {
                    Layout.fillWidth: true
                    visible: backend.isRunning
                    implicitHeight: 6
                    radius: 3
                    color: Theme.surfaceMuted
                    Rectangle {
                        height: parent.height; radius: parent.radius
                        width: backend.progressMaximum > 0
                               ? parent.width * Math.max(0, Math.min(1, backend.progressValue / backend.progressMaximum))
                               : 0
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0; color: Theme.primary }
                            GradientStop { position: 1; color: Theme.secondary }
                        }
                        Behavior on width {
                            enabled: !Theme.reducedMotion
                            NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
                        }
                    }
                }
                Text {
                    visible: backend.isRunning
                    text: backend.status
                    color: Theme.textSecondary
                    font.pixelSize: Typography.captionSize
                }
            }
        }

        Item { Layout.preferredHeight: Theme.space5 }
    }
}
