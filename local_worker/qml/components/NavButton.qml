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
    property bool active: false
    property bool collapsed: false
    property string glyph: ""
    property color activeColor: Theme.primary
    property color activeText: Theme.textPrimary
    property color textColor: Theme.textSecondary
    property color hoverText: Theme.textPrimary
    property color activeBg: Theme.primarySoft
    property color hoverBg: Theme.surfaceMuted
    property color activeIcon: Theme.primary
    property color mutedIcon: Theme.textSecondary
    readonly property bool motionOn: !Theme.reducedMotion && (typeof backend === "undefined" || backend.motionEnabled)
    signal navClicked()

    height: 44
    implicitWidth: 208
    hoverEnabled: true
    onClicked: navClicked()

    // Tooltip with the label when collapsed to an icon-only rail.
    ToolTip.visible: control.collapsed && control.hovered
    ToolTip.text: control.text
    ToolTip.delay: 350

    // Press contracts the whole item ("kapanma"); hover lifts it slightly.
    scale: motionOn ? (down ? 0.95 : (hovered ? 1.015 : 1)) : 1
    Behavior on scale { NumberAnimation { duration: motionOn ? (down ? 110 : 200) : 0; easing.type: Easing.OutCubic } }

    contentItem: Row {
        spacing: 12
        anchors.verticalCenter: parent.verticalCenter
        leftPadding: control.collapsed ? Math.max(0, (control.width - 20) / 2) : 14
        rightPadding: control.collapsed ? 0 : 12

        Icon {
            name: control.glyph
            size: 20
            tint: control.active ? control.activeIcon : (control.hovered ? control.hoverText : control.mutedIcon)
        }

        Text {
            visible: !control.collapsed
            text: control.text
            color: control.active ? control.activeText : (control.hovered ? control.hoverText : control.textColor)
            font.pixelSize: 14
            font.weight: control.active ? Font.DemiBold : Font.Medium
            verticalAlignment: Text.AlignVCenter
        }
    }

    background: Rectangle {
        radius: 12
        color: control.active ? control.activeBg : (control.hovered ? control.hoverBg : "transparent")
        border.width: control.active ? 1 : 0
        border.color: control.active ? Qt.rgba(control.activeColor.r, control.activeColor.g, control.activeColor.b, 0.45) : "transparent"
        Behavior on color { ColorAnimation { duration: Theme.durHover } }
        Behavior on border.color { ColorAnimation { duration: Theme.durHover } }

        // Signature colored glow on the active item — mirrors AppButton's
        // primary-CTA glow so "this is the important/selected one" reads
        // the same way across the app.
        layer.enabled: control.active && control.motionOn
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: control.activeColor
            shadowOpacity: Theme.glowOpacityActive
            shadowBlur: Theme.glowBlur
            shadowVerticalOffset: 0
            shadowHorizontalOffset: 0
        }

        // Hover "hallucination": a soft accent glow blooms over the item on
        // hover (a preview, distinct from the solid active state), contracts on
        // press, and is hidden once the item is actually active. Full activation
        // only happens on click — hover never fully "opens" the item.
        Rectangle {
            id: halo
            anchors.fill: parent
            radius: parent.radius
            visible: opacity > 0.001
            opacity: control.motionOn
                     ? (control.active ? 0 : (control.down ? 0.05 : (control.hovered ? 0.18 : 0)))
                     : 0
            transformOrigin: Item.Center
            scale: (control.hovered && !control.down) ? 1.0 : 0.85
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: Qt.rgba(control.activeColor.r, control.activeColor.g, control.activeColor.b, 0.9) }
                GradientStop { position: 0.55; color: Qt.rgba(control.activeColor.r, control.activeColor.g, control.activeColor.b, 0.22) }
                GradientStop { position: 1.0; color: Qt.rgba(control.activeColor.r, control.activeColor.g, control.activeColor.b, 0.0) }
            }
            Behavior on opacity { NumberAnimation { duration: control.motionOn ? 220 : 0; easing.type: Easing.OutCubic } }
            Behavior on scale { NumberAnimation { duration: control.motionOn ? 280 : 0; easing.type: Easing.OutBack; easing.overshoot: 0.7 } }
        }

        // Animated active accent bar on the left edge — grows in with a small
        // overshoot when the item becomes active.
        Rectangle {
            anchors.left: parent.left
            anchors.leftMargin: 3
            anchors.verticalCenter: parent.verticalCenter
            width: 3
            radius: 2
            color: control.activeColor
            height: control.active ? parent.height * 0.52 : 0
            opacity: control.active ? 1 : 0
            Behavior on height { NumberAnimation { duration: control.motionOn ? 240 : 0; easing.type: Easing.OutBack; easing.overshoot: 1.2 } }
            Behavior on opacity { NumberAnimation { duration: control.motionOn ? 160 : 0 } }
        }
    }
}
