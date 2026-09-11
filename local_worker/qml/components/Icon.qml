import QtQuick
import QtQuick.Shapes
import "../theme"

// Vector icon set on QtQuick.Shapes — crisp, GPU-rasterized outlines instead
// of the old Canvas-rasterized bitmap glyphs (ProgressRing/SearchField
// already use Shapes successfully in this codebase; this follows the same
// proven pattern). Same name/tint/size public API as before, so existing
// call sites (NavButton, and the new ones added alongside this rewrite)
// don't need to change. All coordinates are fractions of width/height so
// icons stay crisp at any requested size, not just the original 20px grid.
Item {
    id: root

    property string name: ""
    property color tint: Theme.textSecondary
    property int size: 20

    width: size
    height: size

    readonly property real sw: Math.max(1.3, size * 0.09)
    readonly property real cx: width / 2
    readonly property real cy: height / 2

    // ── dashboard: 2x2 rounded squares ──
    Item {
        anchors.fill: parent
        visible: root.name === "dashboard"
        Repeater {
            model: [[3, 3], [12, 3], [3, 12], [12, 12]]
            Rectangle {
                required property var modelData
                x: (modelData[0] / 20) * root.width
                y: (modelData[1] / 20) * root.height
                width: (5 / 20) * root.width
                height: (5 / 20) * root.height
                radius: (1.5 / 20) * root.width
                color: "transparent"
                border.width: root.sw
                border.color: root.tint
            }
        }
    }

    // ── analyze: magnifying glass ──
    Shape {
        anchors.fill: parent
        visible: root.name === "analyze"
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            PathAngleArc { centerX: (9 / 20) * root.width; centerY: (9 / 20) * root.height; radiusX: (5.5 / 20) * root.width; radiusY: (5.5 / 20) * root.height; startAngle: 0; sweepAngle: 360 }
        }
        ShapePath {
            strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: (13.5 / 20) * root.width; startY: (13.5 / 20) * root.height
            PathLine { x: (17 / 20) * root.width; y: (17 / 20) * root.height }
        }
    }

    // ── results: document + 3 lines ──
    Item {
        anchors.fill: parent
        visible: root.name === "results"
        Rectangle {
            x: (4 / 20) * root.width; y: (3 / 20) * root.height
            width: (12 / 20) * root.width; height: (14 / 20) * root.height
            radius: (2 / 20) * root.width
            color: "transparent"; border.width: root.sw; border.color: root.tint
        }
        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
                startX: (7 / 20) * root.width; startY: (7 / 20) * root.height
                PathLine { x: (13 / 20) * root.width; y: (7 / 20) * root.height }
            }
            ShapePath {
                strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
                startX: (7 / 20) * root.width; startY: (10.5 / 20) * root.height
                PathLine { x: (14 / 20) * root.width; y: (10.5 / 20) * root.height }
            }
            ShapePath {
                strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
                startX: (7 / 20) * root.width; startY: (14 / 20) * root.height
                PathLine { x: (11 / 20) * root.width; y: (14 / 20) * root.height }
            }
        }
    }

    // ── compare: baseline + 3 bars ──
    Shape {
        anchors.fill: parent
        visible: root.name === "compare"
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: (3 / 20) * root.width; startY: (16.5 / 20) * root.height
            PathLine { x: (17 / 20) * root.width; y: (16.5 / 20) * root.height }
        }
        ShapePath {
            strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: (6 / 20) * root.width; startY: (16.5 / 20) * root.height
            PathLine { x: (6 / 20) * root.width; y: (9 / 20) * root.height }
        }
        ShapePath {
            strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: (10 / 20) * root.width; startY: (16.5 / 20) * root.height
            PathLine { x: (10 / 20) * root.width; y: (4 / 20) * root.height }
        }
        ShapePath {
            strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: (14 / 20) * root.width; startY: (16.5 / 20) * root.height
            PathLine { x: (14 / 20) * root.width; y: (11 / 20) * root.height }
        }
    }

    // ── history: clock face + hands ──
    Shape {
        anchors.fill: parent
        visible: root.name === "history"
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            PathAngleArc { centerX: root.cx; centerY: root.cy; radiusX: root.width * 0.35; radiusY: root.width * 0.35; startAngle: 0; sweepAngle: 360 }
        }
        ShapePath {
            strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: root.cx; startY: root.cy
            PathLine { x: (10 / 20) * root.width; y: (6 / 20) * root.height }
        }
        ShapePath {
            strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: root.cx; startY: root.cy
            PathLine { x: (13.5 / 20) * root.width; y: (12 / 20) * root.height }
        }
    }

    // ── templates: envelope ──
    Item {
        anchors.fill: parent
        visible: root.name === "templates"
        Rectangle {
            x: (3 / 20) * root.width; y: (5 / 20) * root.height
            width: (14 / 20) * root.width; height: (10 / 20) * root.height
            radius: (2 / 20) * root.width
            color: "transparent"; border.width: root.sw; border.color: root.tint
        }
        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"
                capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin
                startX: (4 / 20) * root.width; startY: (6 / 20) * root.height
                PathLine { x: (10 / 20) * root.width; y: (11 / 20) * root.height }
                PathLine { x: (16 / 20) * root.width; y: (6 / 20) * root.height }
            }
        }
    }

    // ── sync: partial-circle refresh arrows with arrowhead ticks ──
    Shape {
        anchors.fill: parent
        visible: root.name === "sync"
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            PathAngleArc { centerX: root.cx; centerY: root.cy; radiusX: root.width * 0.325; radiusY: root.width * 0.325; startAngle: 14.3; sweepAngle: 192.7 }
        }
        ShapePath {
            strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"
            capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin
            startX: (4 / 20) * root.width; startY: (12 / 20) * root.height
            PathLine { x: (2 / 20) * root.width; y: (12 / 20) * root.height }
            PathLine { x: (2 / 20) * root.width; y: (15 / 20) * root.height }
        }
        ShapePath {
            strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"
            capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin
            startX: (16 / 20) * root.width; startY: (8 / 20) * root.height
            PathLine { x: (18 / 20) * root.width; y: (8 / 20) * root.height }
            PathLine { x: (18 / 20) * root.width; y: (5 / 20) * root.height }
        }
    }

    // ── inbox: tray outline ──
    Shape {
        anchors.fill: parent
        visible: root.name === "inbox"
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"
            capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin
            startX: (3 / 20) * root.width; startY: (11 / 20) * root.height
            PathLine { x: (7 / 20) * root.width; y: (11 / 20) * root.height }
            PathLine { x: (8.5 / 20) * root.width; y: (14 / 20) * root.height }
            PathLine { x: (11.5 / 20) * root.width; y: (14 / 20) * root.height }
            PathLine { x: (13 / 20) * root.width; y: (11 / 20) * root.height }
            PathLine { x: (17 / 20) * root.width; y: (11 / 20) * root.height }
            PathLine { x: (15 / 20) * root.width; y: (4 / 20) * root.height }
            PathLine { x: (5 / 20) * root.width; y: (4 / 20) * root.height }
            PathLine { x: (3 / 20) * root.width; y: (11 / 20) * root.height }
        }
    }

    // ── settings: gear (circle + 8 spokes) ──
    Shape {
        anchors.fill: parent
        visible: root.name === "settings"
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            PathAngleArc { centerX: root.cx; centerY: root.cy; radiusX: root.width * 0.15; radiusY: root.width * 0.15; startAngle: 0; sweepAngle: 360 }
        }
        // 8 spokes at 45° increments. Repeater can't delegate ShapePath (it
        // requires Item-derived delegates), so these are written out plainly
        // using the 8 unit-circle directions at multiples of 45°.
        ShapePath { strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: root.cx + 1 * root.width * 0.30; startY: root.cy + 0 * root.width * 0.30
            PathLine { x: root.cx + 1 * root.width * 0.40; y: root.cy + 0 * root.width * 0.40 } }
        ShapePath { strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: root.cx + 0.7071 * root.width * 0.30; startY: root.cy + 0.7071 * root.width * 0.30
            PathLine { x: root.cx + 0.7071 * root.width * 0.40; y: root.cy + 0.7071 * root.width * 0.40 } }
        ShapePath { strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: root.cx + 0 * root.width * 0.30; startY: root.cy + 1 * root.width * 0.30
            PathLine { x: root.cx + 0 * root.width * 0.40; y: root.cy + 1 * root.width * 0.40 } }
        ShapePath { strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: root.cx - 0.7071 * root.width * 0.30; startY: root.cy + 0.7071 * root.width * 0.30
            PathLine { x: root.cx - 0.7071 * root.width * 0.40; y: root.cy + 0.7071 * root.width * 0.40 } }
        ShapePath { strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: root.cx - 1 * root.width * 0.30; startY: root.cy + 0 * root.width * 0.30
            PathLine { x: root.cx - 1 * root.width * 0.40; y: root.cy + 0 * root.width * 0.40 } }
        ShapePath { strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: root.cx - 0.7071 * root.width * 0.30; startY: root.cy - 0.7071 * root.width * 0.30
            PathLine { x: root.cx - 0.7071 * root.width * 0.40; y: root.cy - 0.7071 * root.width * 0.40 } }
        ShapePath { strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: root.cx + 0 * root.width * 0.30; startY: root.cy - 1 * root.width * 0.30
            PathLine { x: root.cx + 0 * root.width * 0.40; y: root.cy - 1 * root.width * 0.40 } }
        ShapePath { strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: root.cx + 0.7071 * root.width * 0.30; startY: root.cy - 0.7071 * root.width * 0.30
            PathLine { x: root.cx + 0.7071 * root.width * 0.40; y: root.cy - 0.7071 * root.width * 0.40 } }
    }

    // ── sun ──
    Shape {
        anchors.fill: parent
        visible: root.name === "sun"
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            PathAngleArc { centerX: root.cx; centerY: root.cy; radiusX: root.width * 0.22; radiusY: root.width * 0.22; startAngle: 0; sweepAngle: 360 }
        }
        ShapePath { strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: root.cx + 1 * root.width * 0.34; startY: root.cy + 0 * root.width * 0.34
            PathLine { x: root.cx + 1 * root.width * 0.46; y: root.cy + 0 * root.width * 0.46 } }
        ShapePath { strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: root.cx + 0.7071 * root.width * 0.34; startY: root.cy + 0.7071 * root.width * 0.34
            PathLine { x: root.cx + 0.7071 * root.width * 0.46; y: root.cy + 0.7071 * root.width * 0.46 } }
        ShapePath { strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: root.cx + 0 * root.width * 0.34; startY: root.cy + 1 * root.width * 0.34
            PathLine { x: root.cx + 0 * root.width * 0.46; y: root.cy + 1 * root.width * 0.46 } }
        ShapePath { strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: root.cx - 0.7071 * root.width * 0.34; startY: root.cy + 0.7071 * root.width * 0.34
            PathLine { x: root.cx - 0.7071 * root.width * 0.46; y: root.cy + 0.7071 * root.width * 0.46 } }
        ShapePath { strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: root.cx - 1 * root.width * 0.34; startY: root.cy + 0 * root.width * 0.34
            PathLine { x: root.cx - 1 * root.width * 0.46; y: root.cy + 0 * root.width * 0.46 } }
        ShapePath { strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: root.cx - 0.7071 * root.width * 0.34; startY: root.cy - 0.7071 * root.width * 0.34
            PathLine { x: root.cx - 0.7071 * root.width * 0.46; y: root.cy - 0.7071 * root.width * 0.46 } }
        ShapePath { strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: root.cx + 0 * root.width * 0.34; startY: root.cy - 1 * root.width * 0.34
            PathLine { x: root.cx + 0 * root.width * 0.46; y: root.cy - 1 * root.width * 0.46 } }
        ShapePath { strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: root.cx + 0.7071 * root.width * 0.34; startY: root.cy - 0.7071 * root.width * 0.34
            PathLine { x: root.cx + 0.7071 * root.width * 0.46; y: root.cy - 0.7071 * root.width * 0.46 } }
    }

    // ── moon: crescent outline (two arcs — outer disc bite, inner cut) ──
    Shape {
        anchors.fill: parent
        visible: root.name === "moon"
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"
            capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin
            startX: root.cx; startY: root.cy - root.width * 0.34
            PathArc {
                x: root.cx; y: root.cy + root.width * 0.34
                radiusX: root.width * 0.34; radiusY: root.width * 0.34
                useLargeArc: true; direction: PathArc.Clockwise
            }
            PathArc {
                x: root.cx; y: root.cy - root.width * 0.34
                radiusX: root.width * 0.27; radiusY: root.width * 0.27
                useLargeArc: true; direction: PathArc.Clockwise
            }
        }
    }

    // ── check ──
    Shape {
        anchors.fill: parent
        visible: root.name === "check"
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"
            capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin
            startX: root.width * 0.20; startY: root.height * 0.55
            PathLine { x: root.width * 0.42; y: root.height * 0.75 }
            PathLine { x: root.width * 0.80; y: root.height * 0.30 }
        }
    }

    // ── close (X) ──
    Shape {
        anchors.fill: parent
        visible: root.name === "close"
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: root.width * 0.25; startY: root.height * 0.25
            PathLine { x: root.width * 0.75; y: root.height * 0.75 }
        }
        ShapePath {
            strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: root.width * 0.75; startY: root.height * 0.25
            PathLine { x: root.width * 0.25; y: root.height * 0.75 }
        }
    }

    // ── fallback: plain circle ──
    Shape {
        anchors.fill: parent
        visible: root.name !== "" && ![
            "dashboard", "analyze", "results", "compare", "history",
            "templates", "sync", "inbox", "settings", "sun", "moon", "check", "close"
        ].includes(root.name)
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: root.tint; strokeWidth: root.sw; fillColor: "transparent"
            PathAngleArc { centerX: root.cx; centerY: root.cy; radiusX: root.width * 0.25; radiusY: root.width * 0.25; startAngle: 0; sweepAngle: 360 }
        }
    }
}
