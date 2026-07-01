import QtQuick
import QtQuick.Layouts
import "../theme"

// Title + optional subtitle for a content block, with an optional trailing
// action slot on the right.
RowLayout {
    id: root
    property string title: ""
    property string subtitle: ""
    default property alias actions: actionRow.data

    spacing: Theme.space4

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 2
        Text {
            Layout.fillWidth: true
            text: root.title
            color: Theme.textPrimary
            font.pixelSize: Typography.headingSize
            font.weight: Typography.weightBold
            elide: Text.ElideRight
        }
        Text {
            Layout.fillWidth: true
            visible: root.subtitle.length > 0
            text: root.subtitle
            color: Theme.textSecondary
            font.pixelSize: Typography.labelSize
            wrapMode: Text.WordWrap
        }
    }

    RowLayout {
        id: actionRow
        Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
        spacing: Theme.space2
    }
}
