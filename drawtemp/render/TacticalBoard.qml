import QtQuick

// R12 keeps its public board API for Main.qml, but delegates ALL drawing,
// pan/zoom and terrain hit testing to R3's shared IsoViewport scenegraph.
// PlayerBridge supplies the canonical Simulation scene to renderer.
IsoViewport {
    id: board
    property var battle: ({})
    property var exploration: ({})
    property var selected: [0, 0]
    readonly property real zoom: renderer.cameraState.zoom
    interactionMode: "select"
    showLegend: false
}
