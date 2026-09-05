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
    // 0 = candidate list + detail, 1 = report & exports (folded in from the
    // former standalone Reports page).
    property int resultsTab: 0
    readonly property bool hasData: backend.totalCandidates > 0

    // Bulk email selection. Lives in QML only (row indices into
    // backend.resultsModel / backend.compareRows) -- transient, not
    // persisted, not a new role on the Python model.
    property var selectedIndices: []
    readonly property bool bulkSending: backend.bulkSendTotal > 0 && backend.bulkSendProgress < backend.bulkSendTotal

    function isSelected(index) {
        return page.selectedIndices.indexOf(index) !== -1
    }

    function toggleSelection(index) {
        var arr = page.selectedIndices.slice()
        var pos = arr.indexOf(index)
        if (pos === -1) arr.push(index)
        else arr.splice(pos, 1)
        page.selectedIndices = arr
    }

    function clearSelection() {
        page.selectedIndices = []
    }

    // backend.compareRows already exposes every current candidate as a
    // plain dict (score, email, etc.) for the Compare page -- reused here
    // as the bulk-read of scores the ResultListModel itself doesn't expose
    // to JS, so no new backend role is needed just for this shortcut.
    function selectBelowThreshold(threshold) {
        var arr = []
        var rows = backend.compareRows
        for (var i = 0; i < rows.length; i++) {
            if (rows[i].score < threshold) arr.push(i)
        }
        page.selectedIndices = arr
    }

    function _chips(text) {
        if (!text) return []
        return text.split(/[,\n;]+/).map(function (s) { return s.trim() }).filter(function (s) { return s.length > 0 })
    }

    // Groups a flat score_breakdown dict ({criterionKey: value, ...}) into
    // the same 4 categories the Analyze page's weight budget uses, via
    // backend.categoryCatalog/criteriaCatalog — no criterion names
    // hardcoded here either. A category with nothing scored (e.g.
    // "Background", whose 3 members never appear in score_breakdown while
    // they're reserved) is simply omitted rather than shown empty.
    function breakdownGroups(breakdown) {
        var groups = []
        var cats = backend.categoryCatalog
        var catalog = backend.criteriaCatalog
        for (var i = 0; i < cats.length; i++) {
            var catKey = cats[i].key
            var items = []
            for (var j = 0; j < catalog.length; j++) {
                var c = catalog[j]
                if (c.category === catKey && breakdown && breakdown.hasOwnProperty(c.key)) {
                    items.push({ key: c.key, label: c.label, value: breakdown[c.key] })
                }
            }
            if (items.length > 0) groups.push({ key: catKey, label: cats[i].label, items: items })
        }
        return groups
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
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !page.hasData
            EmptyState {
                anchors.centerIn: parent
                width: Math.min(parent.width, 420)
                title: "No results yet"
                message: "Run a local analysis from the Analyze tab to rank candidates here."
            }
        }

        // ── Tab switcher ──
        RowLayout {
            Layout.fillWidth: true
            visible: page.hasData
            spacing: Theme.space2

            AppButton {
                text: "Candidates"
                strong: page.resultsTab === 0
                fill: page.resultsTab === 0 ? Theme.primary : Theme.surfaceElevated
                fillHover: page.resultsTab === 0 ? Theme.primaryHover : Theme.surfaceMuted
                fillPressed: Theme.surfaceMuted
                stroke: page.resultsTab === 0 ? Theme.primary : Theme.border
                textColor: page.resultsTab === 0 ? "#ffffff" : Theme.textPrimary
                onClicked: page.resultsTab = 0
            }
            AppButton {
                text: "Report & Exports"
                strong: page.resultsTab === 1
                fill: page.resultsTab === 1 ? Theme.primary : Theme.surfaceElevated
                fillHover: page.resultsTab === 1 ? Theme.primaryHover : Theme.surfaceMuted
                fillPressed: Theme.surfaceMuted
                stroke: page.resultsTab === 1 ? Theme.primary : Theme.border
                textColor: page.resultsTab === 1 ? "#ffffff" : Theme.textPrimary
                onClicked: page.resultsTab = 1
            }
            Item { Layout.fillWidth: true }
        }

        // ── Bulk email toolbar ──
        AppCard {
            id: bulkCard
            Layout.fillWidth: true
            visible: page.hasData && page.resultsTab === 0
            pad: Theme.space3
            Layout.preferredHeight: bulkCol.implicitHeight + bulkCard.pad * 2
            ColumnLayout {
                id: bulkCol
                width: parent.width
                spacing: Theme.space2

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.space3

                    Text { text: "SELECT BELOW"; color: Theme.textMuted; font.pixelSize: Typography.captionSize; font.weight: Typography.weightSemiBold }
                    AppTextField {
                        id: thresholdField
                        Layout.preferredWidth: 84
                        text: "70"
                        placeholder: "Score"
                    }
                    AppButton {
                        text: "Select below"
                        fill: Theme.surfaceElevated; fillHover: Theme.surfaceMuted
                        fillPressed: Theme.surfaceMuted; stroke: Theme.border
                        textColor: Theme.textPrimary
                        onClicked: page.selectBelowThreshold(parseFloat(thresholdField.text) || 0)
                    }
                    AppButton {
                        text: "Clear selection"
                        visible: page.selectedIndices.length > 0
                        fill: Theme.surfaceElevated; fillHover: Theme.surfaceMuted
                        fillPressed: Theme.surfaceMuted; stroke: Theme.border
                        textColor: Theme.textPrimary
                        onClicked: page.clearSelection()
                    }

                    Item { Layout.fillWidth: true }

                    Text {
                        text: page.selectedIndices.length + " selected"
                        color: Theme.textSecondary
                        font.pixelSize: Typography.labelSize
                        font.weight: Typography.weightSemiBold
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.space2

                    AppButton {
                        text: "Send Accept to Selected"
                        strong: true
                        enabled: backend.smtpPasswordSet && page.selectedIndices.length > 0 && !page.bulkSending
                        fill: Theme.success; fillHover: Qt.lighter(Theme.success, 1.1)
                        fillPressed: Qt.darker(Theme.success, 1.1); stroke: Theme.success
                        textColor: "#04130C"
                        onClicked: {
                            confirmAccept.message = "Send the accept email to " + page.selectedIndices.length + " candidate(s)?"
                            confirmAccept.open()
                        }
                    }
                    AppButton {
                        text: "Send Reject to Selected"
                        enabled: backend.smtpPasswordSet && page.selectedIndices.length > 0 && !page.bulkSending
                        fill: Theme.surfaceElevated; fillHover: Theme.surfaceMuted
                        fillPressed: Theme.surfaceMuted; stroke: Theme.danger
                        textColor: Theme.danger
                        onClicked: {
                            confirmReject.message = "Send the reject email to " + page.selectedIndices.length + " candidate(s)?"
                            confirmReject.open()
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        visible: !backend.smtpPasswordSet
                        text: "Configure SMTP in Settings before sending bulk email."
                        color: Theme.warning
                        font.pixelSize: Typography.captionSize
                        wrapMode: Text.WordWrap
                    }

                    Item { Layout.fillWidth: true; visible: backend.smtpPasswordSet }

                    Text {
                        visible: page.bulkSending
                        text: "Sending " + backend.bulkSendProgress + " / " + backend.bulkSendTotal + "…"
                        color: Theme.textSecondary
                        font.pixelSize: Typography.captionSize
                    }
                }
            }
        }

        // ── Master / detail ──
        RowLayout {
            visible: page.hasData && page.resultsTab === 0
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
                            CheckBox {
                                Layout.alignment: Qt.AlignVCenter
                                checked: page.isSelected(row.index)
                                onToggled: page.toggleSelection(row.index)
                            }
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

                        // Score breakdown — per-criterion contribution,
                        // grouped by the same 4 categories as the Analyze
                        // page's weight budget (backend.selectedScoreBreakdown).
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: Theme.space3
                            visible: page.breakdownGroups(backend.selectedScoreBreakdown).length > 0

                            Text { text: "Score breakdown"; color: Theme.textPrimary; font.pixelSize: Typography.subheadingSize; font.weight: Typography.weightSemiBold }
                            Text {
                                Layout.fillWidth: true
                                text: "Points earned toward this run's weight allocation for each criterion."
                                color: Theme.textMuted
                                font.pixelSize: Typography.captionSize
                                wrapMode: Text.WordWrap
                            }

                            Repeater {
                                model: page.breakdownGroups(backend.selectedScoreBreakdown)
                                delegate: ColumnLayout {
                                    id: groupCol
                                    required property var modelData
                                    Layout.fillWidth: true
                                    spacing: Theme.space2

                                    Text {
                                        text: groupCol.modelData.label
                                        color: Theme.textMuted
                                        font.pixelSize: Typography.captionSize
                                        font.weight: Typography.weightSemiBold
                                        font.capitalization: Font.AllUppercase
                                        font.letterSpacing: 1
                                    }
                                    Repeater {
                                        model: groupCol.modelData.items
                                        delegate: ScoreBar {
                                            required property var modelData
                                            Layout.fillWidth: true
                                            label: modelData.label
                                            value: modelData.value
                                            tint: Theme.primary
                                        }
                                    }
                                }
                            }
                        }

                        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border; visible: page.breakdownGroups(backend.selectedScoreBreakdown).length > 0 }

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

        // ── Report & exports (folded in from the former standalone Reports
        // page — same local output package the worker writes to disk). ──
        ScrollView {
            id: reportScroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            visible: page.hasData && page.resultsTab === 1
            contentWidth: availableWidth

            AppCard {
                id: reportCard
                width: reportScroll.availableWidth
                ColumnLayout {
                    id: reportCol
                    width: parent.width
                    spacing: Theme.space4

                    SectionHeader {
                        Layout.fillWidth: true
                        title: "Report & exports"
                        subtitle: "Every export is written to your local output folder. Nothing leaves the device."
                    }

                    GridLayout {
                        Layout.fillWidth: true
                        columns: width < 640 ? 1 : 2
                        columnSpacing: Theme.space5
                        rowSpacing: Theme.space3
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
                    }

                    Text {
                        Layout.fillWidth: true
                        text: "Output folder: " + (backend.outputFolder || "Default")
                        color: Theme.textMuted
                        font.pixelSize: Typography.captionSize
                        elide: Text.ElideMiddle
                    }

                    Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }

                    Text { text: "Report preview"; color: Theme.textPrimary; font.pixelSize: Typography.subheadingSize; font.weight: Typography.weightSemiBold }
                    AppTextArea {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 260
                        readOnlyField: true
                        mono: true
                        text: backend.reportPreview
                    }
                }
            }
        }
    }

    ConfirmDialog {
        id: confirmAccept
        title: "Send accept email"
        confirmText: "Send"
        onConfirmed: backend.sendBulkTemplate(page.selectedIndices, "accept")
    }
    ConfirmDialog {
        id: confirmReject
        title: "Send reject email"
        confirmText: "Send"
        onConfirmed: backend.sendBulkTemplate(page.selectedIndices, "reject")
    }

    Connections {
        target: backend
        function onBulkSendDone(sent, failed) {
            page.clearSelection()
        }
    }
}
