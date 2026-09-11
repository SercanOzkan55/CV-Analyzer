pragma Singleton
import QtQuick

// Typographic scale tokens. Keeps font sizing/weight consistent across the app
// instead of scattering magic pixel sizes. Bundles two variable fonts (Sora
// for display/headings, IBM Plex Sans for body/UI text) so the "Vivid"
// identity doesn't depend on whatever sans the OS happens to ship — falls
// back to the platform default only if a font file fails to load.
QtObject {
    id: typography

    property FontLoader displayLoader: FontLoader { source: "../../assets/fonts/Sora-Variable.ttf" }
    property FontLoader bodyLoader: FontLoader { source: "../../assets/fonts/IBMPlexSans-Variable.ttf" }

    readonly property string displayFamily: displayLoader.status === FontLoader.Ready ? displayLoader.name : Qt.application.font.family
    readonly property string family: bodyLoader.status === FontLoader.Ready ? bodyLoader.name : Qt.application.font.family

    // Sizes
    readonly property int displaySize: 28
    readonly property int titleSize: 22
    readonly property int headingSize: 17
    readonly property int subheadingSize: 15
    readonly property int bodySize: 14
    readonly property int labelSize: 13
    readonly property int captionSize: 12
    readonly property int microSize: 11

    // Weights
    readonly property int weightRegular: Font.Normal
    readonly property int weightMedium: Font.Medium
    readonly property int weightSemiBold: Font.DemiBold
    readonly property int weightBold: Font.Bold
    readonly property int weightBlack: Font.Black

    // Line-height helpers (multipliers)
    readonly property real lineTight: 1.15
    readonly property real lineNormal: 1.35
    readonly property real lineRelaxed: 1.5
}
