import QtQuick
import QtQuick.Effects
import "../theme"

// Themed surface card with optional hover-elevate. Content goes in `default`.
Rectangle {
    id: card

    property bool hoverable: false
    property bool elevated: false
    property int pad: Theme.space5
    default property alias content: body.data

    color: elevated ? Theme.surfaceElevated : Theme.surface
    radius: Theme.radiusLg
    border.width: 1
    border.color: hovered && hoverable ? Theme.borderStrong : Theme.border
    implicitWidth: body.implicitWidth + pad * 2
    implicitHeight: body.implicitHeight + pad * 2

    property bool hovered: false
    scale: (hoverable && hovered && !Theme.reducedMotion) ? 1.01 : 1.0

    Behavior on color { ColorAnimation { duration: Theme.durHover } }
    Behavior on border.color { ColorAnimation { duration: Theme.durHover } }
    Behavior on scale { NumberAnimation { duration: Theme.durHover; easing.type: Easing.OutCubic } }

    layer.enabled: !Theme.reducedMotion
    layer.effect: MultiEffect {
        shadowEnabled: true
        shadowColor: Theme.shadowColor
        shadowOpacity: card.hovered && card.hoverable ? Theme.shadowOpacity : Theme.shadowOpacity * 0.55
        shadowBlur: card.hovered && card.hoverable ? 0.9 : 0.55
        shadowVerticalOffset: 6
    }

    Item {
        id: body
        anchors.fill: parent
        anchors.margins: card.pad
    }

    HoverHandler {
        enabled: card.hoverable
        onHoveredChanged: card.hovered = hovered
    }
}
