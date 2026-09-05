import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
import "../components"
import "../logic/WeightAllocator.js" as WeightAllocator

// Step-based analysis setup over the existing PySide6 backend. Cards are
// content-sized (preferredHeight bound to their inner column) because the page
// scrolls — there is no fixed height to fill against.
ScrollView {
    id: page
    Layout.fillWidth: true
    Layout.fillHeight: true
    clip: true

    signal requestBrowseCv()
    signal requestBrowseOutput()

    readonly property int gutter: Theme.space6
    readonly property int maxWidth: 1280
    function contentW() { return Math.max(0, Math.min(availableWidth - gutter * 2, maxWidth)) }

    ColumnLayout {
        x: Math.max(page.gutter, (page.availableWidth - page.contentW()) / 2)
        y: page.gutter
        width: page.contentW()
        spacing: Theme.space5

        // ── Setup flow ──
        AppCard {
            id: setupCard
            Layout.fillWidth: true
            Layout.preferredHeight: setupCol.implicitHeight + setupCard.pad * 2
            ColumnLayout {
                id: setupCol
                width: parent.width
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
                id: jobCard
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                Layout.preferredHeight: jobCol.implicitHeight + jobCard.pad * 2
                ColumnLayout {
                    id: jobCol
                    width: parent.width
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
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: 40
                            radius: Theme.radiusMd
                            color: Theme.surfaceMuted
                            border.width: 1
                            border.color: Theme.border
                            Text {
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 12
                                verticalAlignment: Text.AlignVCenter
                                text: backend.cvFolder && backend.cvFolder.length > 0 ? backend.cvFolder : "No folder selected"
                                color: backend.cvFolder && backend.cvFolder.length > 0 ? Theme.textPrimary : Theme.textMuted
                                font.pixelSize: Typography.labelSize
                                elide: Text.ElideMiddle
                            }
                        }
                        AppButton {
                            text: "Browse"
                            fill: Theme.surfaceElevated; fillHover: Theme.surfaceMuted
                            fillPressed: Theme.surfaceMuted; stroke: Theme.border
                            textColor: Theme.textPrimary
                            onClicked: page.requestBrowseCv()
                        }
                    }
                    // File-count feedback so an empty / wrong folder is obvious.
                    Text {
                        Layout.fillWidth: true
                        visible: backend.cvFileCount >= 0
                        text: backend.cvFileCount > 0
                              ? (backend.cvFileCount + " supported CV file(s) found  ·  .pdf · .docx · .txt")
                              : "No supported CV files in this folder. Pick the folder that directly contains your CVs."
                        color: backend.cvFileCount > 0 ? Theme.success : Theme.warning
                        font.pixelSize: Typography.captionSize
                        wrapMode: Text.WordWrap
                    }

                    Text { text: "OUTPUT FOLDER"; color: Theme.textMuted; font.pixelSize: Typography.captionSize; font.weight: Typography.weightSemiBold }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.space2
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: 40
                            radius: Theme.radiusMd
                            color: Theme.surfaceMuted
                            border.width: 1
                            border.color: Theme.border
                            Text {
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 12
                                verticalAlignment: Text.AlignVCenter
                                text: backend.outputFolder && backend.outputFolder.length > 0 ? backend.outputFolder : "Default output folder"
                                color: backend.outputFolder && backend.outputFolder.length > 0 ? Theme.textPrimary : Theme.textMuted
                                font.pixelSize: Typography.labelSize
                                elide: Text.ElideMiddle
                            }
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
                        Layout.preferredHeight: 150
                        placeholder: "Paste the job description or role expectations…"
                        text: backend.jobDescription
                        onEditingFinished: backend.jobDescription = text
                    }
                }
            }

            // Scoring criteria
            AppCard {
                id: scoreCard
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                Layout.preferredHeight: scoreCol.implicitHeight + scoreCard.pad * 2
                ColumnLayout {
                    id: scoreCol
                    width: parent.width
                    spacing: Theme.space3

                    // Which category rows are expanded to show member sliders.
                    property var expandedCategories: ({})

                    // Sanity-check display only — the redistribution functions
                    // below are designed to keep this at exactly 100 at all
                    // times; if it's ever anything else, that's a bug.
                    readonly property int liveWeightTotal: {
                        var sum = 0
                        var weights = backend.scoringWeights
                        for (var k in weights) sum += weights[k]
                        return sum
                    }

                    function membersFor(catKey) {
                        var out = []
                        var catalog = backend.criteriaCatalog
                        for (var i = 0; i < catalog.length; i++) {
                            if (catalog[i].category === catKey) out.push(catalog[i])
                        }
                        return out
                    }

                    // Sum of a category's members' CURRENT weights from
                    // backend.scoringWeights. Reserved members are never in
                    // that map, so a fully-reserved category (Background)
                    // naturally aggregates to 0 — no special-casing needed.
                    function categoryAggregate(catKey) {
                        var members = scoreCol.membersFor(catKey)
                        var weights = backend.scoringWeights
                        var sum = 0
                        for (var i = 0; i < members.length; i++) {
                            var w = weights[members[i].key]
                            sum += (w !== undefined ? w : 0)
                        }
                        return sum
                    }

                    // A category is locked (not-yet-scorable) when every one
                    // of its members has hasScorer=false — driven entirely by
                    // criteriaCatalog data, not by hardcoded key names, so
                    // this keeps working unchanged once Phase 4 lands.
                    function isCategoryLocked(catKey) {
                        var members = scoreCol.membersFor(catKey)
                        if (members.length === 0) return false
                        for (var i = 0; i < members.length; i++) {
                            if (members[i].hasScorer) return false
                        }
                        return true
                    }

                    function toggleExpanded(catKey) {
                        var next = {}
                        for (var k in scoreCol.expandedCategories) next[k] = scoreCol.expandedCategories[k]
                        next[catKey] = !next[catKey]
                        scoreCol.expandedCategories = next
                    }

                    function categoryTint(catKey) {
                        if (catKey === "skills_match") return Theme.primary
                        if (catKey === "job_fit") return Theme.secondary
                        if (catKey === "cv_quality") return Theme.accent
                        return Theme.textMuted
                    }

                    // Pushes a WeightAllocator result to the backend in ONE
                    // atomic call (setScoringWeights), ordered the one way
                    // that's always safe for the per-key clamp
                    // (`clamp_scoring_weight`) to land every key exactly on
                    // target: decreases before increases. See
                    // WeightAllocator.orderForApply's docstring for why the
                    // order matters, and setScoringWeights' docstring for
                    // why this must be one call, not one call per key —
                    // multiple calls each fire their own change signal, so
                    // sliders bound to a category's live aggregate (their
                    // `to:` range) visibly jump through every intermediate
                    // state of the batch instead of just the final one.
                    function applyWeights(updates) {
                        var oldByKey = {}
                        for (var i = 0; i < updates.length; i++) {
                            oldByKey[updates[i].key] = backend.getScoringWeight(updates[i].key)
                        }
                        var ordered = WeightAllocator.orderForApply(oldByKey, updates)
                        backend.setScoringWeights(ordered)
                    }

                    // Category slider moved: redistribute the aggregate delta
                    // across the OTHER live categories (a disk-usage-style
                    // budget bar), then scale every affected category's own
                    // members proportionally so their weights follow along.
                    function onCategoryMoved(catKey, newValue) {
                        var cats = backend.categoryCatalog.map(function (c) {
                            return { key: c.key, value: scoreCol.categoryAggregate(c.key), locked: scoreCol.isCategoryLocked(c.key) }
                        })
                        var targets = WeightAllocator.redistribute(cats, 100, catKey, newValue)
                        var updates = []
                        for (var i = 0; i < targets.length; i++) {
                            if (scoreCol.isCategoryLocked(targets[i].key)) continue
                            var members = scoreCol.membersFor(targets[i].key).map(function (m) {
                                return { key: m.key, value: backend.getScoringWeight(m.key), locked: !m.hasScorer }
                            })
                            var scaled = WeightAllocator.scaleGroup(members, targets[i].value)
                            updates = updates.concat(scaled)
                        }
                        scoreCol.applyWeights(updates)
                    }

                    // Member slider moved: redistribute the delta across the
                    // OTHER members of the SAME category only — the
                    // category's own aggregate never changes from this.
                    function onMemberMoved(catKey, memberKey, newValue) {
                        var members = scoreCol.membersFor(catKey).map(function (m) {
                            return { key: m.key, value: backend.getScoringWeight(m.key), locked: !m.hasScorer }
                        })
                        var budget = scoreCol.categoryAggregate(catKey)
                        var targets = WeightAllocator.redistribute(members, budget, memberKey, newValue)
                        scoreCol.applyWeights(targets)
                    }

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

                    Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border; Layout.topMargin: 4 }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.space3
                        Text {
                            text: "SCORING WEIGHTS"
                            color: Theme.textMuted; font.pixelSize: Typography.captionSize; font.weight: Typography.weightSemiBold
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: "Total: " + scoreCol.liveWeightTotal + " / 100"
                            color: scoreCol.liveWeightTotal === 100 ? Theme.textSecondary : Theme.warning
                            font.pixelSize: Typography.labelSize
                            font.weight: Typography.weightBold
                        }
                    }

                    // Presets, driven off criteria.PRESETS via backend.presetCatalog.
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Theme.space2
                        Repeater {
                            model: backend.presetCatalog
                            delegate: AppButton {
                                required property var modelData
                                Layout.fillWidth: true
                                text: modelData.label
                                fill: Theme.surfaceElevated; fillHover: Theme.surfaceMuted
                                fillPressed: Theme.surfaceMuted; stroke: Theme.border
                                textColor: Theme.textPrimary
                                onClicked: backend.applyPreset(modelData.key)
                            }
                        }
                    }

                    // 4-category budget bar. Each row expands to reveal its
                    // member criteria for power users.
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.space3

                        Repeater {
                            model: backend.categoryCatalog
                            delegate: ColumnLayout {
                                id: catRow
                                required property var modelData
                                readonly property string catKey: modelData.key
                                readonly property var members: scoreCol.membersFor(catKey)
                                readonly property bool locked: scoreCol.isCategoryLocked(catKey)
                                readonly property int aggregate: scoreCol.categoryAggregate(catKey)
                                readonly property bool expanded: scoreCol.expandedCategories[catKey] === true
                                readonly property color tint: scoreCol.categoryTint(catKey)

                                Layout.fillWidth: true
                                spacing: 6
                                opacity: catRow.locked ? 0.55 : 1
                                Behavior on opacity { NumberAnimation { duration: Theme.durHover } }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: Theme.space2

                                    Rectangle {
                                        id: chevronBtn
                                        Layout.preferredWidth: 22
                                        Layout.preferredHeight: 22
                                        radius: Theme.radiusSm
                                        color: chevronArea.containsMouse ? Theme.surfaceMuted : "transparent"
                                        Text {
                                            anchors.centerIn: parent
                                            text: catRow.expanded ? "⌄" : "›"
                                            color: Theme.textMuted
                                            font.pixelSize: Typography.labelSize
                                            font.weight: Typography.weightBold
                                        }
                                        MouseArea {
                                            id: chevronArea
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: scoreCol.toggleExpanded(catRow.catKey)
                                        }
                                    }

                                    Text {
                                        text: catRow.modelData.label
                                        color: Theme.textPrimary
                                        font.pixelSize: Typography.labelSize
                                        font.weight: Typography.weightSemiBold
                                        Layout.fillWidth: true
                                    }

                                    AppBadge { visible: catRow.locked; text: "Coming soon"; tint: Theme.textMuted }

                                    Text {
                                        text: catRow.aggregate + " / 100"
                                        color: Theme.textSecondary
                                        font.pixelSize: Typography.captionSize
                                        font.weight: Typography.weightSemiBold
                                    }
                                }

                                AppSlider {
                                    Layout.fillWidth: true
                                    enabled: !catRow.locked
                                    tint: catRow.tint
                                    value: catRow.aggregate
                                    onMoved: scoreCol.onCategoryMoved(catRow.catKey, Math.round(value))
                                }

                                Text {
                                    visible: catRow.locked
                                    Layout.fillWidth: true
                                    text: "Reserved for " + catRow.members.map(function (m) { return m.label }).join(", ") + " — not scored yet."
                                    color: Theme.textMuted
                                    font.pixelSize: Typography.captionSize
                                    wrapMode: Text.WordWrap
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.leftMargin: Theme.space5
                                    Layout.topMargin: 2
                                    Layout.bottomMargin: 4
                                    spacing: Theme.space2
                                    visible: catRow.expanded

                                    Repeater {
                                        model: catRow.members
                                        delegate: ColumnLayout {
                                            id: memberRow
                                            required property var modelData
                                            readonly property bool memberLocked: !modelData.hasScorer
                                            readonly property int memberWeight: memberRow.memberLocked
                                                ? 0
                                                : (backend.scoringWeights[modelData.key] !== undefined ? backend.scoringWeights[modelData.key] : 0)

                                            Layout.fillWidth: true
                                            spacing: 3
                                            opacity: memberRow.memberLocked ? 0.6 : 1

                                            RowLayout {
                                                Layout.fillWidth: true
                                                spacing: Theme.space2
                                                Text {
                                                    text: memberRow.modelData.label
                                                    color: Theme.textSecondary
                                                    font.pixelSize: Typography.captionSize
                                                    font.weight: Typography.weightMedium
                                                    Layout.fillWidth: true
                                                }
                                                AppBadge { visible: memberRow.memberLocked; text: "Coming soon"; tint: Theme.textMuted }
                                                Text {
                                                    text: memberRow.memberWeight
                                                    color: Theme.textMuted
                                                    font.pixelSize: Typography.captionSize
                                                }
                                            }
                                            AppSlider {
                                                Layout.fillWidth: true
                                                implicitHeight: 18
                                                enabled: !memberRow.memberLocked && catRow.aggregate > 0
                                                to: Math.max(1, catRow.aggregate)
                                                tint: catRow.tint
                                                value: memberRow.memberWeight
                                                onMoved: scoreCol.onMemberMoved(catRow.catKey, memberRow.modelData.key, Math.round(value))
                                            }
                                            Text {
                                                visible: memberRow.memberLocked
                                                Layout.fillWidth: true
                                                text: memberRow.modelData.description
                                                color: Theme.textMuted
                                                font.pixelSize: Typography.microSize
                                                wrapMode: Text.WordWrap
                                            }
                                        }
                                    }
                                }
                            }
                        }
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
            id: actionCard
            Layout.fillWidth: true
            elevated: true
            Layout.preferredHeight: actionCol.implicitHeight + actionCard.pad * 2
            ColumnLayout {
                id: actionCol
                width: parent.width
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
