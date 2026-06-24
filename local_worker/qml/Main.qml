import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts
import QtCore
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

    onDarkThemeChanged: uiSettings.darkTheme = darkTheme
    onPageIndexChanged: pageAnimKey += 1

    Settings {
        id: uiSettings
        category: "ui"
        property bool darkTheme: true
    }

    Component.onCompleted: {
        darkTheme = uiSettings.darkTheme
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

                ScrollView {
                    id: analyzeScroll
                    clip: true

                    ColumnLayout {
                        x: root.contentX(analyzeScroll.availableWidth)
                        y: 28
                        width: root.contentWidth(analyzeScroll.availableWidth)
                        spacing: 18

                        GlassCard {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 164
                            cardColor: root.themeCard
                            strokeColor: root.themeBorder
                            glowColor: "#7c5cff"

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 18
                                spacing: 18

                                ColumnLayout {
                                    Layout.preferredWidth: 260
                                    Layout.fillHeight: true
                                    spacing: 10

                                    Pill { text: "SETUP FLOW"; tint: "#7c5cff" }

                                    Text {
                                        Layout.fillWidth: true
                                        text: backend.setupCompletion + "% ready"
                                        color: root.themeText
                                        font.pixelSize: 28
                                        font.weight: Font.Black
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: backend.setupStepLabel
                                        color: root.themeText2
                                        font.pixelSize: 12
                                        wrapMode: Text.WordWrap
                                    }

                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 8
                                        radius: 4
                                        color: root.themeBorder
                                        Rectangle {
                                            width: parent.width * backend.setupCompletion / 100
                                            height: parent.height
                                            radius: parent.radius
                                            color: root.themePrimary
                                            Behavior on width { NumberAnimation { duration: 260; easing.type: Easing.OutCubic } }
                                        }
                                    }
                                }

                                SetupStep {
                                    Layout.fillWidth: true
                                    title: "Choose source"
                                    detail: backend.cvFolder ? "CV folder selected" : "Pick a local CV folder"
                                    number: 1
                                    complete: backend.cvFolder.length > 0
                                    active: backend.cvFolder.length === 0
                                }
                                SetupStep {
                                    Layout.fillWidth: true
                                    title: "Define role"
                                    detail: "Job description or required skills"
                                    number: 2
                                    complete: backend.jobDescription.length > 0 || backend.requiredSkills.length > 0
                                    active: backend.cvFolder.length > 0 && !(backend.jobDescription.length > 0 || backend.requiredSkills.length > 0)
                                }
                                SetupStep {
                                    Layout.fillWidth: true
                                    title: "Tune scoring"
                                    detail: "Accept/review thresholds"
                                    number: 3
                                    complete: backend.acceptThreshold > backend.reviewThreshold
                                    active: backend.acceptThreshold <= backend.reviewThreshold
                                }
                                SetupStep {
                                    Layout.fillWidth: true
                                    title: "Run locally"
                                    detail: backend.isRunning ? "Batch in progress" : "Ready for offline analysis"
                                    number: 4
                                    complete: backend.totalCandidates > 0
                                    active: backend.setupCompletion >= 100 && backend.totalCandidates === 0
                                }
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 20

                            GlassCard {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 548

                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 26
                                    spacing: 16

                                    Text {
                                        text: "Local job setup"
                                        color: root.darkTheme ? "#ffffff" : root.themeText
                                        font.pixelSize: 22
                                        font.weight: Font.Black
                                    }

                                    FieldLabel { text: "JOB NAME" }
                                    ProTextField {
                                        Layout.fillWidth: true
                                        text: backend.jobName
                                        onTextChanged: if (backend.jobName !== text) backend.jobName = text
                                    }

                                    FieldLabel { text: "CV FOLDER" }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 10
                                        PathBox {
                                            Layout.fillWidth: true
                                            placeholder: "Select CV folder..."
                                            path: backend.cvFolder
                                        }
                                        AppButton {
                                            text: "Browse"
                                            onClicked: cvFolderDialog.open()
                                        }
                                    }

                                    FieldLabel { text: "OUTPUT FOLDER" }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 10
                                        PathBox {
                                            Layout.fillWidth: true
                                            placeholder: "Select output folder..."
                                            path: backend.outputFolder
                                        }
                                        AppButton {
                                            text: "Browse"
                                            onClicked: outputFolderDialog.open()
                                        }
                                    }

                                    FieldLabel { text: "JOB DESCRIPTION" }
                                    ProTextArea {
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        placeholderText: "Paste the job description or role expectations..."
                                        text: backend.jobDescription
                                        onTextChanged: if (backend.jobDescription !== text) backend.jobDescription = text
                                    }
                                }
                            }

                            GlassCard {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 548

                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 26
                                    spacing: 16

                                    Text {
                                        text: "Scoring criteria"
                                        color: root.darkTheme ? "#ffffff" : root.themeText
                                        font.pixelSize: 22
                                        font.weight: Font.Black
                                    }

                                    FieldLabel { text: "REQUIRED SKILLS" }
                                    ProTextField {
                                        Layout.fillWidth: true
                                        placeholderText: "Python, React, SQL..."
                                        text: backend.requiredSkills
                                        onTextChanged: if (backend.requiredSkills !== text) backend.requiredSkills = text
                                    }

                                    FieldLabel { text: "NICE TO HAVE" }
                                    ProTextField {
                                        Layout.fillWidth: true
                                        placeholderText: "Docker, GraphQL, AWS..."
                                        text: backend.niceToHaveSkills
                                        onTextChanged: if (backend.niceToHaveSkills !== text) backend.niceToHaveSkills = text
                                    }

                                    FieldLabel { text: "HARD REJECT CRITERIA" }
                                    ProTextField {
                                        Layout.fillWidth: true
                                        placeholderText: "Missing work permit, wrong seniority..."
                                        text: backend.hardRejectCriteria
                                        onTextChanged: if (backend.hardRejectCriteria !== text) backend.hardRejectCriteria = text
                                    }

                                    FieldLabel { text: "ACCEPT THRESHOLD: " + backend.acceptThreshold + "%" }
                                    ProSlider {
                                        Layout.fillWidth: true
                                        from: 30
                                        to: 100
                                        stepSize: 1
                                        value: backend.acceptThreshold
                                        onMoved: backend.acceptThreshold = Math.round(value)
                                    }

                                    FieldLabel { text: "REVIEW THRESHOLD: " + backend.reviewThreshold + "%" }
                                    ProSlider {
                                        Layout.fillWidth: true
                                        from: 10
                                        to: 90
                                        stepSize: 1
                                        value: backend.reviewThreshold
                                        onMoved: backend.reviewThreshold = Math.round(value)
                                    }

                                    FieldLabel { text: "AI REVIEW MODE" }
                                    ProComboBox {
                                        Layout.fillWidth: true
                                        model: ["none", "customer_openai_key"]
                                        currentIndex: backend.aiMode === "customer_openai_key" ? 1 : 0
                                        onActivated: backend.aiMode = currentText
                                    }

                                    Text {
                                        visible: backend.aiMode === "customer_openai_key"
                                        text: "⚠ Bu mod, CV metin özetlerini (maks. 6000 karakter) ve iş detaylarını OpenAI sunucularına gönderir. Verileriniz yerel kalmaz."
                                        color: "#e65100"
                                        wrapMode: Text.WordWrap
                                        font.pixelSize: 11
                                        Layout.fillWidth: true
                                        Layout.topMargin: 4
                                    }

                                    Item { Layout.fillHeight: true }

                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 12
                                        AppButton {
                                            Layout.fillWidth: true
                                            text: backend.isRunning ? "Running..." : "Analyze local folder"
                                            strong: true
                                            enabled: !backend.isRunning
                                            onClicked: backend.startAnalysis()
                                        }
                                        AppButton {
                                            text: "Cancel"
                                            enabled: backend.isRunning
                                            onClicked: backend.cancelAnalysis()
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                ResultsPage {}

                ScrollView {
                    id: historyScroll
                    clip: true

                    ColumnLayout {
                        x: root.contentX(historyScroll.availableWidth)
                        y: 28
                        width: root.contentWidth(historyScroll.availableWidth)
                        spacing: 18

                        RowLayout {
                            Layout.fillWidth: true
                            Text {
                                Layout.fillWidth: true
                                text: "Recent local runs"
                                color: root.darkTheme ? "#ffffff" : root.themeText
                                font.pixelSize: 24
                                font.weight: Font.Black
                            }
                            AppButton {
                                text: "Refresh"
                                onClicked: backend.refreshHistory()
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 132
                            spacing: 14

                            GlassCard {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                cardColor: root.themeCard
                                strokeColor: root.themeBorder
                                glowColor: "#7c5cff"

                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 18
                                    spacing: 8
                                    Pill { text: "CURRENT"; tint: "#7c5cff" }
                                    Text {
                                        Layout.fillWidth: true
                                        text: backend.currentRunSummary
                                        color: root.themeText
                                        font.pixelSize: 16
                                        font.weight: Font.Black
                                        wrapMode: Text.WordWrap
                                    }
                                }
                            }

                            GlassCard {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                cardColor: root.themeCard
                                strokeColor: root.themeBorder
                                glowColor: "#35a7ff"

                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 18
                                    spacing: 8
                                    Pill { text: "PREVIOUS"; tint: "#35a7ff" }
                                    Text {
                                        Layout.fillWidth: true
                                        text: backend.previousRunSummary
                                        color: root.themeText2
                                        font.pixelSize: 15
                                        font.weight: Font.Bold
                                        wrapMode: Text.WordWrap
                                    }
                                }
                            }

                            GlassCard {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                cardColor: root.themeCard
                                strokeColor: root.themeBorder
                                glowColor: "#2ee59d"

                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 18
                                    spacing: 8
                                    Pill { text: "DELTA"; tint: "#2ee59d" }
                                    Text {
                                        Layout.fillWidth: true
                                        text: backend.runDeltaSummary
                                        color: root.themeSuccess
                                        font.pixelSize: 15
                                        font.weight: Font.Bold
                                        wrapMode: Text.WordWrap
                                    }
                                }
                            }
                        }

                        GlassCard {
                            Layout.fillWidth: true
                            Layout.preferredHeight: backend.historyRunCount > 0 ? 560 : 320

                            ListView {
                                anchors.fill: parent
                                anchors.margins: 18
                                spacing: 12
                                clip: true
                                model: backend.historyModel

                                delegate: Rectangle {
                                    id: historyRow
                                    width: ListView.view.width
                                    height: 96
                                    radius: 18
                                    color: historyMouse.containsMouse ? "#101827" : "#0b1322"
                                    border.width: 1
                                    border.color: historyMouse.containsMouse ? "#3d4b72" : "#253856"
                                    scale: historyMouse.containsMouse ? 1.006 : 1
                                    transformOrigin: Item.Center
                                    Behavior on color { ColorAnimation { duration: 140 } }
                                    Behavior on border.color { ColorAnimation { duration: 140 } }
                                    Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }

                                    MouseArea {
                                        id: historyMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            backend.loadRun(runId)
                                            root.pageIndex = 2
                                        }
                                    }

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.margins: 16
                                        spacing: 16

                                        Rectangle {
                                            Layout.preferredWidth: 54
                                            Layout.preferredHeight: 54
                                            radius: 18
                                            color: root.themeCardAlt
                                            border.width: 1
                                            border.color: root.themeBorder
                                            Text {
                                                anchors.centerIn: parent
                                                text: "#" + runId
                                                color: root.themePrimary
                                                font.pixelSize: 14
                                                font.weight: Font.Black
                                            }
                                        }

                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 4
                                            Text {
                                                text: jobName
                                                color: root.darkTheme ? "#ffffff" : root.themeText
                                                font.pixelSize: 16
                                                font.weight: Font.Bold
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: totalFiles + " files | " + createdAt
                                                color: root.themeText2
                                                font.pixelSize: 12
                                                elide: Text.ElideRight
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: outputFolder
                                                color: root.themeMuted
                                                font.pixelSize: 11
                                                elide: Text.ElideMiddle
                                            }
                                        }

                                        AppButton {
                                            text: "Load"
                                            onClicked: {
                                                backend.loadRun(runId)
                                                root.pageIndex = 2
                                            }
                                        }
                                    }
                                }

                                EmptyState {
                                    anchors.fill: parent
                                    anchors.margins: 18
                                    visible: backend.historyRunCount === 0
                                    title: "No local runs yet"
                                    detail: "Completed analyses will appear here with output folders and reload actions."
                                    actionText: "Create first run"
                                    targetPage: 1
                                }
                            }
                        }
                    }
                }

                ScrollView {
                    id: syncScroll
                    clip: true

                    ColumnLayout {
                        x: root.contentX(syncScroll.availableWidth)
                        y: 28
                        width: root.contentWidth(syncScroll.availableWidth)
                        spacing: 18

                        GlassCard {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 190
                            cardColor: root.themeCard
                            strokeColor: backend.syncConnected ? "#2ee59d" : "#314164"
                            glowColor: backend.syncConnected ? "#2ee59d" : "#7c5cff"

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 22
                                spacing: 22

                                Rectangle {
                                    Layout.preferredWidth: 88
                                    Layout.preferredHeight: 88
                                    radius: 28
                                    color: backend.syncConnected ? "#123326" : "#18152f"
                                    border.width: 1
                                    border.color: backend.syncConnected ? "#2ee59d" : "#725cff"
                                    scale: backend.syncRunning ? 1.04 : 1
                                    Behavior on scale { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

                                    Rectangle {
                                        anchors.centerIn: parent
                                        width: parent.width + 18
                                        height: width
                                        radius: width / 2
                                        color: "transparent"
                                        border.width: 1
                                        border.color: backend.syncConnected ? "#2ee59d" : "#7c5cff"
                                        opacity: 0.18
                                        SequentialAnimation on scale {
                                            running: backend.motionEnabled && backend.syncRunning
                                            loops: Animation.Infinite
                                            NumberAnimation { from: 0.78; to: 1.18; duration: 880; easing.type: Easing.OutCubic }
                                            NumberAnimation { from: 1.18; to: 0.78; duration: 760; easing.type: Easing.InCubic }
                                        }
                                    }

                                    Text {
                                        anchors.centerIn: parent
                                        text: "SYNC"
                                        color: root.darkTheme ? "#ffffff" : root.themeText
                                        font.pixelSize: 14
                                        font.weight: Font.Black
                                    }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    Pill {
                                        text: backend.syncBadge
                                        tint: backend.syncConnected ? "#2ee59d" : "#7c5cff"
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: "Website Sync Bridge"
                                        color: root.themeText
                                        font.pixelSize: 30
                                        font.weight: Font.Black
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: backend.syncDetail
                                        color: root.themeText2
                                        font.pixelSize: 13
                                        wrapMode: Text.WordWrap
                                    }
                                }

                                MetricCard {
                                    Layout.preferredWidth: 180
                                    label: "Pending"
                                    value: backend.syncPendingCount
                                    detail: "Local results"
                                    accent: "#ffb84d"
                                }

                                MetricCard {
                                    Layout.preferredWidth: 180
                                    label: "Quota"
                                    value: backend.syncConnected ? backend.syncQuotaRemaining : "-"
                                    detail: "Remaining scans"
                                    accent: "#2ee59d"
                                }

                                MetricCard {
                                    Layout.preferredWidth: 180
                                    label: "Last Sync"
                                    value: backend.syncLastSyncedCount
                                    detail: "Uploaded"
                                    accent: "#35a7ff"
                                }
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 500
                            spacing: 18

                            GlassCard {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                cardColor: root.themeCard
                                strokeColor: root.themeBorder
                                glowColor: "#7c5cff"

                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 22
                                    spacing: 14

                                    Text {
                                        text: "Connection"
                                        color: root.darkTheme ? "#ffffff" : root.themeText
                                        font.pixelSize: 22
                                        font.weight: Font.Black
                                    }

                                    FieldLabel { text: "WEBSITE WORKER API URL" }
                                    ProTextField {
                                        Layout.fillWidth: true
                                        text: backend.syncApiUrl
                                        placeholderText: "http://127.0.0.1:8001/api/worker"
                                        onTextChanged: if (backend.syncApiUrl !== text) backend.syncApiUrl = text
                                    }

                                    FieldLabel { text: "WORKER KEY" }
                                    ProTextField {
                                        Layout.fillWidth: true
                                        text: backend.syncApiKey
                                        echoMode: TextInput.Password
                                        placeholderText: "Paste worker key from Website"
                                        onTextChanged: if (backend.syncApiKey !== text) backend.syncApiKey = text
                                    }

                                    FieldLabel { text: "TARGET WEBSITE JOB ID" }
                                    ProTextField {
                                        Layout.fillWidth: true
                                        text: backend.syncJobId
                                        placeholderText: backend.syncAllowedJobs === "-" ? "Enter job id..." : "Allowed: " + backend.syncAllowedJobs
                                        onTextChanged: if (backend.syncJobId !== text) backend.syncJobId = text
                                    }

                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 10
                                        AppButton {
                                            Layout.fillWidth: true
                                            text: "Save Key"
                                            onClicked: backend.saveWorkerKey()
                                        }
                                        AppButton {
                                            Layout.fillWidth: true
                                            text: backend.syncRunning ? "Testing..." : "Test Connection"
                                            strong: true
                                            enabled: !backend.syncRunning
                                            onClicked: backend.testWebsiteSync()
                                        }
                                    }

                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 128
                                        radius: 16
                                        color: root.themeInput
                                        border.width: 1
                                        border.color: backend.syncConnected ? "#2ee59d" : "#26314d"

                                        ColumnLayout {
                                            anchors.fill: parent
                                            anchors.margins: 14
                                            spacing: 5
                                            Text {
                                                Layout.fillWidth: true
                                                text: backend.syncStatus
                                                color: backend.syncConnected ? "#b8f7dd" : "#f4f7ff"
                                                font.pixelSize: 14
                                                font.weight: Font.Black
                                                elide: Text.ElideRight
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: "Company: " + backend.syncCompanyId + " | Jobs: " + backend.syncAllowedJobs
                                                color: root.themeText2
                                                font.pixelSize: 12
                                                elide: Text.ElideRight
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: "Access scope: " + backend.syncPermissionSummary
                                                color: backend.syncConnected ? "#9ff3d0" : root.themeText2
                                                font.pixelSize: 12
                                                wrapMode: Text.WordWrap
                                                maximumLineCount: 2
                                                elide: Text.ElideRight
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: "Only scores, decisions, and analysis metadata are uploaded when you sync."
                                                color: root.themeMuted
                                                font.pixelSize: 11
                                                wrapMode: Text.WordWrap
                                            }
                                        }
                                    }
                                }
                            }

                            GlassCard {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                cardColor: root.themeCard
                                strokeColor: root.themeBorder
                                glowColor: "#35a7ff"

                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 22
                                    spacing: 14

                                    RowLayout {
                                        Layout.fillWidth: true
                                        Text {
                                            Layout.fillWidth: true
                                            text: "Sync Queue"
                                            color: root.darkTheme ? "#ffffff" : root.themeText
                                            font.pixelSize: 22
                                            font.weight: Font.Black
                                        }
                                        AppButton {
                                            text: "Refresh"
                                            onClicked: backend.refreshSyncQueue()
                                        }
                                    }

                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 150
                                        radius: 18
                                        color: root.themeInput
                                        border.width: 1
                                        border.color: root.themeBorder

                                        ColumnLayout {
                                            anchors.centerIn: parent
                                            width: Math.min(parent.width - 38, 420)
                                            spacing: 10

                                            Text {
                                                Layout.fillWidth: true
                                                text: backend.syncPendingCount > 0 ? backend.syncPendingCount + " local result(s) waiting" : "Queue is clean"
                                                color: root.themeText
                                                font.pixelSize: 20
                                                font.weight: Font.Black
                                                horizontalAlignment: Text.AlignHCenter
                                            }

                                            Text {
                                                Layout.fillWidth: true
                                                text: backend.syncPendingCount > 0 ? "Review results, choose a Website job id, then upload when ready." : "Run an analysis or change a decision to create a sync queue."
                                                color: root.themeText2
                                                font.pixelSize: 12
                                                wrapMode: Text.WordWrap
                                                horizontalAlignment: Text.AlignHCenter
                                            }
                                        }
                                    }

                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 10
                                        AppButton {
                                            Layout.fillWidth: true
                                            text: "Open Results"
                                            onClicked: root.pageIndex = 2
                                        }
                                        AppButton {
                                            Layout.fillWidth: true
                                            text: backend.syncRunning ? "Syncing..." : "Sync Pending Results"
                                            strong: true
                                            enabled: !backend.syncRunning && backend.syncPendingCount > 0
                                            onClicked: backend.syncPendingResults()
                                        }
                                    }

                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        radius: 18
                                        color: root.themeInput
                                        border.width: 1
                                        border.color: root.themeBorder

                                        ColumnLayout {
                                            anchors.fill: parent
                                            anchors.margins: 16
                                            spacing: 10
                                            Text {
                                                text: "Sync Safety"
                                                color: root.themeText
                                                font.pixelSize: 16
                                                font.weight: Font.Black
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: "1. CV files stay local unless you use website upload flows.\n2. This bridge sends ranked result metadata to the selected website job.\n3. Changed decisions are marked pending again so the website can be updated."
                                                color: root.themeText2
                                                font.pixelSize: 12
                                                wrapMode: Text.WordWrap
                                                lineHeight: 1.22
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                ScrollView {
                    id: reportsScroll
                    clip: true

                    ColumnLayout {
                        x: root.contentX(reportsScroll.availableWidth)
                        y: 28
                        width: root.contentWidth(reportsScroll.availableWidth)
                        spacing: 18

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 12
                            MetricCard { label: "Candidates"; value: backend.totalCandidates; detail: "Current report"; accent: "#28e0e6"; surface: root.themeCard; stroke: root.themeBorder; primaryText: root.themeText; mutedText: root.themeText2; subtleText: root.themeMuted }
                            MetricCard { label: "Average Score"; value: backend.averageScoreValue > 0 ? backend.averageScore : "-"; detail: "Current run"; accent: "#35a7ff"; surface: root.themeCard; stroke: root.themeBorder; primaryText: root.themeText; mutedText: root.themeText2; subtleText: root.themeMuted }
                            MetricCard { label: "Shortlisted"; value: backend.shortlistedCount; detail: "Accept queue"; accent: "#2ee59d"; surface: root.themeCard; stroke: root.themeBorder; primaryText: root.themeText; mutedText: root.themeText2; subtleText: root.themeMuted }
                            MetricCard { label: "Review"; value: backend.reviewCount; detail: "Manual check"; accent: "#ffb84d"; surface: root.themeCard; stroke: root.themeBorder; primaryText: root.themeText; mutedText: root.themeText2; subtleText: root.themeMuted }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 172
                            spacing: 14

                            GlassCard {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                cardColor: root.themeCard
                                strokeColor: root.themeBorder
                                glowColor: "#7c5cff"

                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 18
                                    spacing: 9
                                    Pill { text: "OUTPUT PACKAGE"; tint: "#7c5cff" }
                                    Text {
                                        Layout.fillWidth: true
                                        text: "Generated local files"
                                        color: root.themeText
                                        font.pixelSize: 18
                                        font.weight: Font.Black
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: "local_worker_results.csv, local_worker_results.json, local_worker_report.html, sync_manifest.json"
                                        color: root.themeText2
                                        font.pixelSize: 12
                                        wrapMode: Text.WordWrap
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: "Output folder: " + backend.outputFolder
                                        color: root.themeMuted
                                        font.pixelSize: 11
                                        elide: Text.ElideMiddle
                                    }
                                }
                            }

                            GlassCard {
                                Layout.preferredWidth: 330
                                Layout.fillHeight: true
                                cardColor: root.themeCard
                                strokeColor: root.themeBorder
                                glowColor: "#2ee59d"

                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 18
                                    spacing: 10
                                    Text {
                                        text: "Sync manifest"
                                        color: root.themeText
                                        font.pixelSize: 18
                                        font.weight: Font.Black
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: backend.syncPendingCount + " result(s) waiting for website sync."
                                        color: root.themeText2
                                        font.pixelSize: 13
                                        wrapMode: Text.WordWrap
                                    }
                                    AppButton {
                                        Layout.fillWidth: true
                                        text: "Open Website Sync"
                                        strong: backend.syncPendingCount > 0
                                        onClicked: root.pageIndex = 4
                                    }
                                }
                            }
                        }

                        GlassCard {
                            Layout.fillWidth: true
                            Layout.preferredHeight: backend.totalCandidates > 0 ? 460 : 320

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 24
                                spacing: 16

                                RowLayout {
                                    Layout.fillWidth: true
                                    Text {
                                        Layout.fillWidth: true
                                        text: "Local report preview"
                                        color: root.darkTheme ? "#ffffff" : root.themeText
                                        font.pixelSize: 24
                                        font.weight: Font.Black
                                    }
                                    AppButton {
                                        text: "Export CSV"
                                        onClicked: backend.exportCurrentCsv()
                                    }
                                    AppButton {
                                        text: "Open output"
                                        onClicked: backend.openOutputFolder()
                                    }
                                }

                                ProTextArea {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    visible: backend.totalCandidates > 0
                                    readOnly: true
                                    text: backend.reportPreview
                                }

                                EmptyState {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    visible: backend.totalCandidates === 0
                                    title: "No report yet"
                                    detail: "Run a local analysis to generate CSV, JSON, HTML report, and sync manifest files."
                                    actionText: "Start analysis"
                                    targetPage: 1
                                }
                            }
                        }
                    }
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

                ScrollView {
                    id: settingsScroll
                    clip: true

                    ColumnLayout {
                        x: root.contentX(settingsScroll.availableWidth)
                        y: 28
                        width: root.contentWidth(settingsScroll.availableWidth)
                        spacing: 18

                        RowLayout {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 180
                            spacing: 14

                            MetricCard { label: "Runtime"; value: "Qt Quick"; detail: "Native desktop UI"; accent: root.themePrimary; surface: root.themeCard; stroke: root.themeBorder; primaryText: root.themeText; mutedText: root.themeText2; subtleText: root.themeMuted }
                            MetricCard { label: "Motion"; value: backend.motionEnabled ? "On" : "Off"; detail: "CV_WORKER_DISABLE_MOTION"; accent: backend.motionEnabled ? root.themeSuccess : root.themeWarning; surface: root.themeCard; stroke: root.themeBorder; primaryText: root.themeText; mutedText: root.themeText2; subtleText: root.themeMuted }
                            MetricCard { label: "Runs"; value: backend.historyRunCount; detail: "Local workspace"; accent: root.themeSecondary; surface: root.themeCard; stroke: root.themeBorder; primaryText: root.themeText; mutedText: root.themeText2; subtleText: root.themeMuted }
                            MetricCard { label: "Sync Queue"; value: backend.syncPendingCount; detail: backend.syncBadge; accent: root.themeWarning; surface: root.themeCard; stroke: root.themeBorder; primaryText: root.themeText; mutedText: root.themeText2; subtleText: root.themeMuted }
                        }

                        GlassCard {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 150
                            cardColor: root.themeCard
                            strokeColor: root.themeBorder
                            glowColor: root.themePrimary

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 22
                                spacing: 18

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    Pill { text: "APPEARANCE"; tint: "#7c5cff" }
                                    Text {
                                        Layout.fillWidth: true
                                        text: "Theme, density, and motion"
                                        color: root.themeText
                                        font.pixelSize: 20
                                        font.weight: Font.Black
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: "The local UI now uses shared light/dark tokens with calmer surfaces, softer borders, and restrained motion."
                                        color: root.themeText2
                                        font.pixelSize: 13
                                        wrapMode: Text.WordWrap
                                    }
                                }

                                RowLayout {
                                    Layout.alignment: Qt.AlignVCenter
                                    spacing: 10

                                    AppButton {
                                        text: root.darkTheme ? "Switch to Light" : "Switch to Dark"
                                        strong: true
                                        onClicked: root.darkTheme = !root.darkTheme
                                    }
                                    Pill {
                                        text: "Comfortable density"
                                        tint: "#35a7ff"
                                    }
                                    Pill {
                                        text: backend.motionEnabled ? "Motion on" : "Motion reduced"
                                        tint: backend.motionEnabled ? "#2ee59d" : "#ffb84d"
                                    }
                                }
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 360
                            spacing: 18

                            GlassCard {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                cardColor: root.themeCard
                                strokeColor: root.themeBorder
                                glowColor: "#7c5cff"

                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 22
                                    spacing: 14

                                    Text {
                                        text: "Runtime & Privacy"
                                        color: root.darkTheme ? "#ffffff" : root.themeText
                                        font.pixelSize: 22
                                        font.weight: Font.Black
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: "The maintained QML interface runs as a native desktop shell. CV parsing, scoring, report creation, and template preview run locally on this computer. Website sync is explicit and only happens from the Website Sync screen."
                                        color: root.themeText2
                                        font.pixelSize: 13
                                        wrapMode: Text.WordWrap
                                        lineHeight: 1.24
                                    }
                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 1
                                        color: root.themeBorder
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: "Current output folder"
                                        color: root.themeText
                                        font.pixelSize: 14
                                        font.weight: Font.Bold
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: backend.outputFolder
                                        color: root.themeText2
                                        font.pixelSize: 12
                                        wrapMode: Text.WordWrap
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 10
                                        AppButton {
                                            Layout.fillWidth: true
                                            text: "Open output folder"
                                            onClicked: backend.openOutputFolder()
                                        }
                                        AppButton {
                                            Layout.fillWidth: true
                                            text: "Show app status"
                                            onClicked: backend.showAppStatus()
                                        }
                                    }
                                }
                            }

                            GlassCard {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                cardColor: root.themeCard
                                strokeColor: root.themeBorder
                                glowColor: "#35a7ff"

                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 22
                                    spacing: 14

                                    Text {
                                        text: "Website Sync Settings"
                                        color: root.darkTheme ? "#ffffff" : root.themeText
                                        font.pixelSize: 22
                                        font.weight: Font.Black
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: "Worker key storage uses the OS credential store when available. Connection checks and uploads are background tasks so the local UI stays responsive."
                                        color: root.themeText2
                                        font.pixelSize: 13
                                        wrapMode: Text.WordWrap
                                        lineHeight: 1.24
                                    }
                                    FieldLabel { text: "API URL" }
                                    Text {
                                        Layout.fillWidth: true
                                        text: backend.syncApiUrl
                                        color: root.themeText2
                                        font.pixelSize: 12
                                        elide: Text.ElideMiddle
                                    }
                                    FieldLabel { text: "CONNECTION" }
                                    Text {
                                        Layout.fillWidth: true
                                        text: backend.syncStatus + " | Jobs: " + backend.syncAllowedJobs
                                        color: backend.syncConnected ? "#b8f7dd" : "#ffdf9b"
                                        font.pixelSize: 12
                                        wrapMode: Text.WordWrap
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 10
                                        AppButton {
                                            Layout.fillWidth: true
                                            text: "Website Sync"
                                            strong: true
                                            onClicked: root.pageIndex = 4
                                        }
                                        AppButton {
                                            Layout.fillWidth: true
                                            text: "Refresh queue"
                                            onClicked: backend.refreshSyncQueue()
                                        }
                                    }
                                }
                            }
                        }

                        GlassCard {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 220
                            cardColor: root.themeCard
                            strokeColor: root.themeBorder
                            glowColor: "#2ee59d"

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 22
                                spacing: 12

                                Text {
                                    text: "Operational Notes"
                                    color: root.darkTheme ? "#ffffff" : root.themeText
                                    font.pixelSize: 22
                                    font.weight: Font.Black
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: "Use Analyze for local scoring, Results for review and decisions, Reports for generated local files, Templates for decision emails, and Website Sync only when you want to publish local results back to the SaaS account."
                                    color: root.themeText2
                                    font.pixelSize: 13
                                    wrapMode: Text.WordWrap
                                    lineHeight: 1.24
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 10
                                    Pill { text: "Local-first"; tint: "#2ee59d" }
                                    Pill { text: "Explicit sync"; tint: "#7c5cff" }
                                    Pill { text: "Credential store"; tint: "#35a7ff" }
                                    Pill { text: "Reduced motion env flag"; tint: "#ffb84d" }
                                }
                            }
                        }
                    }
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
