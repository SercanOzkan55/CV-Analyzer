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
        property alias acrylicEnabled: theme.acrylicEnabled
    }

    function toggle() {
        mode = darkMode ? "light" : "dark"
    }

    // ── "Vivid" palette ───────────────────────────────────────────────
    // Replaces the earlier muted "Ledger" teal-on-cool-paper look: a near-
    // black graphite ground (not teal-tinted) in dark mode, opaque
    // high-contrast panels instead of quiet flat ones, and a saturated
    // teal→cyan signature pair used deliberately (CTAs, the active nav
    // item, progress rings) rather than spread thin everywhere. Dark mode
    // is the primary, considered variant; light swaps to deeper/richer
    // versions of the same hues for contrast on a bright ground, not a
    // flat inversion.

    // ── Surfaces ──
    readonly property color background: darkMode ? "#0A0D0F" : "#F7F9FA"
    readonly property color sidebar: darkMode ? "#0E1214" : "#EEF1F2"
    readonly property color surface: darkMode ? "#12171A" : "#FFFFFF"
    readonly property color surfaceElevated: darkMode ? "#161C1F" : "#FFFFFF"
    readonly property color surfaceMuted: darkMode ? "#0E1315" : "#EEF1F2"
    readonly property color overlay: darkMode ? "#05070A" : "#1A2024"

    // ── Text ──
    readonly property color textPrimary: darkMode ? "#F3F7F7" : "#10151A"
    readonly property color textSecondary: darkMode ? "#93A3A8" : "#48565C"
    readonly property color textMuted: darkMode ? "#819196" : "#5C6870"
    readonly property color textInverse: darkMode ? "#00251E" : "#FFFFFF"

    // ── Borders ──
    readonly property color border: darkMode ? "#212A2E" : "#DCE2E5"
    readonly property color borderStrong: darkMode ? "#2C383D" : "#C5CDD1"

    // ── Brand / accents (vivid teal + a blue partner for the signature
    // gradient, plus a third cyan tone for a distinguishable 4th category
    // tint; saturated in dark mode for a glow-capable pop, deepened for
    // legibility in light mode rather than reused verbatim) ──
    readonly property color primary: darkMode ? "#00E5C0" : "#007A5E"
    readonly property color primaryHover: darkMode ? "#33F0D6" : "#006B55"
    readonly property color primarySoft: darkMode ? "#0F2C27" : "#DFF5EF"
    readonly property color secondary: darkMode ? "#17A3E8" : "#09689F"
    readonly property color accent: darkMode ? "#2DD4BF" : "#0EA394"
    readonly property color success: darkMode ? "#22C55E" : "#1D9A4C"
    readonly property color warning: darkMode ? "#F5A524" : "#B4790A"
    readonly property color danger: darkMode ? "#F0453C" : "#D6362B"
    readonly property color info: darkMode ? "#17A3E8" : "#2563A8"

    // ── Semantic soft fills (for badges/states) ──
    readonly property color successSoft: darkMode ? "#0F2B1B" : "#E1F6E8"
    readonly property color warningSoft: darkMode ? "#332305" : "#FBEED9"
    readonly property color dangerSoft: darkMode ? "#33110E" : "#FBE7E5"

    // ── Elevation (4-level depth scale. Each level pairs an opacity + blur
    // + vertical offset, feeding a MultiEffect drop shadow. Dark-mode
    // shadows run deeper/more pronounced than the old muted theme — depth
    // is meant to read at a glance, not just appear on close inspection —
    // while light mode stays comparatively restrained since a bright
    // ground already reads as "raised" with much less shadow needed.) ──
    readonly property color shadowColor: darkMode ? "#00120D" : "#0F2B28"

    readonly property real elevFlatOpacity: 0
    readonly property real elevFlatBlur: 0
    readonly property int elevFlatYOffset: 0

    readonly property real elevCardOpacity: darkMode ? 0.40 : 0.10
    readonly property real elevCardBlur: 0.6
    readonly property int elevCardYOffset: 4

    readonly property real elevRaisedOpacity: darkMode ? 0.55 : 0.16
    readonly property real elevRaisedBlur: 0.8
    readonly property int elevRaisedYOffset: 9

    readonly property real elevModalOpacity: darkMode ? 0.68 : 0.24
    readonly property real elevModalBlur: 1.0
    readonly property int elevModalYOffset: 18

    // ── Signature glow (colored shadow reserved for genuinely interactive/
    // active elements — primary CTAs and the active nav item — so it reads
    // as a deliberate accent rather than ambient noise under every panel) ──
    readonly property color glowColor: primary
    readonly property real glowOpacityHover: darkMode ? 0.38 : 0.20
    readonly property real glowOpacityActive: darkMode ? 0.55 : 0.28
    readonly property real glowBlur: 0.9

    // ── Chrome / acrylic-lite (translucent layered surfaces for sidebar,
    // header, popups — a soft "frosted glass" read built from the existing
    // surfaceElevated/border tones at alpha, not a real blur-behind, which
    // is unproven for live-scrolling content in this app; see
    // `acrylicEnabled` below for the isolated, opt-in true-blur path) ──
    readonly property color chromeFill: Qt.rgba(surfaceElevated.r, surfaceElevated.g, surfaceElevated.b, darkMode ? 0.86 : 0.9)
    readonly property color chromeBorder: Qt.rgba(border.r, border.g, border.b, darkMode ? 0.7 : 0.75)

    // Gates an optional real blur-behind effect on the sidebar only (off by
    // default — live GPU blur of scrolling page content is unproven in this
    // app; verify smoothness on real hardware before ever defaulting this on).
    property bool acrylicEnabled: false

    // ── Signature accent gradient (for primary CTAs, the active-nav pill,
    // high-score progress rings, avatar). Teal→blue — the one deliberately
    // bold, spent-in-one-place move; everything else around it stays quiet. ──
    readonly property color primaryGradientStart: primary
    readonly property color primaryGradientEnd: secondary

    // ── Motion ──
    property bool reducedMotion: false
    readonly property int durMicro: reducedMotion ? 0 : 130
    readonly property int durHover: reducedMotion ? 0 : 170
    readonly property int durPage: reducedMotion ? 0 : 280
    readonly property int durSidebar: reducedMotion ? 0 : 250
    readonly property int durDialog: reducedMotion ? 0 : 210
    readonly property int durData: reducedMotion ? 0 : 720

    // ── Shape (tighter than the previous rounder "Ledger" scale — a
    // deliberately more engineered, less soft-glass edge) ──
    readonly property int radiusSm: 7
    readonly property int radiusMd: 10
    readonly property int radiusLg: 14
    readonly property int radiusXl: 18

    // ── Spacing scale ──
    readonly property int space1: 4
    readonly property int space2: 8
    readonly property int space3: 12
    readonly property int space4: 16
    readonly property int space5: 24
    readonly property int space6: 32
}
