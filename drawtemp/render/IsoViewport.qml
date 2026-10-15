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
    // Optional Studio layer policy; Player defaults to all layers visible.
    property var layerVisibility: ({})
    property var layerOpacity: ({})
    function layerEnabled(name) { return layerVisibility[name] !== false }
    function layerAlpha(name) {
        return layerOpacity[name] === undefined ? 1.0 : layerOpacity[name] / 100.0
    }
    // Player-only presentation: briefly conceal the static actor while its
    // committed move / attack clip is displayed. Studio defaults to none.
    property var concealedActorIds: []
    property var activeVisualClip: ({})
    property real activeVisualPhase: 1

    function actorMotion(row) {
        if (row.kind !== "actor" || !activeVisualClip ||
            row.id !== activeVisualClip.actor)
            return ({})
        return renderer.motionPoint(activeVisualClip, activeVisualPhase)
    }
    property bool showLegend: interactionMode === "pan"
    property var hoveredCell: ({})
    readonly property var camera: renderer.cameraState
    signal strokeStarted(int x, int y)
    signal strokeMoved(int x, int y)
    signal strokeFinished(int x, int y)
    signal strokeCancelled()
    signal cellSelected(int x, int y)

    Rectangle {
        anchors.fill: parent
        // Must be below chunk textures (z=-1) and all dynamic scene layers.
        z: -100000
        color: "#1d2831"
        gradient: Gradient {
            GradientStop { position: 0; color: "#263c45" }
            GradientStop { position: 1; color: "#151e29" }
        }
    }

    // Independent visual clock: no CT, tactical RNG or save state is changed.
    Timer {
        interval: 125
        repeat: true
        running: renderer.animatedAssets && root.showActors
        onTriggered: renderer.advanceVisual(125)
    }

    // R3.D: one QSG texture node per static 8x8 terrain chunk instead of
    // a Shape/Image/ShapePath hierarchy for every simple cell. Terrain with
    // relief, props, walls or hazards retains its original QML node pipeline.
    // Qt Quick uploads composited QImages through the single image provider.
    Repeater {
        model: root.showGrid && renderer.textureBatching ? renderer.tileBatches : []
        delegate: Image {
            required property var modelData
            readonly property real ratio: root.camera.zoom
            x: root.width / 2 + root.camera.panX + modelData.sx * ratio
            y: root.height / 2 + root.camera.panY + modelData.sy * ratio
            width: modelData.width * ratio
            height: modelData.height * ratio
            source: modelData.url
            fillMode: Image.Stretch
            smooth: false
            asynchronous: false
            cache: false  // Let the bounded provider own CPU images, not QML cache.
            z: -1
        }
    }

    // Projection, clipping, depth and atlas coordinates are supplied by R3.
    // Delegates use Qt Quick scene-graph nodes; never QML Canvas or CPU paint.
    Repeater {
        model: root.showGrid && renderer.textureBatching
            ? renderer.displayItems : renderer.items
        delegate: Loader {
            id: renderDelegate
            required property var modelData
            property var row: modelData
            property real scaleFactor: root.camera.zoom
            property bool isTile: row.kind === "tile"
            property bool isActor: row.kind === "actor"
            property bool isBuilding: row.kind === "building"
            readonly property var motion: isActor ? root.actorMotion(row) : ({})
            readonly property real renderSX: motion.sx !== undefined ? motion.sx : row.sx
            readonly property real renderSY: motion.sy !== undefined ? motion.sy : row.sy
            visible: isBuilding ? root.layerEnabled("Bâtiments")
                     : isActor
                     ? (root.showActors && root.layerEnabled("Unités") &&
                        root.concealedActorIds.indexOf(row.id) < 0)
                     : isTile ? true : root.layerEnabled("Objets")
            opacity: isBuilding ? root.layerAlpha("Bâtiments")
                     : isActor ? root.layerAlpha("Unités")
                     : isTile ? 1.0 : root.layerAlpha("Objets")
            sourceComponent: isTile ? tileComponent :
                (isActor ? actorComponent : (isBuilding ? buildingComponent : objectComponent))
            x: root.width / 2 + root.camera.panX + renderSX * scaleFactor
               - (isTile ? 48 : isActor ? (row.imageUrl ? row.pivotX : 20) :
                  isBuilding ? 0 : 15) * scaleFactor
            y: root.height / 2 + root.camera.panY + renderSY * scaleFactor
               - (isTile ? 24 : isActor ? (row.imageUrl ? row.pivotY : 68) :
                  isBuilding ? 0 : 40) * scaleFactor
            scale: scaleFactor
            transformOrigin: Item.TopLeft
            // Render moving actors at their interpolated feet depth.
            z: isActor && motion.worldX !== undefined ?
                (motion.worldX + motion.worldY) * 100 + 60 : row.zOrder
        }
    }

    // Hover stays interactive even when its static ground tile is batched.
    Item {
        id: batchHover
        readonly property var cell: root.hoveredCell
        readonly property real ratio: root.camera.zoom
        visible: root.showGrid && renderer.textureBatching &&
                 cell.x !== undefined && cell.y !== undefined &&
                 renderer.isBatchedCell(cell.x, cell.y)
        x: root.width/2 + root.camera.panX + (cell.x - cell.y) * 48 * ratio - 48 * ratio
        y: root.height/2 + root.camera.panY + (cell.x + cell.y) * 24 * ratio - 24 * ratio
        width: 96 * ratio
        height: 48 * ratio
        z: (cell.x + cell.y) * 100 + 5
        Shape {
            anchors.fill: parent
            ShapePath {
                strokeWidth: 2
                strokeColor: "#ffe080"
                fillColor: "#22ffe080"
                startX: batchHover.width / 2
                startY: 0
                PathLine { x: batchHover.width; y: batchHover.height / 2 }
                PathLine { x: batchHover.width / 2; y: batchHover.height }
                PathLine { x: 0; y: batchHover.height / 2 }
                PathLine { x: batchHover.width / 2; y: 0 }
            }
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
            // Exposed relief only when an adjacent height is lower.
            Shape {
                visible: tile.eastDrop > 0
                anchors.fill: parent
                ShapePath {
                    strokeWidth: 0.8
                    strokeColor: "#39444a"
                    fillColor: "#716f62"
                    startX: 96; startY: 24
                    PathLine { x: 48; y: 48 }
                    PathLine { x: 48; y: 48 + tile.eastDrop * 12 }
                    PathLine { x: 96; y: 24 + tile.eastDrop * 12 }
                    PathLine { x: 96; y: 24 }
                }
            }
            Shape {
                visible: tile.southDrop > 0
                anchors.fill: parent
                ShapePath {
                    strokeWidth: 0.8
                    strokeColor: "#37444a"
                    fillColor: "#8c8573"
                    startX: 48; startY: 48
                    PathLine { x: 0; y: 24 }
                    PathLine { x: 0; y: 24 + tile.southDrop * 12 }
                    PathLine { x: 48; y: 48 + tile.southDrop * 12 }
                    PathLine { x: 48; y: 48 }
                }
            }
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
            // Transient overlays never mutate tactical or authored data.
            Shape {
                visible: tile.overlay !== ""
                opacity: 0.24
                anchors.fill: parent
                ShapePath {
                    strokeWidth: 0
                    fillColor: tile.overlayColor
                    startX: 48; startY: 0
                    PathLine { x: 96; y: 24 }
                    PathLine { x: 48; y: 48 }
                    PathLine { x: 0; y: 24 }
                    PathLine { x: 48; y: 0 }
                }
            }
            Shape {
                visible: tile.overlay !== ""
                anchors.fill: parent
                ShapePath {
                    strokeWidth: 2.5
                    strokeColor: tile.overlayColor
                    fillColor: "transparent"
                    startX: 48; startY: 0
                    PathLine { x: 96; y: 24 }
                    PathLine { x: 48; y: 48 }
                    PathLine { x: 0; y: 24 }
                    PathLine { x: 48; y: 0 }
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

    // The same projected polygons are used for drawing and surface picking.
    // A roof is omitted by the renderer when a living unit enters the house.
    Component {
        id: buildingComponent
        Item {
            property var structure: parent.row
            width: structure.spanX
            height: structure.spanY
            Shape {
                anchors.fill: parent
                ShapePath {
                    strokeWidth: structure.part === "roof" ? 1.6 : 0.8
                    strokeColor: structure.part === "roof" ? "#efcf9d" : "#5d514d"
                    fillColor: structure.color
                    startX: structure.points[0][0]
                    startY: structure.points[0][1]
                    PathLine { x: structure.points[1][0]; y: structure.points[1][1] }
                    PathLine { x: structure.points[2][0]; y: structure.points[2][1] }
                    PathLine { x: structure.points[3][0]; y: structure.points[3][1] }
                    PathLine { x: structure.points[0][0]; y: structure.points[0][1] }
                }
            }
        }
    }

    Component {
        id: actorComponent
        Item {
            property var actor: parent.row
            readonly property bool hasArt: !!actor.imageUrl
            width: hasArt ? actor.frameWidth : 40
            height: hasArt ? actor.frameHeight : 68
            Image {
                id: resolvedSprite
                visible: parent.hasArt && status !== Image.Error
                width: parent.width
                height: parent.height
                source: parent.hasArt ? actor.imageUrl : ""
                sourceClipRect: parent.hasArt
                    ? Qt.rect(actor.atlasX, actor.atlasY, actor.frameWidth, actor.frameHeight)
                    : Qt.rect(0, 0, 0, 0)
                fillMode: Image.Stretch
                smooth: false
                asynchronous: false
                cache: true
            }
            Rectangle {
                visible: !parent.hasArt || resolvedSprite.status === Image.Error
                width: 34; height: 9; radius: 5
                x: 3; y: 58
                color: "#10191c"; opacity: 0.45
            }
            Rectangle {
                visible: !parent.hasArt || resolvedSprite.status === Image.Error
                width: 28; height: 38; radius: 9
                x: 6; y: 19
                color: actor.alive ? (actor.team === "enemy" ? "#af6556" : "#496cbb") : "#777c85"
                border.width: 2; border.color: "#e2d7c4"
            }
            Rectangle {
                visible: !parent.hasArt || resolvedSprite.status === Image.Error
                width: 19; height: 19; radius: 10
                x: 10; y: 5
                color: "#eacaa1"; border.color: "#62504b"
            }
            Rectangle {
                visible: root.activeVisualClip.actor === actor.id &&
                         root.activeVisualClip.kind === "attack"
                x: parent.width * 0.70; y: parent.height * 0.28
                width: 28; height: 4; rotation: -30 + 70 * root.activeVisualPhase
                radius: 1
                color: "#f2e4b6"
            }
            Text {
                text: actor.label || actor.id
                x: (parent.width - 100) / 2; y: -15
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
        onExited: root.hoveredCell = ({})
        onWheel: function(wheel) {
            renderer.zoomAt(wheel.angleDelta.y, wheel.x, wheel.y)
            wheel.accepted = true
        }
    }

    onWidthChanged: renderer.resizeViewport(width, height)
    onHeightChanged: renderer.resizeViewport(width, height)
    Component.onCompleted: renderer.resizeViewport(width, height)
}
