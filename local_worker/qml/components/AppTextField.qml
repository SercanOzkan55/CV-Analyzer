import QtQuick
import QtQuick.Controls
import "../theme"

// Themed single-line text input with a focus ring.
Rectangle {
    id: root
    property alias text: field.text
    property string placeholder: ""
    property bool readOnlyField: false
    signal editingFinished()

    implicitHeight: 40
    implicitWidth: 200
    radius: Theme.radiusMd
    color: Theme.surfaceMuted
    border.width: field.activeFocus ? 2 : 1
    border.color: field.activeFocus ? Theme.primary : Theme.border
    Behavior on border.color { ColorAnimation { duration: Theme.durHover } }

    TextField {
        id: field
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        verticalAlignment: Text.AlignVCenter
        placeholderText: root.placeholder
        placeholderTextColor: Theme.textMuted
        color: Theme.textPrimary
        font.pixelSize: Typography.labelSize
        selectionColor: Theme.primary
        selectByMouse: true
        readOnly: root.readOnlyField
        background: null
        onEditingFinished: root.editingFinished()
    }
}
