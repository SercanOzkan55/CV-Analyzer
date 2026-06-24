pragma Singleton
import QtQuick
import QtCore

// Central design-token singleton. All components read semantic colors from
// here instead of hardcoding them, so light/dark/system themes stay
// consistent. Backend-agnostic: identical whether the app is backed by
// PySide6 (current) or a C++ QObject layer later.
QtObject {
    id: theme

    // "light" | "dark" | "system"
    property string mode: "dark"

    readonly property bool systemDark: Application.styleHints.colorScheme === Qt.Dark
    readonly property bool darkMode: mode === "dark" || (mode === "system" && systemDark)

    // Persist the user's choice across launches.
    property Settings _settings: Settings {
        category: "appearance"
        property alias mode: theme.mode
    }

    function toggle() {
        mode = darkMode ? "light" : "dark"
    }

    // ── Surfaces ──
    readonly property color background: darkMode ? "#080D1C" : "#F4F7FC"
    readonly property color sidebar: darkMode ? "#070B17" : "#FFFFFF"
    readonly property color surface: darkMode ? "#11182B" : "#FFFFFF"
    readonly property color surfaceElevated: darkMode ? "#172039" : "#F8FAFD"
    readonly property color surfaceMuted: darkMode ? "#0D1425" : "#EEF2F8"
    readonly property color overlay: darkMode ? "#040711" : "#1F2733"

    // ── Text ──
    readonly property color textPrimary: darkMode ? "#F7F9FF" : "#101828"
    readonly property color textSecondary: darkMode ? "#A8B5D1" : "#5E6B85"
    readonly property color textMuted: darkMode ? "#74809C" : "#8994A8"
    readonly property color textInverse: darkMode ? "#0A1020" : "#FFFFFF"

    // ── Borders ──
    readonly property color border: darkMode ? "#26314D" : "#DCE3EE"
    readonly property color borderStrong: darkMode ? "#384564" : "#C8D1E0"

    // ── Brand / accents (constant across themes for identity) ──
    readonly property color primary: "#7657F6"
    readonly property color primaryHover: "#866CFF"
    readonly property color primarySoft: darkMode ? "#1B1740" : "#ECE9FF"
    readonly property color secondary: "#38A9FF"
    readonly property color accent: "#22D3EE"
    readonly property color success: "#2DD48A"
    readonly property color warning: "#FFBD4A"
    readonly property color danger: "#FF667A"
    readonly property color info: "#49A8FF"

    // ── Semantic soft fills (for badges/states) ──
    readonly property color successSoft: darkMode ? "#0F2E22" : "#E2F8EE"
    readonly property color warningSoft: darkMode ? "#33260C" : "#FFF3DC"
    readonly property color dangerSoft: darkMode ? "#33121A" : "#FFE5E9"

    // ── Elevation (shadow strength) ──
    readonly property real shadowOpacity: darkMode ? 0.45 : 0.16
    readonly property color shadowColor: darkMode ? "#000000" : "#4A5A75"

    // ── Motion ──
    property bool reducedMotion: false
    readonly property int durMicro: reducedMotion ? 0 : 130
    readonly property int durHover: reducedMotion ? 0 : 170
    readonly property int durPage: reducedMotion ? 0 : 280
    readonly property int durSidebar: reducedMotion ? 0 : 250
    readonly property int durDialog: reducedMotion ? 0 : 210
    readonly property int durData: reducedMotion ? 0 : 720

    // ── Shape ──
    readonly property int radiusSm: 8
    readonly property int radiusMd: 12
    readonly property int radiusLg: 16
    readonly property int radiusXl: 22

    // ── Spacing scale ──
    readonly property int space1: 4
    readonly property int space2: 8
    readonly property int space3: 12
    readonly property int space4: 16
    readonly property int space5: 24
    readonly property int space6: 32
}
