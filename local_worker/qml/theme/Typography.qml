pragma Singleton
import QtQuick

// Typographic scale tokens. Keeps font sizing/weight consistent across the app
// instead of scattering magic pixel sizes. Family falls back to the platform
// default sans (Qt no longer ships fonts) so it looks native on each OS.
QtObject {
    readonly property string family: Qt.application.font.family

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
