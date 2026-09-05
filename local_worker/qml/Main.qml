import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Effects
import QtQuick.Layouts
import "theme"
import "components"
import "pages"

ApplicationWindow {
    id: root

    width: 1380
    height: 900
    minimumWidth: 980
    minimumHeight: 740
    visible: true
    title: "CV Analyzer Local Worker"
    color: Theme.background

    Behavior on color { ColorAnimation { duration: 180 } }

    property int pageAnimKey: 0
    // Collapsible sidebar: collapses to an icon-only rail so pages fill the screen.
    property bool sidebarCollapsed: false

    onPageIndexChanged: pageAnimKey += 1

    // Reactive bridge so a reduced-motion change anywhere stops animations on
    // every page immediately.
    Binding {
        target: Theme
        property: "reducedMotion"
        value: (typeof backend !== "undefined") ? !backend.motionEnabled : false
    }

    property int pageIndex: 0

    // Sidebar nav grouped into labeled sections so related pages sit
    // together instead of one flat 9-item list. `index` is the page's
    // position in the StackLayout below (pageIndex).
    property var navSections: [
        {
            section: "Workspace",
            items: [
                { title: "Dashboard", glyph: "dashboard", index: 0 },
                { title: "Analyze", glyph: "analyze", index: 1 },
                { title: "Results", glyph: "results", index: 2 },
                { title: "Compare", glyph: "compare", index: 3 },
                { title: "History", glyph: "history", index: 4 }
            ]
        },
        {
            section: "Outreach",
            items: [
                { title: "Templates", glyph: "templates", index: 5 }
            ]
        },
        {
            section: "Sync",
            items: [
                { title: "Website Sync", glyph: "sync", index: 6 }
            ]
        },
        {
            section: "System",
            items: [
                { title: "Inbox", glyph: "inbox", index: 7 },
                { title: "Settings", glyph: "settings", index: 8 }
            ]
        }
    ]

    function pageTitle() {
        if (pageIndex === 0) return "Local Worker"
        if (pageIndex === 1) return "Analyze Candidates"
        if (pageIndex === 2) return "Ranked Results"
        if (pageIndex === 3) return "Compare Candidates"
        if (pageIndex === 4) return "Run History"
        if (pageIndex === 5) return "Email Templates"
        if (pageIndex === 6) return "Website Sync"
        if (pageIndex === 7) return "Inbox & Audit"
        return "Worker Settings"
    }

    function pageSubtitle() {
        if (pageIndex === 0) return "Private CV matching, local files, share-ready exports."
        if (pageIndex === 1) return "Choose folders, define scoring criteria, and run a local batch."
        if (pageIndex === 2) return "Review scores, decisions, matched skills, exports and explanations."
        if (pageIndex === 3) return "Compare 2–4 ranked candidates side by side."
        if (pageIndex === 4) return "Reload previous local runs from the local workspace."
        if (pageIndex === 5) return "Edit local accept/reject message templates and preview variables."
        if (pageIndex === 6) return "Connect worker key, test Website access, and sync approved local results."
        if (pageIndex === 7) return "Owner notifications and the local decision audit trail."
        return "Tune local behavior, sync permissions, and desktop preferences."
    }

    component TopIconButton: Button {
        id: control

        property string glyph: ""

        width: Math.max(40, contentItem.implicitWidth + 18)
        height: 40
        hoverEnabled: true
        text: ""

        contentItem: Text {
            text: control.glyph
            color: control.hovered ? Theme.textPrimary : Theme.textSecondary
            font.pixelSize: control.glyph.length > 2 ? 11 : 15
            font.weight: Font.DemiBold
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }

        background: Rectangle {
            radius: 12
            color: control.hovered ? Theme.surfaceMuted : Theme.surfaceElevated
            border.width: 1
            border.color: control.hovered ? Theme.primary : Theme.border
            Behavior on color { ColorAnimation { duration: Theme.durHover } }
            Behavior on border.color { ColorAnimation { duration: Theme.durHover } }
        }
    }

    FolderDialog {
        id: cvFolderDialog
        title: "Select CV folder"
        onAccepted: backend.setCvFolderFromUrl(selectedFolder)
    }

    FolderDialog {
        id: outputFolderDialog
        title: "Select output folder"
        onAccepted: backend.setOutputFolderFromUrl(selectedFolder)
    }

    Connections {
        target: backend
        function onToast(message, type) {
            toastMessage.text = message
            toastBox.toastType = type
            toastBox.open()
            toastTimer.restart()
        }
    }

    Timer {
        id: toastTimer
        interval: 3600
        onTriggered: toastBox.close()
    }

    Popup {
        id: toastBox
        property string toastType: "info"
        readonly property color accent: toastType === "error" ? Theme.danger
            : toastType === "warning" ? Theme.warning
            : toastType === "success" ? Theme.success
            : Theme.primary
        readonly property string glyph: toastType === "error" ? "✕"
            : toastType === "warning" ? "!"
            : toastType === "success" ? "✓"
            : "i"
        x: root.width - width - 28
        y: root.height - height - 28
        width: Math.min(460, root.width - 56)
        modal: false
        focus: false
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        padding: 0

        background: Rectangle {
            radius: Theme.radiusMd
            color: Theme.surfaceElevated
            border.width: 1
            border.color: Theme.border

            layer.enabled: !Theme.reducedMotion
            layer.effect: MultiEffect {
                shadowEnabled: true
                shadowColor: Theme.shadowColor
                shadowOpacity: Theme.darkMode ? 0.5 : 0.18
                shadowBlur: 0.8
                shadowVerticalOffset: 8
            }
        }

        contentItem: RowLayout {
            spacing: Theme.space3

            Rectangle {
                Layout.preferredWidth: 28
                Layout.preferredHeight: 28
                Layout.alignment: Qt.AlignTop
                radius: 14
                color: Qt.rgba(toastBox.accent.r, toastBox.accent.g, toastBox.accent.b, Theme.darkMode ? 0.22 : 0.14)
                Text {
                    anchors.centerIn: parent
                    text: toastBox.glyph
                    color: toastBox.accent
                    font.pixelSize: 13
                    font.weight: Font.Bold
                }
            }

            Text {
                id: toastMessage
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignVCenter
                color: Theme.textPrimary
                wrapMode: Text.WordWrap
                font.pixelSize: 14
                font.weight: Font.Medium
            }
        }

        // contentItem has no anchors.fill, so Popup.padding/margins is what
        // actually insets it — the previous version set anchors.margins on
        // a RowLayout with no anchor target, which QML silently ignores.
        topPadding: Theme.space4
        bottomPadding: Theme.space4
        leftPadding: Theme.space4
        rightPadding: Theme.space4

        enter: Transition {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 160; easing.type: Easing.OutCubic }
            NumberAnimation { property: "y"; from: root.height; to: root.height - toastBox.height - 28; duration: 220; easing.type: Easing.OutCubic }
        }
        exit: Transition {
            NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 120; easing.type: Easing.InCubic }
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.preferredWidth: root.sidebarCollapsed ? 84 : 246
            Layout.fillHeight: true
            color: Theme.sidebar
            border.width: 0
            Behavior on color { ColorAnimation { duration: 180 } }
            Behavior on Layout.preferredWidth { NumberAnimation { duration: 240; easing.type: Easing.OutCubic } }

            Rectangle {
                anchors.right: parent.right
                width: 1
                height: parent.height
                color: Theme.border
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: root.sidebarCollapsed ? 16 : 18
                spacing: 14

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    Image {
                        Layout.preferredWidth: 46
                        Layout.preferredHeight: 46
                        Layout.alignment: root.sidebarCollapsed ? Qt.AlignHCenter : Qt.AlignLeft
                        source: "../assets/logo.png"
                        fillMode: Image.PreserveAspectFit
                        smooth: true
                        mipmap: true
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 1
                        visible: !root.sidebarCollapsed
                        Text {
                            text: "CV Analyzer"
                            color: Theme.textPrimary
                            font.pixelSize: 17
                            font.weight: Font.Black
                        }
                        Text {
                            text: "Private & Local CV Matching"
                            color: Theme.textSecondary
                            font.pixelSize: 11
                        }
                    }
                }

                Item { Layout.preferredHeight: 12 }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Theme.space4

                    Repeater {
                        model: root.navSections
                        delegate: ColumnLayout {
                            id: sectionCol
                            required property var modelData
                            Layout.fillWidth: true
                            spacing: 4

                            Text {
                                Layout.fillWidth: true
                                Layout.leftMargin: root.sidebarCollapsed ? 0 : 14
                                Layout.bottomMargin: 2
                                visible: !root.sidebarCollapsed
                                text: sectionCol.modelData.section
                                color: Theme.textMuted
                                font.pixelSize: Typography.microSize
                                font.weight: Typography.weightSemiBold
                                font.capitalization: Font.AllUppercase
                                font.letterSpacing: 1
                            }

                            Column {
                                Layout.fillWidth: true
                                spacing: 8
                                Repeater {
                                    model: sectionCol.modelData.items
                                    NavButton {
                                        required property var modelData
                                        width: parent.width
                                        collapsed: root.sidebarCollapsed
                                        text: modelData.title
                                        glyph: modelData.glyph
                                        active: root.pageIndex === modelData.index
                                        activeColor: Theme.primary
                                        activeText: Theme.textPrimary
                                        textColor: Theme.textSecondary
                                        hoverText: Theme.textPrimary
                                        activeBg: Theme.primarySoft
                                        hoverBg: Theme.surfaceMuted
                                        activeIcon: Theme.primary
                                        mutedIcon: Theme.textSecondary
                                        onNavClicked: root.pageIndex = modelData.index
                                    }
                                }
                            }
                        }
                    }
                }

                Item { Layout.fillHeight: true }

                AppCard {
                    id: quickStartCard
                    Layout.fillWidth: true
                    // AppCard's own implicitHeight doesn't reflect a child
                    // ColumnLayout that fills it via anchors.fill (sizing
                    // only flows card->content, not back up) — without this
                    // explicit height the card was rendering badge-height
                    // only, and everything else (title/description/progress
                    // bar/button) was overflowing past that, invisible once
                    // AppCard gained clip:true. Every other multi-line
                    // AppCard in this app already sets this explicitly.
                    Layout.preferredHeight: quickStartCol.implicitHeight + quickStartCard.pad * 2
                    visible: !root.sidebarCollapsed
                    pad: Theme.space4

                    ColumnLayout {
                        id: quickStartCol
                        anchors.fill: parent
                        spacing: Theme.space2

                        AppBadge { text: "QUICK START"; tint: Theme.primary }
                        Text {
                            text: backend.isRunning ? "Analysis running" : "New analysis"
                            color: Theme.textPrimary
                            font.pixelSize: 15
                            font.weight: Font.Bold
                        }
                        Text {
                            Layout.fillWidth: true
                            text: backend.isRunning ? backend.status : "Upload a CV folder and start local matching."
                            color: Theme.textSecondary
                            font.pixelSize: 12
                            wrapMode: Text.WordWrap
                        }
                        ProgressBar {
                            Layout.fillWidth: true
                            from: 0
                            to: backend.progressMaximum
                            value: backend.progressValue
                            visible: backend.isRunning || backend.progressValue > 0
                        }
                        AppButton {
                            Layout.fillWidth: true
                            text: backend.isRunning ? "View results" : "Start now"
                            strong: true
                            fill: Theme.primary; fillHover: Theme.primaryHover
                            fillPressed: Qt.darker(Theme.primary, 1.15); stroke: Theme.primary
                            textColor: "#ffffff"
                            onClicked: root.pageIndex = backend.isRunning ? 2 : 1
                        }
                    }
                }

                // Developer contact — opens the OS default browser/mail app.
                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: Theme.space2
                    visible: !root.sidebarCollapsed
                    spacing: Theme.space3
                    Item { Layout.fillWidth: true }
                    Text {
                        text: "LinkedIn"
                        color: Theme.textMuted
                        font.pixelSize: 11
                        font.underline: linkedinArea.containsMouse
                        MouseArea {
                            id: linkedinArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: Qt.openUrlExternally("https://linkedin.com/in/sercan-özkan-a205852a7/")
                        }
                    }
                    Text { text: "·"; color: Theme.textMuted; font.pixelSize: 11 }
                    Text {
                        text: "Email"
                        color: Theme.textMuted
                        font.pixelSize: 11
                        font.underline: emailArea.containsMouse
                        MouseArea {
                            id: emailArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: Qt.openUrlExternally("mailto:ozkansercan55@gmail.com")
                        }
                    }
                    Item { Layout.fillWidth: true }
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 78
                color: Theme.sidebar
                border.width: 0
                Behavior on color { ColorAnimation { duration: 180 } }

                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: 1
                    color: Theme.border
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 22
                    anchors.rightMargin: 22
                    spacing: 14

                    // Sidebar collapse toggle (hamburger). Pages fill more of the
                    // screen when the rail is collapsed.
                    Rectangle {
                        id: navToggle
                        Layout.preferredWidth: 40
                        Layout.preferredHeight: 40
                        Layout.alignment: Qt.AlignVCenter
                        radius: 12
                        color: toggleArea.containsMouse ? Theme.surfaceMuted : "transparent"
                        border.width: 1
                        border.color: toggleArea.containsMouse ? Theme.border : "transparent"
                        Behavior on color { ColorAnimation { duration: 140 } }
                        Behavior on border.color { ColorAnimation { duration: 140 } }

                        Column {
                            anchors.centerIn: parent
                            spacing: 4
                            Repeater {
                                model: 3
                                Rectangle {
                                    width: 18; height: 2; radius: 1
                                    color: toggleArea.containsMouse ? Theme.textPrimary : Theme.textSecondary
                                    Behavior on color { ColorAnimation { duration: 140 } }
                                }
                            }
                        }
                        MouseArea {
                            id: toggleArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.sidebarCollapsed = !root.sidebarCollapsed
                        }
                    }

                    ColumnLayout {
                        Layout.preferredWidth: 360
                        spacing: 2
                        Text {
                            text: root.pageTitle()
                            color: Theme.textPrimary
                            font.pixelSize: 25
                            font.weight: Font.Black
                            elide: Text.ElideRight
                        }
                        Text {
                            text: root.pageSubtitle()
                            color: Theme.textSecondary
                            font.pixelSize: 13
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }

                    Item {
                        Layout.fillWidth: true
                    }

                    AppBadge {
                        text: backend.isRunning ? "Active Batch" : "Offline Ready"
                        tint: backend.isRunning ? Theme.warning : Theme.success
                    }

                    AppBadge {
                        text: backend.syncPendingCount > 0 ? backend.syncPendingCount + " Sync Required" : "Sync Clear"
                        tint: backend.syncPendingCount > 0 ? Theme.warning : Theme.primary
                    }

                    TopIconButton {
                        glyph: Theme.darkMode ? "Sun" : "Moon"
                        onClicked: Theme.toggle()
                    }

                    Rectangle {
                        Layout.preferredWidth: 40
                        Layout.preferredHeight: 40
                        radius: 20
                        color: Theme.surfaceElevated
                        border.width: 1
                        border.color: Theme.border

                        Text {
                            anchors.centerIn: parent
                            text: "S"
                            color: Theme.textPrimary
                            font.pixelSize: 15
                            font.weight: Font.Black
                        }
                    }
                }
            }

            StackLayout {
                id: pageStack
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: root.pageIndex

                // Animated page transition (fade + slide-up). opacity/transform
                // do not affect layout geometry, so this is safe over the
                // existing pages. Driven by root.pageAnimKey (bumped on change).
                opacity: 1
                transform: Translate { id: pageTranslate }

                Connections {
                    target: root
                    function onPageAnimKeyChanged() {
                        if (typeof backend !== "undefined" && !backend.motionEnabled) {
                            pageStack.opacity = 1
                            pageTranslate.y = 0
                            return
                        }
                        pageTransition.restart()
                    }
                }

                SequentialAnimation {
                    id: pageTransition
                    PropertyAction { target: pageStack; property: "opacity"; value: 0.0 }
                    PropertyAction { target: pageTranslate; property: "y"; value: 16 }
                    ParallelAnimation {
                        NumberAnimation { target: pageStack; property: "opacity"; to: 1.0; duration: 280; easing.type: Easing.OutCubic }
                        NumberAnimation { target: pageTranslate; property: "y"; to: 0; duration: 360; easing.type: Easing.OutBack; easing.overshoot: 0.6 }
                    }
                }

                DashboardPage {
                    onRequestPage: (index) => { root.pageIndex = index }
                    onRequestBrowse: cvFolderDialog.open()
                }

                AnalyzePage {
                    onRequestBrowseCv: cvFolderDialog.open()
                    onRequestBrowseOutput: outputFolderDialog.open()
                }

                ResultsPage {}

                CompareCandidatesPage {
                    onRequestPage: (index) => { root.pageIndex = index }
                }

                HistoryPage {
                    onRequestPage: (index) => { root.pageIndex = index }
                }

                TemplatesPage {}

                WebsiteSyncPage {
                    onRequestPage: (index) => { root.pageIndex = index }
                }

                InboxPage {}

                SettingsPage {
                    onRequestTheme: (mode) => { Theme.mode = mode }
                    onRequestMotion: (enabled) => { backend.motionEnabled = enabled }
                    onRequestPage: (index) => { root.pageIndex = index }
                }
            }
        }
    }
}
