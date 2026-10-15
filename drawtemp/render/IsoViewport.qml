import QtQuick
import QtQuick.Window
import QtQuick.Shapes

// R3: sole scenegraph-backed terrain/actor/object viewport for R3, R5 and R12.
// All three clients inject the same Python RendererController and scene schema.
// Only input policy differs: pan/inspect, paint gestures, or tactical selection.
Item {
    id: root
    width: 960
    height: 640
    clip: true
    property string interactionMode: "pan"  // pan | edit | select
    property bool showGrid: true
    property bool showBlocked: false
    property bool showHeights: false
    property bool showActors: true
    // Default to all visible for Player/R3. R5 Studio supplies per-map policy.
    property var layerVisibility: ({})
    property var layerOpacity: ({})
    function layerEnabled(name) { return layerVisibility[name] !== false }
    function layerAlpha(name) {
        return layerOpacity[name] === undefined ? 1.0 : layerOpacity[name] / 100.0
    }
    property bool showLegend: interactionMode === "pan"
    property var hoveredCell: ({})
    // Editor-only, detached preview of brush footprint and adjacent blends.
    property var previewCells: []
    signal cellHovered(int x, int y)
    signal hoverLeft()
    readonly property var camera: renderer.cameraState
    signal strokeStarted(int x, int y)
    signal strokeMoved(int x, int y)
    signal strokeFinished(int x, int y)
    signal strokeCancelled()
    signal cellSelected(int x, int y)

    Rectangle {
        anchors.fill: parent
        color: "#1d2831"
        gradient: Gradient {
            GradientStop { position: 0; color: "#263c45" }
            GradientStop { position: 1; color: "#151e29" }
        }
    }

    // Projection, clipping, depth and atlas coordinates are supplied by R3.
    // Delegates use Qt Quick scene-graph nodes; never QML Canvas or CPU paint.
    Repeater {
        model: renderer.items
        delegate: Loader {
            id: renderDelegate
            required property var modelData
            property var row: modelData
            property real scaleFactor: root.camera.zoom
            property bool isTile: row.kind === "tile"
            property bool isActor: row.kind === "actor"
            visible: isActor ? (root.showActors && root.layerEnabled("Unités"))
                     : isTile ? true : root.layerEnabled("Objets")
            opacity: isActor ? root.layerAlpha("Unités")
                     : isTile ? 1.0 : root.layerAlpha("Objets")
            sourceComponent: isTile ? tileComponent : (isActor ? actorComponent : objectComponent)
            x: root.width / 2 + root.camera.panX + row.sx * scaleFactor
               - (isTile ? 48 : isActor ? 20 : 15) * scaleFactor
            y: root.height / 2 + root.camera.panY + row.sy * scaleFactor
               - (isTile ? 24 : isActor ? 68 : 40) * scaleFactor
            scale: scaleFactor
            transformOrigin: Item.TopLeft
            z: row.zOrder
        }
    }

    Component {
        id: tileComponent
        Item {
            property var tile: parent.row
            readonly property bool highlighted: tile.selected ||
                (root.hoveredCell.x === tile.x && root.hoveredCell.y === tile.y)
            width: 96
            height: 48
            Shape {
                anchors.fill: parent
                opacity: root.layerAlpha("Terrain")
                ShapePath {
                    strokeWidth: highlighted ? 2.5 : (root.showGrid ? 0.8 : 0)
                    strokeColor: highlighted ? "#ffda77" : "#283b3d"
                    fillColor: root.layerEnabled("Terrain") ? tile.color : "transparent"
                    startX: 48; startY: 0
                    PathLine { x: 96; y: 24 }
                    PathLine { x: 48; y: 48 }
                    PathLine { x: 0; y: 24 }
                    PathLine { x: 48; y: 0 }
                }
            }
            Image {
                anchors.fill: parent
                visible: renderer.atlasUrl !== "" && root.layerEnabled("Terrain")
                opacity: root.layerAlpha("Terrain")
                source: renderer.atlasUrl
                sourceClipRect: Qt.rect(tile.atlasX, 0, 96, 48)
                fillMode: Image.Stretch
                smooth: false
                asynchronous: false
            }
            // R5.4: GPU scenegraph polygons derived from the same canonical
            // AutoBlend rules for Studio and Player (no CPU Canvas fallback).
            Repeater {
                model: tile.blends || []
                delegate: Shape {
                    required property var modelData
                    anchors.fill: parent
                    opacity: root.layerEnabled("Terrain") ? root.layerAlpha("Terrain") : 0
                    ShapePath {
                        strokeWidth: 0
                        fillColor: modelData.color
                        startX: modelData.points[0][0]
                        startY: modelData.points[0][1]
                        PathLine { x: modelData.points[1][0]; y: modelData.points[1][1] }
                        PathLine { x: modelData.points[2][0]; y: modelData.points[2][1] }
                        PathLine { x: modelData.points[3][0]; y: modelData.points[3][1] }
                        PathLine { x: modelData.points[0][0]; y: modelData.points[0][1] }
                    }
                }
            }
            Shape {
                visible: highlighted || (tile.goal && root.layerEnabled("Objectifs"))
                opacity: highlighted ? 1.0 : root.layerAlpha("Objectifs")
                anchors.fill: parent
                ShapePath {
                    strokeWidth: highlighted ? 3 : 2
                    strokeColor: highlighted ? "#ffe080" : "#e7c770"
                    fillColor: highlighted ? "#22ffe080" : "transparent"
                    startX: 48; startY: 0
                    PathLine { x: 96; y: 24 }
                    PathLine { x: 48; y: 48 }
                    PathLine { x: 0; y: 24 }
                    PathLine { x: 48; y: 0 }
                }
            }
            Rectangle {
                visible: tile.feature === "tree" && root.layerEnabled("Décors")
                opacity: root.layerAlpha("Décors")
                width: 15; height: 36; x: 40; y: -22
                radius: 6; color: "#3c7452"
                border.color: "#b7c991"; border.width: 1
            }
            Rectangle {
                visible: tile.feature === "stone_wall" &&
                         root.layerEnabled("Décors") && root.layerEnabled("Bâtiments")
                opacity: Math.min(root.layerAlpha("Décors"), root.layerAlpha("Bâtiments"))
                width: 33; height: 20; x: 30; y: 0
                color: "#68737c"; border.color: "#bac0b9"
            }
            // Every paintable decor token has a visible map representation.
            // Dedicated R4 sprite bindings may later replace these lightweight
            // scenegraph shapes without changing the authored feature value.
            Item {
                visible: tile.feature !== "" && tile.feature !== "tree" &&
                         tile.feature !== "stone_wall" && root.layerEnabled("Décors")
                opacity: root.layerAlpha("Décors")
                x: 32; y: -3
                width: 34; height: 30
                Rectangle {
                    x: 3; y: 7; width: 28; height: 18
                    radius: tile.feature === "bush" ? 11 : 4
                    color: ["bush", "reeds"].indexOf(tile.feature) >= 0 ? "#537d53"
                         : ["boulder", "ruin", "pillar"].indexOf(tile.feature) >= 0 ? "#89938f"
                         : ["lantern", "crate"].indexOf(tile.feature) >= 0 ? "#9f774f"
                         : "#8a9187"
                    border.color: "#e0d1ab"
                    border.width: 1
                }
                Text {
                    anchors.centerIn: parent
                    text: tile.feature === "reeds" ? "≋" :
                          tile.feature === "lantern" ? "✦" :
                          tile.feature === "crate" ? "□" :
                          tile.feature === "stairs" ? "≡" :
                          tile.feature === "arch" ? "∩" :
                          tile.feature === "fence" ? "╫" :
                          tile.feature === "bush" ? "❀" :
                          tile.feature === "boulder" ? "◆" :
                          tile.feature === "pillar" ? "▥" : "▣"
                    color: "#f8ead0"; font.pixelSize: 15; font.bold: true
                }
            }
            Rectangle {
                visible: root.showBlocked && tile.blocked
                width: 11; height: 11; x: 43; y: 19; radius: 2
                color: "#cf655c"; border.color: "#f7d4af"
            }
            Rectangle {
                visible: tile.hazard > 0
                width: 10; height: 10; radius: 5; x: 43; y: 10
                color: "#e98649"
            }
            Rectangle {
                visible: tile.cover > 0
                width: 8; height: 8; x: 53; y: 23; radius: 2
                color: "#6aa68c"
            }
            Text {
                visible: root.showHeights && tile.height > 0
                text: tile.height
                x: 58; y: 6; color: "#fff2d5"
                font.bold: true; font.pixelSize: 12
            }
        }
    }

    Component {
        id: actorComponent
        Item {
            property var actor: parent.row
            width: 40; height: 68
            Rectangle {
                width: 34; height: 9; radius: 5
                x: 3; y: 58
                color: "#10191c"; opacity: 0.45
            }
            Rectangle {
                width: 28; height: 38; radius: 9
                x: 6; y: 19
                color: actor.alive ? (actor.team === "enemy" ? "#af6556" : "#496cbb") : "#777c85"
                border.width: 2; border.color: "#e2d7c4"
            }
            Rectangle {
                width: 19; height: 19; radius: 10
                x: 10; y: 5
                color: "#eacaa1"; border.color: "#62504b"
            }
            Text {
                text: actor.label || actor.id
                x: -30; y: -15
                width: 100; horizontalAlignment: Text.AlignHCenter
                color: "#fff3df"; font.pixelSize: 11
                style: Text.Outline; styleColor: "#1e2930"
            }
        }
    }

    Component {
        id: objectComponent
        Item {
            property var entry: parent.row
            width: 30; height: 40
            Rectangle {
                anchors.fill: parent
                radius: 5
                color: entry.label === "door" ? "#866445" :
                       entry.label === "marker" ? "#d5a35f" : "#6b807c"
                border.color: "#d0bd92"; border.width: 2
            }
            Text {
                anchors.centerIn: parent
                text: entry.label === "door" ? "P" :
                      entry.label === "switch" ? "L" :
                      entry.label === "marker" ? "!" : "•"
                color: "#faf0de"; font.bold: true
            }
        }
    }

    Rectangle {
        visible: root.showLegend
        height: 34; width: legend.implicitWidth + 28
        anchors { left: parent.left; top: parent.top; margins: 14 }
        radius: 7; color: "#aa121d2a"
        Text {
            id: legend
            anchors.centerIn: parent
            color: "#f7efd9"; font.pixelSize: 13
            text: "R3 · ISO " + Math.round(root.camera.zoom * 100) +
                  "%  |  Glisser : pan  •  Molette : zoom"
        }
    }

    // Preview overlays are non-interactive: the R3 camera/picking path remains
    // authoritative for both ghost stamps and actual commits.
    Repeater {
        model: root.previewCells
        delegate: Item {
            required property var modelData
            property var preview: modelData
            x: root.width/2 + root.camera.panX + preview.sx * root.camera.zoom
               - 48*root.camera.zoom
            y: root.height/2 + root.camera.panY + preview.sy * root.camera.zoom
               - 24*root.camera.zoom
            width: 96; height: 48
            scale: root.camera.zoom
            transformOrigin: Item.TopLeft
            z: 1000000
            Shape {
                anchors.fill: parent
                opacity: preview.painted ? 0.64 : 0.46
                ShapePath {
                    strokeWidth: preview.painted ? 2.5 : 1.5
                    strokeColor: preview.painted ? "#ffe294" : "#64c3c8"
                    fillColor: preview.painted ? preview.color : "transparent"
                    startX: 48; startY: 0
                    PathLine { x: 96; y: 24 }
                    PathLine { x: 48; y: 48 }
                    PathLine { x: 0; y: 24 }
                    PathLine { x: 48; y: 0 }
                }
            }
        }
    }

    MouseArea {
        id: pointer
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        property real lastX: 0
        property real lastY: 0
        property real downX: 0
        property real downY: 0
        property bool editing: false
        property var lastCell: ({})
        property string previewKey: ""

        function valid(cell) {
            return cell && cell.x !== undefined && cell.y !== undefined
        }
        onPressed: function(mouse) {
            lastX = mouse.x; lastY = mouse.y
            downX = mouse.x; downY = mouse.y
            editing = false
            if (mouse.button === Qt.LeftButton && root.interactionMode === "edit") {
                var cell = renderer.cellAt(mouse.x, mouse.y)
                if (valid(cell)) {
                    editing = true
                    lastCell = cell
                    root.strokeStarted(cell.x, cell.y)
                }
            }
        }
        onPositionChanged: function(mouse) {
            var cell = renderer.cellAt(mouse.x, mouse.y)
            root.hoveredCell = valid(cell) ? cell : ({})
            const key = valid(cell) ? cell.x + ":" + cell.y : ""
            if (key !== previewKey) {
                previewKey = key
                if (valid(cell)) root.cellHovered(cell.x, cell.y)
                else root.hoverLeft()
            }
            var panning = (mouse.buttons & Qt.RightButton) ||
                          (root.interactionMode !== "edit" && (mouse.buttons & Qt.LeftButton))
            if (panning) {
                renderer.panBy(mouse.x - lastX, mouse.y - lastY)
            } else if (editing && (mouse.buttons & Qt.LeftButton) && valid(cell) &&
                       (!valid(lastCell) || cell.x !== lastCell.x || cell.y !== lastCell.y)) {
                lastCell = cell
                root.strokeMoved(cell.x, cell.y)
            }
            lastX = mouse.x; lastY = mouse.y
        }
        onReleased: function(mouse) {
            if (mouse.button === Qt.LeftButton && editing) {
                var cell = renderer.cellAt(mouse.x, mouse.y)
                if (!valid(cell)) cell = lastCell
                if (valid(cell)) root.strokeFinished(cell.x, cell.y)
                editing = false
            } else if (mouse.button === Qt.LeftButton &&
                       Math.abs(mouse.x - downX) + Math.abs(mouse.y - downY) < 6) {
                var picked = renderer.cellAt(mouse.x, mouse.y)
                if (valid(picked) && root.interactionMode === "select")
                    root.cellSelected(picked.x, picked.y)
                else if (root.interactionMode === "pan")
                    renderer.pickAt(mouse.x, mouse.y)
            }
        }
        onCanceled: {
            if (editing) root.strokeCancelled()
            editing = false
        }
        onExited: {
            root.hoveredCell = ({})
            previewKey = ""
            root.hoverLeft()
        }
        onWheel: function(wheel) {
            renderer.zoomAt(wheel.angleDelta.y, wheel.x, wheel.y)
            wheel.accepted = true
        }
    }

    onWidthChanged: renderer.resizeViewport(width, height)
    onHeightChanged: renderer.resizeViewport(width, height)
    Component.onCompleted: renderer.resizeViewport(width, height)
}
