import QtQuick
import QtQuick.Controls

Button {
    id: control

    property color fill: "#111827"
    property color fillHover: "#151b2e"
    property color fillPressed: "#0b1020"
    property color stroke: "#26314d"
    property color textColor: "#f8fbff"
    property bool strong: false
    property real radius: 12

    // Ripple effect properties
    property real rippleRadius: 0
    property real rippleOpacity: 0
    property point rippleCenter: Qt.point(0, 0)

    implicitHeight: 46
    implicitWidth: Math.max(132, contentItem.implicitWidth + 42)
    padding: 0
    hoverEnabled: true

    scale: down ? 0.965 : (hovered ? 1.018 : 1)

    Behavior on scale {
        NumberAnimation { duration: 150; easing.type: Easing.OutCubic }
    }

    // Ripple animation
    ParallelAnimation {
        id: rippleAnim
        NumberAnimation {
            target: control
            property: "rippleRadius"
            from: 0
            to: Math.max(control.width, control.height) * 1.5
            duration: 380
            easing.type: Easing.OutQuad
        }
        NumberAnimation {
            target: control
            property: "rippleOpacity"
            from: 0.36
            to: 0.0
            duration: 380
            easing.type: Easing.OutQuad
        }
    }

    contentItem: Text {
        text: control.text
        color: control.enabled ? control.textColor : "#65718a"
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
        border.color: control.enabled ? (control.hovered ? Qt.lighter(control.stroke, 1.2) : control.stroke) : "#243044"
        color: control.down ? control.fillPressed : (control.hovered ? control.fillHover : control.fill)
        opacity: control.hovered ? 0.96 : 1

        Behavior on opacity { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
        Behavior on color { ColorAnimation { duration: 150 } }
        Behavior on border.color { ColorAnimation { duration: 150 } }

        // Gradient overlay for strong style buttons
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            visible: control.strong
            opacity: control.hovered ? 0.52 : 0.38
            gradient: Gradient {
                GradientStop { position: 0; color: "#7c5cff" }
                GradientStop { position: 1; color: "#4d8dff" }
            }
            Behavior on opacity {
                NumberAnimation { duration: 150; easing.type: Easing.OutCubic }
            }
        }

        // Ripple Effect Canvas (clipped to rounded corners)
        Canvas {
            id: rippleCanvas
            anchors.fill: parent
            opacity: control.rippleOpacity
            visible: control.rippleOpacity > 0.001

            onPaint: {
                var ctx = getContext("2d")
                ctx.clearRect(0, 0, width, height)

                // Draw clip path for rounded corners
                var r = control.radius
                ctx.beginPath()
                ctx.moveTo(r, 0)
                ctx.lineTo(width - r, 0)
                ctx.arcTo(width, 0, width, r, r)
                ctx.lineTo(width, height - r)
                ctx.arcTo(width, height, width - r, height, r)
                ctx.lineTo(r, height)
                ctx.arcTo(0, height, 0, height - r, r)
                ctx.lineTo(0, r)
                ctx.arcTo(0, 0, r, 0, r)
                ctx.closePath()
                ctx.clip()

                // Draw ripple circle
                ctx.beginPath()
                ctx.arc(control.rippleCenter.x, control.rippleCenter.y, control.rippleRadius, 0, Math.PI * 2)
                ctx.fillStyle = (typeof root !== 'undefined' && !root.darkTheme && !control.strong) ?
                                "rgba(99, 102, 241, 0.22)" : "rgba(255, 255, 255, 0.42)"
                ctx.fill()
            }

            Connections {
                target: control
                function onRippleRadiusChanged() { rippleCanvas.requestPaint() }
            }
        }

        // Click event tracker for ripple coordinates
        MouseArea {
            anchors.fill: parent
            propagateComposedEvents: true
            hoverEnabled: false
            acceptedButtons: Qt.LeftButton

            onPressed: (mouse) => {
                if (typeof backend === 'undefined' || backend.motionEnabled) {
                    control.rippleCenter = Qt.point(mouse.x, mouse.y)
                    rippleAnim.stop()
                    control.rippleRadius = 0
                    control.rippleOpacity = 0.36
                    rippleAnim.start()
                }
                mouse.accepted = false // propagate to standard Button click handler
            }
        }
    }
}
