import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"

// Outreach template editor (accept / reject) with a live preview bound to the
// currently selected candidate. Templates are persisted locally by the backend.
// Fills the cell so the editor + preview grow; spacers center the column group
// once it reaches maxWidth so it never stretches absurdly wide.
Item {
    id: page
    Layout.fillWidth: true
    Layout.fillHeight: true

    readonly property int gutter: Theme.space6
    readonly property int maxWidth: 1500

    function softFill(c) { return Qt.rgba(c.r, c.g, c.b, Theme.darkMode ? 0.18 : 0.12) }

    RowLayout {
        anchors.fill: parent
        anchors.margins: page.gutter
        spacing: 0

        // Fills the cell, then centers once it reaches maxWidth (so it never
        // stretches absurdly wide on large monitors).
        RowLayout {
            id: content
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.maximumWidth: page.maxWidth
            Layout.alignment: Qt.AlignHCenter
            spacing: Theme.space5

            // ── Actions ──
            AppCard {
                Layout.preferredWidth: 248
                Layout.fillHeight: true
                ColumnLayout {
                    anchors.fill: parent
                    spacing: Theme.space3

                    SectionHeader { Layout.fillWidth: true; title: "Template"; subtitle: "Pick the outreach to edit." }

                    AppButton {
                        Layout.fillWidth: true
                        text: "Accept template"
                        readonly property bool active: backend.templateMode === "accept"
                        fill: active ? page.softFill(Theme.success) : Theme.surfaceElevated
                        fillHover: active ? page.softFill(Theme.success) : Theme.surfaceMuted
                        fillPressed: Theme.surfaceMuted
                        stroke: active ? Theme.success : Theme.border
                        textColor: active ? Theme.success : Theme.textPrimary
                        onClicked: backend.setTemplateMode("accept")
                    }
                    AppButton {
                        Layout.fillWidth: true
                        text: "Reject template"
                        readonly property bool active: backend.templateMode === "reject"
                        fill: active ? page.softFill(Theme.danger) : Theme.surfaceElevated
                        fillHover: active ? page.softFill(Theme.danger) : Theme.surfaceMuted
                        fillPressed: Theme.surfaceMuted
                        stroke: active ? Theme.danger : Theme.border
                        textColor: active ? Theme.danger : Theme.textPrimary
                        onClicked: backend.setTemplateMode("reject")
                    }

                    Item { Layout.fillHeight: true }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: noteCol.implicitHeight + 24
                        radius: Theme.radiusMd
                        color: Theme.surfaceMuted
                        border.width: 1; border.color: Theme.border
                        ColumnLayout {
                            id: noteCol
                            anchors.left: parent.left; anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.margins: 12
                            spacing: 4
                            AppBadge { text: "LOCAL-ONLY"; tint: Theme.success }
                            Text {
                                Layout.fillWidth: true
                                text: "Templates are saved in your OS app-data folder. Nothing is uploaded."
                                color: Theme.textMuted
                                font.pixelSize: Typography.captionSize
                                wrapMode: Text.WordWrap
                            }
                        }
                    }
                }
            }

            // ── Editor ──
            AppCard {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumWidth: 360
                ColumnLayout {
                    anchors.fill: parent
                    spacing: Theme.space3

                    SectionHeader { Layout.fillWidth: true; title: "Template editor"; subtitle: "Use variables to personalise each message." }

                    Text { text: "SUBJECT"; color: Theme.textMuted; font.pixelSize: Typography.captionSize; font.weight: Typography.weightSemiBold }
                    AppTextField {
                        Layout.fillWidth: true
                        text: backend.templateSubject
                        placeholder: "e.g. Your application to {role}"
                        onTextChanged: if (backend.templateSubject !== text) backend.templateSubject = text
                    }

                    Text { text: "MESSAGE BODY"; color: Theme.textMuted; font.pixelSize: Typography.captionSize; font.weight: Typography.weightSemiBold; Layout.topMargin: 4 }
                    AppTextArea {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        text: backend.templateBody
                        placeholder: "Hi {name},\n\n…"
                        onTextChanged: if (backend.templateBody !== text) backend.templateBody = text
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.topMargin: 4
                        spacing: Theme.space2
                        Text { text: "INSERT"; color: Theme.textMuted; font.pixelSize: Typography.captionSize; font.weight: Typography.weightSemiBold; Layout.alignment: Qt.AlignVCenter }
                        Repeater {
                            model: ["{name}", "{email}", "{role}", "{score}"]
                            delegate: AppButton {
                                required property string modelData
                                Layout.preferredWidth: 86
                                implicitHeight: 38
                                text: modelData
                                fill: Theme.surfaceElevated; fillHover: Theme.surfaceMuted
                                fillPressed: Theme.surfaceMuted; stroke: Theme.border
                                textColor: Theme.textSecondary
                                onClicked: backend.insertTemplateVariable(modelData)
                            }
                        }
                        Item { Layout.fillWidth: true }
                        AppButton {
                            text: "Save"
                            strong: true
                            fill: Theme.primary; fillHover: Theme.primaryHover
                            fillPressed: Qt.darker(Theme.primary, 1.15); stroke: Theme.primary
                            textColor: "#ffffff"
                            onClicked: backend.saveTemplates()
                        }
                    }
                }
            }

            // ── Live preview ──
            AppCard {
                Layout.preferredWidth: 384
                Layout.fillHeight: true
                ColumnLayout {
                    anchors.fill: parent
                    spacing: Theme.space3

                    SectionHeader { Layout.fillWidth: true; title: "Live preview"; subtitle: "Bound to the selected candidate." }

                    // Recipient chip
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 84
                        radius: Theme.radiusMd
                        color: Theme.surfaceMuted
                        border.width: 1; border.color: Theme.border
                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 14
                            spacing: Theme.space3
                            ProgressRing {
                                Layout.preferredWidth: 56; Layout.preferredHeight: 56
                                thickness: 7
                                value: backend.selectedScoreValue > 0 ? backend.selectedScoreValue : 85
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 1
                                Text { Layout.fillWidth: true; text: backend.selectedCandidateName; color: Theme.textPrimary; font.pixelSize: Typography.labelSize; font.weight: Typography.weightBold; elide: Text.ElideRight }
                                Text { Layout.fillWidth: true; text: backend.selectedEmail; color: Theme.textSecondary; font.pixelSize: Typography.captionSize; elide: Text.ElideRight }
                                Text { Layout.fillWidth: true; text: backend.selectedDecisionLabel + "  ·  " + backend.selectedConfidence; color: Theme.textMuted; font.pixelSize: Typography.captionSize; elide: Text.ElideRight }
                            }
                        }
                    }

                    Text { text: "TO"; color: Theme.textMuted; font.pixelSize: Typography.captionSize; font.weight: Typography.weightSemiBold }
                    Text { Layout.fillWidth: true; text: backend.selectedEmail; color: Theme.textSecondary; font.pixelSize: Typography.labelSize; elide: Text.ElideRight }

                    Text { text: "SUBJECT"; color: Theme.textMuted; font.pixelSize: Typography.captionSize; font.weight: Typography.weightSemiBold; Layout.topMargin: 2 }
                    Text { Layout.fillWidth: true; text: backend.templatePreviewSubject; color: Theme.textPrimary; font.pixelSize: Typography.subheadingSize; font.weight: Typography.weightSemiBold; wrapMode: Text.WordWrap }

                    Rectangle { Layout.fillWidth: true; Layout.topMargin: 2; height: 1; color: Theme.border }

                    ScrollView {
                        id: previewScroll
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        contentWidth: availableWidth
                        Text {
                            width: previewScroll.availableWidth
                            text: backend.templatePreviewBody
                            color: Theme.textSecondary
                            font.pixelSize: Typography.labelSize
                            wrapMode: Text.WordWrap
                            lineHeight: 1.3
                        }
                    }
                }
            }
        }
    }
}
