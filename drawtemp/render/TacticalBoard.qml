import QtQuick
import QtQuick.Shapes

// R12 adds an overlay on the exact R3 isometric projection. R3 still owns
// terrain, actors, camera, zoom and hit-testing; no second tile renderer.
IsoViewport {
    id: board
    property var battle: ({})
    property var exploration: ({})
    property var selected: [0, 0]
    property var tactical: ({})
    property bool showTacticalOverlay: true
    readonly property real zoom: renderer.cameraState.zoom
    interactionMode: "select"
    showLegend: false

    Repeater {
        model: board.showTacticalOverlay && board.tactical && board.tactical.markers ?
                   board.tactical.markers : []
        delegate: Item {
            id: highlight
            required property var modelData
            readonly property real ratio: renderer.cameraState.zoom
            readonly property int cellX: modelData.x
            readonly property int cellY: modelData.y
            width: 96 * ratio
            height: 48 * ratio
            x: board.width / 2 + renderer.cameraState.panX +
               (cellX - cellY) * 48 * ratio - 48 * ratio
            y: board.height / 2 + renderer.cameraState.panY +
               ((cellX + cellY) * 24 - (modelData.height || 0) * 12) * ratio -
               24 * ratio
            z: (cellX + cellY) * 100 + 12
            visible: x + width > 0 && y + height > 0 &&
                     x < board.width && y < board.height

            readonly property color tint:
                modelData.kind === "hazard" ? "#df6e44" :
                modelData.kind === "prepared" ? "#dc636b" :
                modelData.kind === "cast" ? "#b678d6" :
                modelData.kind === "charge" ? "#ebbb63" : "#6fcdbd"
            Shape {
                anchors.fill: parent
                ShapePath {
                    strokeColor: highlight.tint
                    strokeWidth: Math.max(1, 2 * highlight.ratio)
                    // Unknown enemy charges remain dashed/low-opacity overlays.
                    strokeStyle: highlight.modelData.certainty === "possible" ?
                                     ShapePath.DashLine : ShapePath.SolidLine
                    fillColor: highlight.modelData.kind === "reachable" ?
                                   "#186fcdbd" : "#32da6e44"
                    startX: highlight.width / 2; startY: 0
                    PathLine { x: highlight.width; y: highlight.height / 2 }
                    PathLine { x: highlight.width / 2; y: highlight.height }
                    PathLine { x: 0; y: highlight.height / 2 }
                    PathLine { x: highlight.width / 2; y: 0 }
                }
            }
        }
    }
}
