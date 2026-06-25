import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts
import QtCore
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
    color: themeBg

    property bool darkTheme: true
    property int pageAnimKey: 0
    property int contentMaxWidth: 1500
    property int contentMargin: 28
    // Collapsible sidebar: collapses to an icon-only rail so pages fill the screen.
    property bool sidebarCollapsed: false
    property bool compact: width < 1100
    property bool wide: width > 1550
    property color themeBg: darkTheme ? "#0b1020" : "#f5f7fb"
    property color themeSurface: darkTheme ? "#12182b" : "#ffffff"
    property color themeSurface2: darkTheme ? "#182038" : "#eef2f8"
    property color themeElevated: darkTheme ? "#151d33" : "#ffffff"
    property color themeBorder: darkTheme ? "#27314a" : "#d9e1ef"
    property color themePrimary: darkTheme ? "#7c5cff" : "#6d5df6"
    property color themeSecondary: darkTheme ? "#35a7ff" : "#2f80ed"
    property color themeSuccess: darkTheme ? "#22c55e" : "#16a34a"
    property color themeWarning: darkTheme ? "#f59e0b" : "#d97706"
    property color themeDanger: darkTheme ? "#ef4444" : "#dc2626"
    property color themeText: darkTheme ? "#f5f7ff" : "#0f172a"
    property color themeText2: darkTheme ? "#a6b0cf" : "#5b647a"
    property color themeMuted: darkTheme ? "#66708f" : "#8792a8"
    property color themeInput: darkTheme ? "#0b1020" : "#f8fafc"
    property color themeSidebar: darkTheme ? "#070b16" : "#ffffff"
    property color themeCard: darkTheme ? "#101624" : "#ffffff"
    property color themeCardAlt: darkTheme ? "#151b2e" : "#f8fafc"

    Behavior on color { ColorAnimation { duration: 180 } }

    function contentWidth(availableWidth) {
        return Math.max(0, Math.min(availableWidth - contentMargin * 2, contentMaxWidth))
    }

    function contentX(availableWidth) {
        return Math.max(contentMargin, (availableWidth - contentWidth(availableWidth)) / 2)
    }

    function metricSurfaceProps() {
        return {
            "surface": themeCard,
            "stroke": themeBorder,
            "primaryText": themeText,
            "mutedText": themeText2,
            "subtleText": themeMuted
        }
    }

    // Keep the new Theme singleton (used by the modular pages) in sync with the
    // shell's legacy darkTheme toggle + reduced-motion flag, so every screen
    // re-themes together.
    function _syncTheme() {
        Theme.mode = darkTheme ? "dark" : "light"
        Theme.reducedMotion = (typeof backend !== "undefined") ? !backend.motionEnabled : false
    }

    onDarkThemeChanged: { uiSettings.darkTheme = darkTheme; _syncTheme() }
    onPageIndexChanged: pageAnimKey += 1

    Settings {
        id: uiSettings
        category: "ui"
        property bool darkTheme: true
    }

    Component.onCompleted: {
        darkTheme = uiSettings.darkTheme
        _syncTheme()
    }

    // Reactive bridge so a reduced-motion change anywhere stops animations on
    // every page immediately.
    Binding {
        target: Theme
        property: "reducedMotion"
        value: (typeof backend !== "undefined") ? !backend.motionEnabled : false
    }

    property int pageIndex: 0
    property var navItems: [
        { title: "Dashboard", glyph: "dashboard" },
        { title: "Analyze", glyph: "analyze" },
        { title: "Results", glyph: "results" },
        { title: "History", glyph: "history" },
        { title: "Website Sync", glyph: "sync" },
        { title: "Reports", glyph: "reports" },
        { title: "Templates", glyph: "templates" },
        { title: "Settings", glyph: "settings" },
        { title: "Inbox", glyph: "inbox" }
    ]

    function pageTitle() {
        if (pageIndex === 0) return "Local Worker"
        if (pageIndex === 1) return "Analyze Candidates"
        if (pageIndex === 2) return "Ranked Results"
        if (pageIndex === 3) return "Run History"
        if (pageIndex === 4) return "Website Sync"
        if (pageIndex === 5) return "Local Reports"
        if (pageIndex === 6) return "Email Templates"
        if (pageIndex === 8) return "Inbox & Audit"
        return "Worker Settings"
    }

    function pageSubtitle() {
        if (pageIndex === 0) return "Private CV matching, local files, share-ready exports."
        if (pageIndex === 1) return "Choose folders, define scoring criteria, and run a local batch."
        if (pageIndex === 2) return "Review scores, decisions, matched skills, and explanations."
        if (pageIndex === 3) return "Reload previous local runs from the local workspace."
        if (pageIndex === 4) return "Connect worker key, test Website access, and sync approved local results."
        if (pageIndex === 5) return "Preview current run output and export local files."
        if (pageIndex === 6) return "Edit local accept/reject message templates and preview variables."
        if (pageIndex === 8) return "Owner notifications and the local decision audit trail."
        return "Tune local behavior, sync permissions, and desktop preferences."
    }

    component Pill: Rectangle {
        property string text: ""
        property color tint: "#6366f1"
        height: 30
        radius: 15
        color: Qt.rgba(tint.r, tint.g, tint.b, root.darkTheme ? 0.12 : 0.1)
        border.width: 1
        border.color: Qt.rgba(tint.r, tint.g, tint.b, 0.32)
        implicitWidth: label.implicitWidth + 24

        Text {
            id: label
            anchors.centerIn: parent
            text: parent.text
            color: root.darkTheme ? "#dce8ff" : root.themeText
            font.pixelSize: 12
            font.weight: Font.DemiBold
        }
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
            color: control.hovered ? root.themeText : root.themeText2
            font.pixelSize: control.glyph.length > 2 ? 11 : 15
            font.weight: Font.DemiBold
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }

        background: Rectangle {
            radius: 12
            color: control.hovered ? root.themeSurface2 : root.themeInput
            border.width: 1
            border.color: control.hovered ? root.themePrimary : root.themeBorder
            Behavior on color { ColorAnimation { duration: 140 } }
            Behavior on border.color { ColorAnimation { duration: 140 } }
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
        x: root.width - width - 28
        y: root.height - height - 28
        width: Math.min(460, root.width - 56)
        modal: false
        focus: false
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        padding: 0
        background: Rectangle {
            id: toastBg
            radius: 18
            color: root.darkTheme ? Qt.rgba(18/255, 24/255, 43/255, 0.88) : Qt.rgba(255/255, 255/255, 255/255, 0.93)
            border.width: 1
            border.color: toastBox.toastType === "error" ? "#ef4444" : toastBox.toastType === "warning" ? "#f59e0b" : "#6366f1"
            Rectangle {
                anchors.fill: parent
                radius: parent.radius
                color: "transparent"
                border.width: 1
                border.color: root.darkTheme ? Qt.rgba(255, 255, 255, 0.08) : Qt.rgba(255, 255, 255, 0.3)
            }
        }
        contentItem: RowLayout {
            spacing: 12
            anchors.margins: 16

            Rectangle {
                Layout.preferredWidth: 10
                Layout.fillHeight: true
                radius: 5
                color: toastBox.background.border.color
            }

            Text {
                id: toastMessage
                Layout.fillWidth: true
                color: root.themeText
                wrapMode: Text.WordWrap
                font.pixelSize: 14
                font.weight: Font.Medium
            }
        }

        enter: Transition {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 160; easing.type: Easing.OutCubic }
            NumberAnimation { property: "y"; from: root.height; to: root.height - toastBox.height - 28; duration: 220; easing.type: Easing.OutCubic }
        }
        exit: Transition {
            NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 120; easing.type: Easing.InCubic }
        }
    }

    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0; color: root.darkTheme ? "#10172a" : "#ffffff" }
            GradientStop { position: 0.55; color: root.themeBg }
            GradientStop { position: 1; color: root.darkTheme ? "#070b16" : "#eef2f8" }
        }
        Behavior on color { ColorAnimation { duration: 180 } }
    }

    Rectangle {
        x: root.width * 0.2
        y: -180
        width: 560
        height: 440
        radius: 220
        opacity: root.darkTheme ? 0.09 : 0.05
        gradient: Gradient {
            GradientStop { position: 0; color: root.themePrimary }
            GradientStop { position: 1; color: "transparent" }
        }
        SequentialAnimation on opacity {
            running: backend.motionEnabled
            loops: Animation.Infinite
            NumberAnimation { from: root.darkTheme ? 0.06 : 0.03; to: root.darkTheme ? 0.11 : 0.06; duration: 2600; easing.type: Easing.InOutSine }
            NumberAnimation { from: root.darkTheme ? 0.11 : 0.06; to: root.darkTheme ? 0.06 : 0.03; duration: 3000; easing.type: Easing.InOutSine }
        }
    }

    Rectangle {
        x: root.width * 0.62
        y: root.height * 0.18
        width: 520
        height: 520
        radius: 260
        opacity: root.darkTheme ? 0.07 : 0.035
        gradient: Gradient {
            GradientStop { position: 0; color: root.themeSecondary }
            GradientStop { position: 1; color: "transparent" }
        }
        SequentialAnimation on opacity {
            running: backend.motionEnabled
            loops: Animation.Infinite
            NumberAnimation { from: root.darkTheme ? 0.04 : 0.02; to: root.darkTheme ? 0.09 : 0.045; duration: 3200; easing.type: Easing.InOutSine }
            NumberAnimation { from: root.darkTheme ? 0.09 : 0.045; to: root.darkTheme ? 0.04 : 0.02; duration: 2800; easing.type: Easing.InOutSine }
        }
    }

    Canvas {
        anchors.fill: parent
        opacity: root.darkTheme ? 0.06 : 0.045
        onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            ctx.strokeStyle = root.darkTheme ? "#5d7299" : "#9ba8c2"
            ctx.lineWidth = 1
            for (var x = 0; x < width; x += 48) {
                ctx.beginPath()
                ctx.moveTo(x, 0)
                ctx.lineTo(x, height)
                ctx.stroke()
            }
            for (var y = 0; y < height; y += 48) {
                ctx.beginPath()
                ctx.moveTo(0, y)
                ctx.lineTo(width, y)
                ctx.stroke()
            }
        }
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
    }

    Rectangle {
        x: root.width * 0.42
        y: -120
        width: 560
        height: root.height + 260
        rotation: 18
        opacity: root.darkTheme ? 0.055 : 0.03
        gradient: Gradient {
            GradientStop { position: 0; color: root.themePrimary }
            GradientStop { position: 0.5; color: root.themeSecondary }
            GradientStop { position: 1; color: "transparent" }
        }
        NumberAnimation on rotation {
            running: backend.motionEnabled
            loops: Animation.Infinite
            from: 16
            to: 22
            duration: 9000
            easing.type: Easing.InOutSine
        }
    }

    Repeater {
        model: [
            { px: 0.18, py: 0.18, s: 4, c: "#7c5cff", d: 5200 },
            { px: 0.33, py: 0.72, s: 3, c: "#28e0e6", d: 6400 },
            { px: 0.58, py: 0.24, s: 5, c: "#2ee59d", d: 7000 },
            { px: 0.74, py: 0.66, s: 3, c: "#ffb84d", d: 5800 },
            { px: 0.86, py: 0.34, s: 4, c: "#9a6cff", d: 7600 },
            { px: 0.46, py: 0.48, s: 2, c: "#35a7ff", d: 6200 }
        ]

        Rectangle {
            x: root.width * modelData.px
            y: root.height * modelData.py
            width: modelData.s
            height: modelData.s
            radius: modelData.s / 2
            color: modelData.c
            opacity: root.darkTheme ? 0.18 : 0.1
            border.width: 1
            border.color: modelData.c

            Rectangle {
                anchors.centerIn: parent
                width: parent.width + 22
                height: width
                radius: width / 2
                color: "transparent"
                border.width: 1
                border.color: parent.color
                opacity: 0.12
            }

            SequentialAnimation on y {
                running: backend.motionEnabled
                loops: Animation.Infinite
                NumberAnimation { from: root.height * modelData.py; to: root.height * modelData.py - 18; duration: modelData.d; easing.type: Easing.InOutSine }
                NumberAnimation { from: root.height * modelData.py - 18; to: root.height * modelData.py; duration: modelData.d; easing.type: Easing.InOutSine }
            }

            SequentialAnimation on opacity {
                running: backend.motionEnabled
                loops: Animation.Infinite
                NumberAnimation { from: root.darkTheme ? 0.08 : 0.04; to: root.darkTheme ? 0.22 : 0.12; duration: modelData.d / 2; easing.type: Easing.InOutSine }
                NumberAnimation { from: root.darkTheme ? 0.22 : 0.12; to: root.darkTheme ? 0.08 : 0.04; duration: modelData.d / 2; easing.type: Easing.InOutSine }
            }
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.preferredWidth: root.sidebarCollapsed ? 84 : 246
            Layout.fillHeight: true
            color: root.themeSidebar
            border.width: 0
            Behavior on color { ColorAnimation { duration: 180 } }
            Behavior on Layout.preferredWidth { NumberAnimation { duration: 240; easing.type: Easing.OutCubic } }

            Rectangle {
                anchors.right: parent.right
                width: 1
                height: parent.height
                color: root.themeBorder
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: root.sidebarCollapsed ? 16 : 18
                spacing: 14

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    Rectangle {
                        Layout.preferredWidth: 46
                        Layout.preferredHeight: 46
                        Layout.alignment: root.sidebarCollapsed ? Qt.AlignHCenter : Qt.AlignLeft
                        radius: 16
                        gradient: Gradient {
                            GradientStop { position: 0; color: root.themeSuccess }
                            GradientStop { position: 0.55; color: root.themePrimary }
                            GradientStop { position: 1; color: "#9a6cff" }
                        }
                        border.width: 1
                        border.color: root.themePrimary
                        Text {
                            anchors.centerIn: parent
                            text: "CV"
                            color: root.darkTheme ? "#ffffff" : root.themeText
                            font.pixelSize: 13
                            font.weight: Font.Black
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 1
                        visible: !root.sidebarCollapsed
                        Text {
                            text: "CV Analyzer"
                            color: root.themeText
                            font.pixelSize: 17
                            font.weight: Font.Black
                        }
                        Text {
                            text: "Private & Local CV Matching"
                            color: root.themeText2
                            font.pixelSize: 11
                        }
                    }
                }

                Item { Layout.preferredHeight: 12 }

                Item {
                    id: navContainer
                    Layout.fillWidth: true
                    Layout.preferredHeight: root.navItems.length * 44 + (root.navItems.length - 1) * 8

                    Rectangle {
                        id: activeIndicator
                        x: -18
                        width: 3
                        height: 24
                        radius: 2
                        color: root.themePrimary
                        y: root.pageIndex * (44 + 8) + 10

                        Behavior on y {
                            NumberAnimation {
                                duration: 250
                                easing.type: Easing.OutCubic
                            }
                        }
                    }

                    Column {
                        anchors.fill: parent
                        spacing: 8
                        Repeater {
                            model: root.navItems
                            NavButton {
                                width: navContainer.width
                                collapsed: root.sidebarCollapsed
                                text: modelData.title
                                glyph: modelData.glyph
                                active: root.pageIndex === index
                                activeColor: root.themePrimary
                                activeText: root.darkTheme ? "#ffffff" : root.themeText
                                textColor: root.themeText2
                                hoverText: root.themeText
                                activeBg: root.darkTheme ? "#18152f" : "#eef0ff"
                                hoverBg: root.themeSurface2
                                activeIcon: root.themePrimary
                                mutedIcon: root.themeText2
                                onNavClicked: root.pageIndex = index
                            }
                        }
                    }
                }

                Item { Layout.fillHeight: true }

                GlassCard {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 176
                    visible: !root.sidebarCollapsed
                    cardColor: root.themeCardAlt
                    strokeColor: root.themeBorder
                    glowColor: root.themePrimary

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 8

                        Pill { text: "QUICK START"; tint: "#7c5cff" }
                        Text {
                            text: backend.isRunning ? "Analysis running" : "New analysis"
                            color: root.themeText
                            font.pixelSize: 15
                            font.weight: Font.Bold
                        }
                        Text {
                            Layout.fillWidth: true
                            text: backend.isRunning ? backend.status : "Upload a CV folder and start local matching."
                            color: root.themeText2
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
                            onClicked: root.pageIndex = backend.isRunning ? 2 : 1
                        }
                    }
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
                color: root.themeSidebar
                border.width: 0
                Behavior on color { ColorAnimation { duration: 180 } }

                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: 1
                    color: root.themeBorder
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
                        color: toggleArea.containsMouse ? root.themeSurface2 : "transparent"
                        border.width: 1
                        border.color: toggleArea.containsMouse ? root.themeBorder : "transparent"
                        Behavior on color { ColorAnimation { duration: 140 } }
                        Behavior on border.color { ColorAnimation { duration: 140 } }

                        Column {
                            anchors.centerIn: parent
                            spacing: 4
                            Repeater {
                                model: 3
                                Rectangle {
                                    width: 18; height: 2; radius: 1
                                    color: toggleArea.containsMouse ? root.themeText : root.themeText2
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
                            color: root.themeText
                            font.pixelSize: 25
                            font.weight: Font.Black
                            elide: Text.ElideRight
                        }
                        Text {
                            text: root.pageSubtitle()
                            color: root.themeText2
                            font.pixelSize: 13
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }

                    Item {
                        Layout.fillWidth: true
                    }

                    Pill {
                        text: backend.isRunning ? "Active Batch" : "Offline Ready"
                        tint: backend.isRunning ? root.themeWarning : root.themeSuccess
                    }

                    Pill {
                        text: backend.syncPendingCount > 0 ? backend.syncPendingCount + " Sync Required" : "Sync Clear"
                        tint: backend.syncPendingCount > 0 ? root.themeWarning : root.themePrimary
                    }

                    TopIconButton {
                        glyph: root.darkTheme ? "Sun" : "Moon"
                        onClicked: root.darkTheme = !root.darkTheme
                    }

                    Rectangle {
                        Layout.preferredWidth: 40
                        Layout.preferredHeight: 40
                        radius: 20
                        color: root.themeInput
                        border.width: 1
                        border.color: root.themeBorder

                        Text {
                            anchors.centerIn: parent
                            text: "S"
                            color: root.themeText
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

                HistoryPage {
                    onRequestPage: (index) => { root.pageIndex = index }
                }

                WebsiteSyncPage {
                    onRequestPage: (index) => { root.pageIndex = index }
                }

                ReportsPage {
                    onRequestPage: (index) => { root.pageIndex = index }
                }

                TemplatesPage {}

                SettingsPage {
                    onRequestTheme: (mode) => { root.darkTheme = (mode === "dark") }
                    onRequestMotion: (enabled) => { backend.motionEnabled = enabled }
                    onRequestPage: (index) => { root.pageIndex = index }
                }

                InboxPage {}
            }
        }
    }
}
