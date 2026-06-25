import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"

// Side-by-side comparison of 2–4 analyzed candidates. Pure presentation over
// the existing PySide6 backend: reads backend.compareRows (real result data),
// no fabricated fields.
ScrollView {
    id: page
    clip: true

    signal requestPage(int index)

    readonly property int gutter: Theme.space6
    readonly property int maxWidth: 1320
    function contentW() { return Math.max(0, Math.min(availableWidth - gutter * 2, maxWidth)) }

    readonly property var allRows: backend.compareRows
    property var selected: []          // array of candidate dicts (max 4)
    readonly property int maxScore: {
        var m = -1
        for (var i = 0; i < selected.length; i++) m = Math.max(m, selected[i].score)
        return m
    }

    function isSelected(cand) {
        for (var i = 0; i < selected.length; i++)
            if (selected[i].fileName === cand.fileName) return true
        return false
    }
    function toggle(cand) {
        var next = []
        var found = false
        for (var i = 0; i < selected.length; i++) {
            if (selected[i].fileName === cand.fileName) { found = true; continue }
            next.push(selected[i])
        }
        if (!found && next.length < 4) next.push(cand)
        selected = next
    }
    function chips(text) {
        if (!text) return []
        return text.split(/[,\n;]+/).map(function (s) { return s.trim() }).filter(function (s) { return s.length > 0 })
    }

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
                Text { text: "Compare candidates"; color: Theme.textPrimary; font.pixelSize: Typography.titleSize; font.weight: Typography.weightBold }
                Text {
                    Layout.fillWidth: true
                    text: page.selected.length + " of 4 selected · pick 2–4 to compare side by side"
                    color: Theme.textSecondary
                    font.pixelSize: Typography.labelSize
                }
            }
            AppButton {
                text: "Clear"
                visible: page.selected.length > 0
                fill: Theme.surfaceElevated; fillHover: Theme.surfaceMuted
                fillPressed: Theme.surfaceMuted; stroke: Theme.border
                textColor: Theme.textPrimary
                onClicked: page.selected = []
            }
        }

        // ── No analysis yet ──
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 320
            visible: page.allRows.length < 2
            EmptyState {
                anchors.centerIn: parent
                width: Math.min(parent.width, 440)
                title: page.allRows.length === 0 ? "No candidates yet" : "Need at least 2 candidates"
                message: page.allRows.length === 0
                         ? "Run a local analysis from the Analyze tab. Comparison needs at least two ranked candidates."
                         : "Only one candidate in this run — analyze a folder with more CVs to compare."
                actionText: "Go to Analyze"
                onActionTriggered: page.requestPage(1)
            }
        }

        // ── Candidate picker ──
        AppCard {
            id: pickerCard
            Layout.fillWidth: true
            visible: page.allRows.length >= 2
            Layout.preferredHeight: pickerCol.implicitHeight + pickerCard.pad * 2
            ColumnLayout {
                id: pickerCol
                width: parent.width
                spacing: Theme.space3
                SectionHeader { Layout.fillWidth: true; title: "Candidates"; subtitle: "Click to add or remove (up to 4)." }
                Flow {
                    Layout.fillWidth: true
                    spacing: Theme.space2
                    Repeater {
                        model: page.allRows
                        delegate: Rectangle {
                            id: chip
                            required property var modelData
                            readonly property bool on: page.isSelected(modelData)
                            readonly property bool atLimit: page.selected.length >= 4 && !on
                            implicitHeight: 36
                            implicitWidth: chipRow.implicitWidth + 26
                            radius: Theme.radiusMd
                            color: on ? Theme.primarySoft : Theme.surfaceMuted
                            border.width: 1
                            border.color: on ? Theme.primary : Theme.border
                            opacity: atLimit ? 0.5 : 1
                            Behavior on color { ColorAnimation { duration: Theme.durHover } }
                            Behavior on border.color { ColorAnimation { duration: Theme.durHover } }
                            RowLayout {
                                id: chipRow
                                anchors.centerIn: parent
                                spacing: 8
                                Rectangle {
                                    width: 16; height: 16; radius: 4
                                    color: chip.on ? Theme.primary : "transparent"
                                    border.width: 1
                                    border.color: chip.on ? Theme.primary : Theme.borderStrong
                                    Text { anchors.centerIn: parent; visible: chip.on; text: "✓"; color: "#ffffff"; font.pixelSize: 11; font.weight: Typography.weightBold }
                                }
                                Text { text: chip.modelData.name; color: Theme.textPrimary; font.pixelSize: Typography.labelSize; font.weight: Typography.weightMedium }
                                Text { text: chip.modelData.score + "%"; color: Theme.textMuted; font.pixelSize: Typography.captionSize; font.weight: Typography.weightSemiBold }
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: chip.atLimit ? Qt.ArrowCursor : Qt.PointingHandCursor
                                onClicked: if (!chip.atLimit) page.toggle(chip.modelData)
                            }
                        }
                    }
                }
            }
        }

        // ── Hint when <2 picked ──
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 200
            visible: page.allRows.length >= 2 && page.selected.length < 2
            EmptyState {
                anchors.centerIn: parent
                width: Math.min(parent.width, 420)
                title: "Pick candidates to compare"
                message: "Select at least two candidates above to see a side-by-side breakdown of scores, skills and risks."
            }
        }

        // ── Comparison columns ──
        ScrollView {
            Layout.fillWidth: true
            Layout.preferredHeight: cmpRow.implicitHeight
            visible: page.selected.length >= 2
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AsNeeded
            contentWidth: cmpRow.implicitWidth

            RowLayout {
                id: cmpRow
                spacing: Theme.space4
                Repeater {
                    model: page.selected
                    delegate: AppCard {
                        id: col
                        required property var modelData
                        readonly property bool isTop: modelData.score === page.maxScore && page.maxScore >= 0
                        Layout.alignment: Qt.AlignTop
                        implicitWidth: 280
                        Layout.preferredHeight: colCol.implicitHeight + col.pad * 2
                        border.color: isTop ? Theme.success : Theme.border
                        border.width: isTop ? 2 : 1

                        ColumnLayout {
                            id: colCol
                            width: parent.width
                            spacing: Theme.space3

                            // Identity + top badge
                            RowLayout {
                                Layout.fillWidth: true
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 1
                                    Text { Layout.fillWidth: true; text: col.modelData.name; color: Theme.textPrimary; font.pixelSize: Typography.subheadingSize; font.weight: Typography.weightBold; elide: Text.ElideRight }
                                    Text { Layout.fillWidth: true; text: col.modelData.fileName; color: Theme.textMuted; font.pixelSize: Typography.captionSize; elide: Text.ElideMiddle }
                                }
                                AppBadge { visible: col.isTop; text: "Top score"; tint: Theme.success }
                            }

                            // Score ring
                            ProgressRing {
                                Layout.alignment: Qt.AlignHCenter
                                implicitWidth: 92; implicitHeight: 92
                                thickness: 9
                                value: col.modelData.score
                                tint: col.isTop ? Theme.success : Theme.primary
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: Theme.space2
                                AppBadge { text: col.modelData.decision; tint: Theme.primary }
                                AppBadge { text: col.modelData.confidence; tint: Theme.info }
                                Item { Layout.fillWidth: true }
                            }

                            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }

                            // Matched skills
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 5
                                visible: page.chips(col.modelData.matched).length > 0
                                Text { text: "Matched"; color: Theme.textSecondary; font.pixelSize: Typography.captionSize; font.weight: Typography.weightSemiBold }
                                Flow {
                                    Layout.fillWidth: true
                                    spacing: 5
                                    Repeater { model: page.chips(col.modelData.matched); delegate: AppBadge { required property string modelData; text: modelData; tint: Theme.success } }
                                }
                            }
                            // Missing skills
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 5
                                visible: page.chips(col.modelData.missing).length > 0
                                Text { text: "Missing"; color: Theme.textSecondary; font.pixelSize: Typography.captionSize; font.weight: Typography.weightSemiBold }
                                Flow {
                                    Layout.fillWidth: true
                                    spacing: 5
                                    Repeater { model: page.chips(col.modelData.missing); delegate: AppBadge { required property string modelData; text: modelData; tint: Theme.danger } }
                                }
                            }
                            // Risks
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 5
                                visible: page.chips(col.modelData.risks).length > 0
                                Text { text: "Risk flags"; color: Theme.textSecondary; font.pixelSize: Typography.captionSize; font.weight: Typography.weightSemiBold }
                                Flow {
                                    Layout.fillWidth: true
                                    spacing: 5
                                    Repeater { model: page.chips(col.modelData.risks); delegate: AppBadge { required property string modelData; text: modelData; tint: Theme.warning } }
                                }
                            }

                            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }

                            RowLayout {
                                Layout.fillWidth: true
                                Text { text: "Sync"; color: Theme.textMuted; font.pixelSize: Typography.captionSize; Layout.fillWidth: true }
                                StatusBadge { status: col.modelData.sync }
                            }
                            Text {
                                Layout.fillWidth: true
                                visible: col.modelData.email.length > 0
                                text: col.modelData.email
                                color: Theme.textMuted
                                font.pixelSize: Typography.captionSize
                                elide: Text.ElideMiddle
                            }
                        }
                    }
                }
            }
        }

        Item { Layout.preferredHeight: Theme.space5 }
    }
}
