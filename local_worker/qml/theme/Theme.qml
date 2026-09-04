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

    // ── "Ledger" palette ──────────────────────────────────────────────
    // Cool paper neutrals + a single deep-teal accent (in place of the
    // earlier purple/blue/cyan trio). Category tints (see AnalyzePage.qml's
    // categoryTint()) now come from ONE hue family at different values
    // (primary/secondary/accent below) rather than three unrelated hues —
    // distinguishable by lightness, not by competing colors. success/
    // warning/danger stay semantic and deliberately don't share the accent
    // hue. Dark mode is its own considered variant (this app defaults to
    // dark), not an inversion of the light one.

    // ── Surfaces ──
    readonly property color background: darkMode ? "#10181A" : "#F5F6F8"
    readonly property color sidebar: darkMode ? "#0C1213" : "#EFF1F3"
    readonly property color surface: darkMode ? "#161D1F" : "#FFFFFF"
    readonly property color surfaceElevated: darkMode ? "#1C2426" : "#FFFFFF"
    readonly property color surfaceMuted: darkMode ? "#10181A" : "#EEF0F3"
    readonly property color overlay: darkMode ? "#05090A" : "#1A2027"

    // ── Text ──
    readonly property color textPrimary: darkMode ? "#EDF1F1" : "#1A2027"
    readonly property color textSecondary: darkMode ? "#A9B4B4" : "#3C4450"
    readonly property color textMuted: darkMode ? "#6F7B7B" : "#6B7480"
    readonly property color textInverse: darkMode ? "#0E1516" : "#FFFFFF"

    // ── Borders ──
    readonly property color border: darkMode ? "#253133" : "#DEE2E8"
    readonly property color borderStrong: darkMode ? "#34474A" : "#C7CDD5"

    // ── Brand / accents (one teal family; brighter in dark mode for
    // contrast against a dark ground, deeper in light mode) ──
    readonly property color primary: darkMode ? "#2DBBAB" : "#0F766E"
    readonly property color primaryHover: darkMode ? "#45CCBC" : "#14877D"
    readonly property color primarySoft: darkMode ? "#10302C" : "#E3F3F1"
    readonly property color secondary: darkMode ? "#5FAFA5" : "#4C978F"
    readonly property color accent: darkMode ? "#8ECFC4" : "#7BAEA6"
    readonly property color success: darkMode ? "#3FB86A" : "#2F9E52"
    readonly property color warning: darkMode ? "#E0A23A" : "#C8850F"
    readonly property color danger: darkMode ? "#E36259" : "#C6403A"
    readonly property color info: darkMode ? "#5A93B0" : "#3B6E8F"

    // ── Semantic soft fills (for badges/states) ──
    readonly property color successSoft: darkMode ? "#133021" : "#E3F5E9"
    readonly property color warningSoft: darkMode ? "#332508" : "#FBEED9"
    readonly property color dangerSoft: darkMode ? "#34140F" : "#FBE7E5"

    // ── Elevation (shadow strength; light mode leans on thin borders more
    // than shadow, per Ledger's flatter, quieter feel) ──
    readonly property real shadowOpacity: darkMode ? 0.45 : 0.10
    readonly property color shadowColor: darkMode ? "#000000" : "#1A2027"

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
