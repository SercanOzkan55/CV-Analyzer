import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects
import "../theme"

// Generic reusable confirm/cancel modal. No confirm/modal component existed
// before this (only the non-modal FolderDialog and the toast Popup in
// Main.qml) so this is deliberately generic rather than tied to any one
// action: callers set `title`/`message` (and optionally `confirmText`/
// `cancelText`) then call `.open()`; `confirmed()` fires when the user
// accepts, right before the popup closes itself. Cancel (or clicking
// outside / Escape) just closes it with no signal.
Popup {
    id: root
    modal: true
    focus: true
    anchors.centerIn: Overlay.overlay
    padding: Theme.space5
    width: Math.min(420, (Overlay.overlay ? Overlay.overlay.width : 420) - 56)
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    property string title: "Confirm"
    property string message: ""
    property string confirmText: "Confirm"
    property string cancelText: "Cancel"

    signal confirmed()

    background: Rectangle {
        radius: 18
        color: Theme.surfaceElevated
        border.width: 1
        border.color: Theme.border

        layer.enabled: !Theme.reducedMotion
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: Theme.shadowColor
            shadowOpacity: Theme.elevModalOpacity
            shadowBlur: Theme.elevModalBlur
            shadowVerticalOffset: Theme.elevModalYOffset
        }
    }

    contentItem: ColumnLayout {
        width: root.availableWidth
        spacing: Theme.space4

        Text {
            Layout.fillWidth: true
            text: root.title
            color: Theme.textPrimary
            font.pixelSize: Typography.subheadingSize
            font.weight: Typography.weightBold
        }
        Text {
            Layout.fillWidth: true
            text: root.message
            color: Theme.textSecondary
            font.pixelSize: Typography.labelSize
            wrapMode: Text.WordWrap
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.space2
            Item { Layout.fillWidth: true }
            AppButton {
                text: root.cancelText
                fill: Theme.surfaceElevated; fillHover: Theme.surfaceMuted
                fillPressed: Theme.surfaceMuted; stroke: Theme.border
                textColor: Theme.textPrimary
                onClicked: root.close()
            }
            AppButton {
                text: root.confirmText
                strong: true
                fill: Theme.primary; fillHover: Theme.primaryHover
                fillPressed: Qt.darker(Theme.primary, 1.15); stroke: Theme.primary
                textColor: "#ffffff"
                onClicked: { root.confirmed(); root.close() }
            }
        }
    }
}
