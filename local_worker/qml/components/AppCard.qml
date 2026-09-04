import QtQuick
import QtQuick.Effects
import "../theme"

// Themed surface card with optional hover-elevate. Content goes in `default`.
Rectangle {
    id: card

    property bool hoverable: false
    property bool elevated: false
    property int pad: Theme.space5
    // Opt-in subtle 3D perspective tilt toward the cursor on hover. Pure
    // QtQuick transforms (no QtQuick3D / GPU scene) so it stays light and
    // verifiable; disabled under reduced motion.
    property bool tilt3d: false
    property real maxTilt: 5
    default property alias content: body.data

    // Content (e.g. a Repeater'd list) can be taller than the card ends up
    // rendered at (Layout.fillHeight cards, small windows). Without clip,
    // an overflowing row's sharp rectangular corners poke straight through
    // this Rectangle's own rounded corners — clip keeps overflow cleanly
    // cropped to the card's shape instead.
    clip: true
    color: elevated ? Theme.surfaceElevated : Theme.surface
    radius: Theme.radiusMd
    border.width: 1
    border.color: hovered && hoverable ? Theme.borderStrong : Theme.border
    implicitWidth: body.implicitWidth + pad * 2
    implicitHeight: body.implicitHeight + pad * 2

    property bool hovered: false
    scale: (hoverable && hovered && !Theme.reducedMotion) ? 1.01 : 1.0

    // Tilt angles, driven by cursor position; eased + reset on exit.
    property real tiltX: 0
    property real tiltY: 0
    transform: [
        Rotation {
            origin.x: card.width / 2
            origin.y: card.height / 2
            axis.x: 1; axis.y: 0; axis.z: 0
            angle: card.tiltX
        },
        Rotation {
            origin.x: card.width / 2
            origin.y: card.height / 2
            axis.x: 0; axis.y: 1; axis.z: 0
            angle: card.tiltY
        }
    ]

    Behavior on color { ColorAnimation { duration: Theme.durHover } }
    Behavior on border.color { ColorAnimation { duration: Theme.durHover } }
    Behavior on scale { NumberAnimation { duration: Theme.durHover; easing.type: Easing.OutCubic } }
    Behavior on tiltX { NumberAnimation { duration: Theme.durHover; easing.type: Easing.OutCubic } }
    Behavior on tiltY { NumberAnimation { duration: Theme.durHover; easing.type: Easing.OutCubic } }

    // Ledger direction: quiet, flat surfaces by default (a 1px border does
    // the separating), with a shadow appearing only as hover-lift feedback
    // on cards that are actually interactive — not as permanent ambient
    // weight under every static panel.
    layer.enabled: hoverable && hovered && !Theme.reducedMotion
    layer.effect: MultiEffect {
        shadowEnabled: true
        shadowColor: Theme.shadowColor
        shadowOpacity: Theme.shadowOpacity
        shadowBlur: 0.7
        shadowVerticalOffset: 4
    }

    Item {
        id: body
        anchors.fill: parent
        anchors.margins: card.pad
    }

    HoverHandler {
        id: hoverHandler
        enabled: card.hoverable
        onHoveredChanged: {
            card.hovered = hovered
            if (!hovered) { card.tiltX = 0; card.tiltY = 0 }
        }
        onPointChanged: {
            if (!card.tilt3d || Theme.reducedMotion || !hovered || card.width <= 0 || card.height <= 0)
                return
            var px = point.position.x / card.width - 0.5
            var py = point.position.y / card.height - 0.5
            card.tiltY = px * card.maxTilt * 2
            card.tiltX = -py * card.maxTilt * 2
        }
    }
}
