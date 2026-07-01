import QtQuick
import QtQuick.Controls
import "../theme"

// Themed multi-line text input with a focus ring and internal scrolling.
// Uses the Flickable + TextArea.flickable pattern so wrap mode reliably wraps
// to the viewport width (no horizontal clipping); mono mode keeps the natural
// width so wide tables can scroll sideways.
Rectangle {
    id: root
    property alias text: area.text
    property string placeholder: ""
    property bool readOnlyField: false
    property bool mono: false
    signal editingFinished()

    implicitHeight: 120
    implicitWidth: 240
    radius: Theme.radiusMd
    color: Theme.surfaceMuted
    border.width: area.activeFocus ? 2 : 1
    border.color: area.activeFocus ? Theme.primary : Theme.border
    Behavior on border.color { ColorAnimation { duration: Theme.durHover } }

    Flickable {
        id: flick
        anchors.fill: parent
        anchors.margins: 6
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        ScrollBar.horizontal: ScrollBar { policy: root.mono ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff }

        TextArea.flickable: TextArea {
            id: area
            placeholderText: root.placeholder
            placeholderTextColor: Theme.textMuted
            color: Theme.textPrimary
            font.pixelSize: Typography.labelSize
            font.family: root.mono ? "Cascadia Mono, Consolas, monospace" : font.family
            selectionColor: Theme.primary
            selectByMouse: true
            readOnly: root.readOnlyField
            wrapMode: root.mono ? TextArea.NoWrap : TextArea.Wrap
            background: null
            onEditingFinished: root.editingFinished()
        }
    }
}
