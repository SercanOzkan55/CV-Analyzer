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

    component FieldLabel: Text {
        color: root.themeText2
        font.pixelSize: 12
        font.weight: Font.DemiBold
    }

    component ProTextField: TextField {
        height: 46
        color: root.themeText
        placeholderTextColor: root.themeMuted
        selectedTextColor: root.darkTheme ? "#08111f" : "#ffffff"
        selectionColor: root.themePrimary
        font.pixelSize: 14
        leftPadding: 16
        rightPadding: 16
        background: Rectangle {
            radius: 14
            color: parent.activeFocus ? root.themeSurface : root.themeInput
            border.width: 1
            border.color: parent.activeFocus ? root.themePrimary : root.themeBorder
            Behavior on border.color { ColorAnimation { duration: 140 } }
            Behavior on color { ColorAnimation { duration: 140 } }
        }
    }

    component PathBox: Rectangle {
        property string path: ""
        property string placeholder: ""
        height: 46
        radius: 14
        color: root.themeInput
        border.width: 1
        border.color: root.themeBorder

        Text {
            anchors.fill: parent
            anchors.leftMargin: 16
            anchors.rightMargin: 16
            text: parent.path || parent.placeholder
            color: parent.path ? root.themeText : root.themeMuted
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideMiddle
            font.pixelSize: 14
        }
    }

    component ProTextArea: TextArea {
        color: root.themeText
        placeholderTextColor: root.themeMuted
        selectedTextColor: root.darkTheme ? "#08111f" : "#ffffff"
        selectionColor: root.themePrimary
        font.pixelSize: 14
        wrapMode: TextEdit.Wrap
        leftPadding: 16
        rightPadding: 16
        topPadding: 14
        bottomPadding: 14
        background: Rectangle {
            radius: 16
            color: parent.activeFocus ? root.themeSurface : root.themeInput
            border.width: 1
            border.color: parent.activeFocus ? root.themePrimary : root.themeBorder
            Behavior on border.color { ColorAnimation { duration: 140 } }
            Behavior on color { ColorAnimation { duration: 140 } }
        }
    }

    component ProSlider: Slider {
        id: control
        height: 34
        background: Rectangle {
            x: control.leftPadding
            y: control.topPadding + control.availableHeight / 2 - height / 2
            width: control.availableWidth
            height: 7
            radius: 4
            color: root.darkTheme ? "#243148" : "#dbe4f0"
            Rectangle {
                width: control.visualPosition * parent.width
                height: parent.height
                radius: parent.radius
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: root.themePrimary }
                    GradientStop { position: 1; color: root.themeSecondary }
                }
            }
        }
        handle: Rectangle {
            x: control.leftPadding + control.visualPosition * (control.availableWidth - width)
            y: control.topPadding + control.availableHeight / 2 - height / 2
            width: 24
            height: 24
            radius: 12
            color: root.themeSurface
            border.width: 2
            border.color: control.pressed ? root.themeSecondary : root.themePrimary
            Behavior on border.color { ColorAnimation { duration: 120 } }
        }
    }

    component ProComboBox: ComboBox {
        id: control
        height: 46
        font.pixelSize: 14

        contentItem: Text {
            leftPadding: 16
            rightPadding: 42
            text: control.displayText
            color: root.themeText
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            font.pixelSize: 14
        }

        indicator: Text {
            x: control.width - width - 16
            y: control.topPadding + (control.availableHeight - height) / 2
            text: "v"
            color: root.themeText2
            font.pixelSize: 13
            font.weight: Font.Bold
        }

        background: Rectangle {
            radius: 14
            color: control.activeFocus ? root.themeSurface : root.themeInput
            border.width: 1
            border.color: control.activeFocus ? root.themePrimary : root.themeBorder
        }

        delegate: ItemDelegate {
            width: control.width
            height: 42
            text: modelData
            highlighted: control.highlightedIndex === index
            contentItem: Text {
                text: modelData
                color: highlighted ? "#ffffff" : root.themeText2
                font.pixelSize: 14
                verticalAlignment: Text.AlignVCenter
            }
            background: Rectangle {
                color: highlighted ? root.themePrimary : root.themeSurface
            }
        }

        popup: Popup {
            y: control.height + 6
            width: control.width
            implicitHeight: contentItem.implicitHeight
            padding: 1
            background: Rectangle {
                radius: 14
                color: root.themeSurface
                border.width: 1
                border.color: root.themeBorder
            }
            contentItem: ListView {
                clip: true
                implicitHeight: contentHeight
                model: control.popup.visible ? control.delegateModel : null
                currentIndex: control.highlightedIndex
            }
        }
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

    component ScoreRing: Item {
        id: scoreRing

        property real value: 87
        property real animatedValue: value
        property color ringColor: "#2ee59d"
        property color trackColor: root.themeBorder

        width: 144
        height: 144

        Canvas {
            id: ringCanvas
            anchors.fill: parent
            antialiasing: true

            onPaint: {
                var ctx = getContext("2d")
                var stroke = Math.max(5, Math.min(width, height) * 0.083)
                var cx = width / 2
                var cy = height / 2
                var radius = Math.min(width, height) / 2 - stroke / 2 - 3
                var start = -Math.PI / 2
                var end = start + (Math.PI * 2 * Math.max(0, Math.min(100, scoreRing.animatedValue)) / 100)

                ctx.clearRect(0, 0, width, height)
                ctx.lineWidth = stroke
                ctx.lineCap = "round"

                ctx.beginPath()
                ctx.strokeStyle = scoreRing.trackColor
                ctx.arc(cx, cy, radius, 0, Math.PI * 2, false)
                ctx.stroke()

                ctx.beginPath()
                ctx.strokeStyle = scoreRing.ringColor
                ctx.arc(cx, cy, radius, start, end, false)
                ctx.stroke()
            }
        }

        Rectangle {
            anchors.centerIn: parent
            width: parent.width * 0.62
            height: width
            radius: width / 2
            color: root.darkTheme ? "#111827" : "#ffffff"
            border.width: 1
            border.color: root.themeBorder
        }

        Row {
            anchors.centerIn: parent
            spacing: 1

            Text {
                text: Math.round(scoreRing.animatedValue)
                color: root.themeText
                font.pixelSize: Math.max(16, scoreRing.width * 0.235)
                font.weight: Font.Black
                verticalAlignment: Text.AlignVCenter
            }

            Text {
                y: Math.max(3, scoreRing.width * 0.062)
                text: "%"
                color: root.themeText2
                font.pixelSize: Math.max(8, scoreRing.width * 0.105)
                font.weight: Font.Black
            }
        }

        Behavior on animatedValue { NumberAnimation { duration: 650; easing.type: Easing.OutCubic } }
        onValueChanged: animatedValue = value
        onAnimatedValueChanged: ringCanvas.requestPaint()
        Component.onCompleted: {
            animatedValue = value
            ringCanvas.requestPaint()
        }
    }

    component ActivityItem: RowLayout {
        property string title: ""
        property string detail: ""
        property string time: ""
        property color accent: "#2ee59d"

        spacing: 10

        Rectangle {
            Layout.preferredWidth: 9
            Layout.preferredHeight: 9
            Layout.alignment: Qt.AlignTop
            Layout.topMargin: 6
            radius: 5
            color: accent
            layer.enabled: true
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2

            Text {
                Layout.fillWidth: true
                text: title
                color: root.themeText
                font.pixelSize: 12
                font.weight: Font.Bold
                elide: Text.ElideRight
            }

            Text {
                Layout.fillWidth: true
                text: detail
                color: root.themeText2
                font.pixelSize: 11
                elide: Text.ElideRight
            }
        }

        Text {
            text: time
            color: root.themeMuted
            font.pixelSize: 10
        }
    }

    component ScoreBar: RowLayout {
        property string label: ""
        property int value: 80
        property color accent: "#35a7ff"

        spacing: 10

        Text {
            Layout.preferredWidth: 96
            text: label
            color: root.themeText2
            font.pixelSize: 11
            elide: Text.ElideRight
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 7
            radius: 4
            color: root.themeBorder

            Rectangle {
                width: parent.width * Math.max(0, Math.min(100, value)) / 100
                height: parent.height
                radius: parent.radius
                color: accent
            }
        }

        Text {
            Layout.preferredWidth: 34
            text: value + "%"
            color: accent
            font.pixelSize: 11
            font.weight: Font.Bold
            horizontalAlignment: Text.AlignRight
        }
    }

    component DistributionBar: ColumnLayout {
        property string label: ""
        property int count: 0
        property int total: Math.max(1, backend.totalCandidates)
        property color accent: "#35a7ff"

        spacing: 6

        RowLayout {
            Layout.fillWidth: true
            Text {
                Layout.fillWidth: true
                text: label
                color: root.themeText2
                font.pixelSize: 12
                font.weight: Font.DemiBold
            }
            Text {
                text: count
                color: accent
                font.pixelSize: 12
                font.weight: Font.Black
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 9
            radius: 5
            color: root.themeBorder

            Rectangle {
                width: parent.width * Math.max(0, Math.min(1, count / Math.max(1, total)))
                height: parent.height
                radius: parent.radius
                color: accent
                Behavior on width { NumberAnimation { duration: 260; easing.type: Easing.OutCubic } }
            }
        }
    }

    component SetupStep: RowLayout {
        property string title: ""
        property string detail: ""
        property bool complete: false
        property bool active: false
        property int number: 1

        spacing: 10

        Rectangle {
            Layout.preferredWidth: 34
            Layout.preferredHeight: 34
            radius: 12
            color: complete ? "#123326" : (active ? "#18152f" : "#0b1020")
            border.width: 1
            border.color: complete ? "#2ee59d" : (active ? "#7c5cff" : "#26314d")
            Text {
                anchors.centerIn: parent
                text: complete ? "OK" : number
                color: complete ? "#b8f7dd" : "#c8d1ee"
                font.pixelSize: 13
                font.weight: Font.Black
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 1
            Text {
                Layout.fillWidth: true
                text: title
                color: active || complete ? "#f4f7ff" : "#9aa8c7"
                font.pixelSize: 13
                font.weight: Font.Bold
                elide: Text.ElideRight
            }
            Text {
                Layout.fillWidth: true
                text: detail
                color: root.themeMuted
                font.pixelSize: 11
                elide: Text.ElideRight
            }
        }
    }

    component PipelineStep: ColumnLayout {
        property string title: ""
        property string detail: ""
        property int number: 1
        property bool complete: false
        property bool active: false

        spacing: 8

        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 42
            Layout.preferredHeight: 42
            radius: 14
            color: complete ? "#123326" : (active ? "#18152f" : "#0b1020")
            border.width: 1
            border.color: complete ? "#2ee59d" : (active ? "#7c5cff" : "#26314d")
            scale: active ? 1.04 : 1
            Behavior on scale { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

            Text {
                anchors.centerIn: parent
                text: complete ? "OK" : number
                color: complete ? "#b8f7dd" : (active ? "#ffffff" : "#8e9abf")
                font.pixelSize: 15
                font.weight: Font.Black
            }
        }

        Text {
            Layout.fillWidth: true
            text: title
            color: complete || active ? "#f4f7ff" : "#8e9abf"
            font.pixelSize: 12
            font.weight: Font.Bold
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
        }

        Text {
            Layout.fillWidth: true
            text: detail
            color: root.themeMuted
            font.pixelSize: 10
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
        }
    }

    component EmptyState: Rectangle {
        property string title: ""
        property string detail: ""
        property string actionText: ""
        property int targetPage: 1

        radius: 18
        color: root.themeInput
        border.width: 1
        border.color: root.themeBorder

        ColumnLayout {
            anchors.centerIn: parent
            width: Math.min(parent.width - 40, 380)
            spacing: 12

            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: 58
                Layout.preferredHeight: 58
                radius: 20
                color: root.darkTheme ? "#18152f" : "#eef0ff"
                border.width: 1
                border.color: root.themePrimary
                Text {
                    anchors.centerIn: parent
                    text: "CV"
                    color: root.darkTheme ? "#ffffff" : root.themeText
                    font.pixelSize: 14
                    font.weight: Font.Black
                }
            }

            Text {
                Layout.fillWidth: true
                text: title
                color: root.themeText
                font.pixelSize: 16
                font.weight: Font.Black
                horizontalAlignment: Text.AlignHCenter
            }

            Text {
                Layout.fillWidth: true
                text: detail
                color: root.themeText2
                font.pixelSize: 12
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignHCenter
            }

            AppButton {
                Layout.alignment: Qt.AlignHCenter
                visible: actionText.length > 0
                text: actionText
                strong: true
                onClicked: root.pageIndex = targetPage
            }
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
            Layout.preferredWidth: 246
            Layout.fillHeight: true
            color: root.themeSidebar
            border.width: 0
            Behavior on color { ColorAnimation { duration: 180 } }

            Rectangle {
                anchors.right: parent.right
                width: 1
                height: parent.height
                color: root.themeBorder
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: 14

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    Rectangle {
                        Layout.preferredWidth: 46
                        Layout.preferredHeight: 46
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

                ScrollView {
                    id: templatesScroll
                    clip: true

                    RowLayout {
                        x: root.contentX(templatesScroll.availableWidth)
                        y: 28
                        width: root.contentWidth(templatesScroll.availableWidth)
                        height: templatesScroll.availableHeight - 56
                        spacing: 20

                        GlassCard {
                            Layout.preferredWidth: 250
                            Layout.fillHeight: true

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 22
                                spacing: 12

                                Text {
                                    text: "Actions"
                                    color: root.darkTheme ? "#ffffff" : root.themeText
                                    font.pixelSize: 22
                                    font.weight: Font.Black
                                }

                                AppButton {
                                    Layout.fillWidth: true
                                    text: "Accept template"
                                    fill: backend.templateMode === "accept" ? "#1f1a3d" : "#18181b"
                                    stroke: backend.templateMode === "accept" ? "#6366f1" : "#29344b"
                                    onClicked: backend.setTemplateMode("accept")
                                }
                                AppButton {
                                    Layout.fillWidth: true
                                    text: "Reject template"
                                    fill: backend.templateMode === "reject" ? "#3b1824" : "#18181b"
                                    stroke: backend.templateMode === "reject" ? "#ef4444" : "#29344b"
                                    onClicked: backend.setTemplateMode("reject")
                                }

                                Item { Layout.fillHeight: true }

                                Text {
                                    Layout.fillWidth: true
                                    text: "Templates are saved locally in the OS app data folder."
                                    color: root.themeMuted
                                    wrapMode: Text.WordWrap
                                    font.pixelSize: 12
                                }
                            }
                        }

                        GlassCard {
                            Layout.fillWidth: true
                            Layout.fillHeight: true

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 22
                                spacing: 14

                                Text {
                                    text: "Template editor"
                                    color: root.darkTheme ? "#ffffff" : root.themeText
                                    font.pixelSize: 22
                                    font.weight: Font.Black
                                }

                                FieldLabel { text: "SUBJECT" }
                                ProTextField {
                                    Layout.fillWidth: true
                                    text: backend.templateSubject
                                    onTextChanged: if (backend.templateSubject !== text) backend.templateSubject = text
                                }

                                FieldLabel { text: "MESSAGE BODY" }
                                ProTextArea {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    text: backend.templateBody
                                    onTextChanged: if (backend.templateBody !== text) backend.templateBody = text
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8
                                    FieldLabel { text: "INSERT" }
                                    Repeater {
                                        model: ["{name}", "{email}", "{role}", "{score}"]
                                        AppButton {
                                            text: modelData
                                            implicitWidth: 92
                                            onClicked: backend.insertTemplateVariable(modelData)
                                        }
                                    }
                                    Item { Layout.fillWidth: true }
                                    AppButton {
                                        text: "Save"
                                        strong: true
                                        onClicked: backend.saveTemplates()
                                    }
                                }
                            }
                        }

                        GlassCard {
                            Layout.preferredWidth: 380
                            Layout.fillHeight: true

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 22
                                spacing: 14

                                Text {
                                    text: "Live preview"
                                    color: root.darkTheme ? "#ffffff" : root.themeText
                                    font.pixelSize: 22
                                    font.weight: Font.Black
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    radius: 20
                                    color: root.themeInput
                                    border.width: 1
                                    border.color: root.themeBorder

                                    ColumnLayout {
                                        anchors.fill: parent
                                        anchors.margins: 20
                                        spacing: 12

                                        Rectangle {
                                            Layout.fillWidth: true
                                            Layout.preferredHeight: 86
                                            radius: 16
                                            color: root.themeCard
                                            border.width: 1
                                            border.color: root.themeBorder

                                            RowLayout {
                                                anchors.fill: parent
                                                anchors.margins: 14
                                                spacing: 12

                                                ScoreRing {
                                                    Layout.preferredWidth: 58
                                                    Layout.preferredHeight: 58
                                                    value: backend.selectedScoreValue > 0 ? backend.selectedScoreValue : 85
                                                }

                                                ColumnLayout {
                                                    Layout.fillWidth: true
                                                    spacing: 2
                                                    Text {
                                                        Layout.fillWidth: true
                                                        text: backend.selectedCandidateName
                                                        color: root.themeText
                                                        font.pixelSize: 14
                                                        font.weight: Font.Bold
                                                        elide: Text.ElideRight
                                                    }
                                                    Text {
                                                        Layout.fillWidth: true
                                                        text: backend.selectedEmail
                                                        color: root.themeText2
                                                        font.pixelSize: 11
                                                        elide: Text.ElideRight
                                                    }
                                                    Text {
                                                        Layout.fillWidth: true
                                                        text: backend.selectedDecisionLabel + " | " + backend.selectedConfidence
                                                        color: root.themeMuted
                                                        font.pixelSize: 10
                                                        elide: Text.ElideRight
                                                    }
                                                }
                                            }
                                        }

                                        FieldLabel { text: "TO" }
                                        Text {
                                            Layout.fillWidth: true
                                            text: backend.selectedEmail
                                            color: root.themeMuted
                                            font.pixelSize: 13
                                            elide: Text.ElideRight
                                        }

                                        FieldLabel { text: "SUBJECT" }
                                        Text {
                                            Layout.fillWidth: true
                                            text: backend.templatePreviewSubject
                                            color: root.darkTheme ? "#ffffff" : root.themeText
                                            wrapMode: Text.WordWrap
                                            font.pixelSize: 15
                                            font.weight: Font.Bold
                                        }

                                        Rectangle {
                                            Layout.fillWidth: true
                                            height: 1
                                            color: root.themeBorder
                                        }

                                        Text {
                                            Layout.fillWidth: true
                                            Layout.fillHeight: true
                                            text: backend.templatePreviewBody
                                            color: root.themeText2
                                            wrapMode: Text.WordWrap
                                            font.pixelSize: 13
                                            lineHeight: 1.22
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                SettingsPage {
                    onRequestTheme: (mode) => { root.darkTheme = (mode === "dark") }
                    onRequestMotion: (enabled) => { backend.motionEnabled = enabled }
                    onRequestPage: (index) => { root.pageIndex = index }
                }

                InboxPage {
                    pageMargin: root.contentMargin
                    maxWidth: root.contentMaxWidth
                    surface: root.themeCard
                    surfaceAlt: root.themeCardAlt
                    border: root.themeBorder
                    textColor: root.themeText
                    textMuted: root.themeText2
                    subtle: root.themeMuted
                    primary: root.themePrimary
                    success: root.themeSuccess
                    warning: root.themeWarning
                    danger: root.themeDanger
                }
            }
        }
    }
}
