import QtQuick
import QtQuick.Controls
import QtQuick.Effects
import "../theme"

Button {
    id: control

    // Defaults now follow the current "Ledger" teal theme instead of a
    // leftover purple/blue palette from an earlier design — every call site
    // already overrides these explicitly, so this only changes the
    // (previously dead) fallback look.
    property color fill: Theme.surfaceElevated
    property color fillHover: Theme.surfaceMuted
    property color fillPressed: Theme.surfaceMuted
    property color stroke: Theme.border
    property color textColor: Theme.textPrimary
    property bool strong: false
    property real radius: 12

    implicitHeight: 46
    implicitWidth: Math.max(132, contentItem.implicitWidth + 42)
    padding: 0
    hoverEnabled: true

    // Disabled buttons previously looked almost identical to enabled ones —
    // only the text/border color shifted slightly, background fill didn't
    // change at all — so a correctly-disabled button (e.g. "Clear all" with
    // nothing to clear) read as broken/unresponsive rather than as
    // intentionally off. One clear, uniform dim signal fixes that.
    opacity: control.enabled ? 1 : 0.45

    scale: Theme.reducedMotion ? 1 : (down ? 0.965 : (hovered ? 1.018 : 1))

    Behavior on scale {
        NumberAnimation { duration: Theme.durMicro; easing.type: Easing.OutCubic }
    }

    contentItem: Text {
        text: control.text
        color: control.enabled ? control.textColor : Theme.textMuted
        font.pixelSize: 14
        font.weight: Font.DemiBold
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        id: bgRect
        radius: control.radius
        border.width: 1
        border.color: control.enabled ? (control.hovered ? Qt.lighter(control.stroke, 1.2) : control.stroke) : Theme.border
        color: control.down ? control.fillPressed : (control.hovered ? control.fillHover : control.fill)
        opacity: control.hovered ? 0.96 : 1

        Behavior on opacity { NumberAnimation { duration: Theme.durMicro; easing.type: Easing.OutCubic } }
        Behavior on color { ColorAnimation { duration: Theme.durHover } }
        Behavior on border.color { ColorAnimation { duration: Theme.durHover } }

        // Signature colored glow on primary CTAs — reserved for these
        // buttons specifically so it reads as a deliberate accent, not
        // ambient shadow noise under every control.
        layer.enabled: control.strong && !Theme.reducedMotion
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: Theme.glowColor
            shadowOpacity: control.hovered ? Theme.glowOpacityActive : Theme.glowOpacityHover
            shadowBlur: Theme.glowBlur
            shadowVerticalOffset: 2
            shadowHorizontalOffset: 0
        }

        // Gradient overlay for strong (primary CTA) style buttons — the
        // one signature-gradient touch, on the highest-emphasis buttons only.
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            visible: control.strong
            opacity: control.hovered ? 0.55 : 0.4
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: Theme.primaryGradientStart }
                GradientStop { position: 1; color: Theme.primaryGradientEnd }
            }
            Behavior on opacity {
                NumberAnimation { duration: Theme.durMicro; easing.type: Easing.OutCubic }
            }
        }
    }
}
