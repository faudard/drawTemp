import QtQuick

// Shared R3 renderer rows + top-down projection. No scene-specific gameplay.
// Both this view and IsoViewport consume RendererController.items; all picking,
// camera transforms and tile culling stay in drawtemp.render.
Item {
    id: viewport
    clip: true
    readonly property var camera: renderer.cameraState
    readonly property bool topDown: renderer.projectionMode === "top_down"
    readonly property bool sideView: renderer.projectionMode === "side"
    readonly property bool flatView: topDown || sideView

    onWidthChanged: if (width > 0 && height > 0) renderer.resizeViewport(width, height)
    onHeightChanged: if (width > 0 && height > 0) renderer.resizeViewport(width, height)
    Component.onCompleted: if (width > 0 && height > 0)
                               renderer.resizeViewport(width, height)

    Rectangle { anchors.fill: parent; color: "#192c29"; z: -300000 }

    // R52.A: shared decorative pass, always behind interactive terrain.
    Repeater {
        model: renderer.depthLayers
        delegate: Rectangle {
            required property var modelData
            readonly property var layer: modelData
            readonly property real zoom: viewport.camera.zoom
            visible: viewport.flatView
            width: layer.width * zoom
            height: layer.height * zoom
            x: viewport.width / 2 + (viewport.camera.panX + layer.sx * zoom) * layer.parallax - width / 2
            y: viewport.height / 2 + (viewport.camera.panY + layer.sy * zoom) * layer.parallax - height / 2
            z: -200000 + layer.depthIndex
            color: layer.color
            opacity: layer.opacity
        }
    }

    // R52.B1: ambient tint overlays the scene graph, never the picking model.
    // This Rectangle has no pointer handlers or direct Gameplay bindings.
    Rectangle {
        anchors.fill: parent
        z: 90000
        readonly property var tint: renderer.lightingOverlay
        color: tint.color
        opacity: tint.opacity
        visible: opacity > 0
    }
    Timer {
        interval: 50
        repeat: true
        running: renderer.lightingAnimating
        onTriggered: renderer.advanceLighting(interval)
    }

    Repeater {
        model: renderer.items
        delegate: Item {
            id: projected
            required property var modelData
            property var row: modelData
            readonly property bool tile: row.kind === "tile"
            readonly property bool actor: row.kind === "actor"
            readonly property bool object: row.kind === "object"
            readonly property real unit: viewport.camera.zoom
            readonly property real extentX: tile ? 64 : actor ? 40 : 30
            readonly property real extentY: viewport.sideView && tile ? 24 : extentX
            x: viewport.width / 2 + viewport.camera.panX + row.sx * unit - extentX * unit / 2
            y: viewport.height / 2 + viewport.camera.panY + row.sy * unit - extentY * unit / 2
            width: extentX * unit
            height: extentY * unit
            z: row.zOrder
            visible: viewport.flatView && (tile || actor || object)

            // Cosmetic side-on ledge; no gameplay collision or pointer handler.
            Rectangle {
                visible: projected.tile && viewport.sideView && row.height > 0
                x: 0
                // Inset visual lip stays inside pickable 64x24 tile bounds.
                width: projected.width
                height: Math.min(8, Math.max(0, row.height) * 4) * projected.unit
                y: projected.height - height
                color: "#34424a"
                z: 1
            }

            Rectangle {
                anchors.fill: parent
                visible: projected.tile
                color: row.color
                border.width: 1
                border.color: row.selected ? "#ffe195" : "#4d7161"
                Rectangle {
                    anchors.fill: parent
                    anchors.margins: 3 * projected.unit
                    visible: row.blocked
                    radius: 5 * projected.unit
                    color: "#667a76"
                    border.color: "#8b9993"
                    border.width: 2
                }
            }
            Rectangle {
                anchors.fill: parent
                visible: projected.tile && row.lightShade !== undefined
                color: "#07121b"
                opacity: row.lightShade === undefined ? 0 : row.lightShade
            }
            Rectangle {
                anchors.fill: parent
                visible: projected.actor && !(spriteLoader.item &&
                                               spriteLoader.item.status === Image.Ready)
                radius: width / 2
                color: row.alive ? (row.team === "player" ? "#f1ca75" : "#d06561")
                                 : "#685558"
                opacity: row.alive ? 1 : .35
                border.color: row.combatState === "dodge" ? "#ffffff"
                            : row.combatState === "attack" ? "#ffdf8d" : "#3d4643"
                border.width: 3 * projected.unit
                Text {
                    anchors.centerIn: parent
                    color: "#2a3433"
                    font.bold: true
                    font.pixelSize: Math.max(10, 20 * projected.unit)
                    text: row.team === "player" ? "★" : "●"
                }
            }
            // R36.C1: the exact same R4/R3 PNG atlas crop contract used by
            // IsoViewport. The animation frame comes from committed ticks.
            // Keep the old silhouette when art is missing or decoder fails.
            // Do not create an Image texture loader for every terrain tile.
            // Only actor delegates that have validated R28 art instantiate it.
            Loader {
                id: spriteLoader
                active: projected.actor && !!row.imageUrl
                sourceComponent: Component {
                    Image {
                        readonly property real spriteScale: Math.min(
                            1.5, 64 / Math.max(1, row.frameWidth || 0, row.frameHeight || 0))
                        source: row.imageUrl
                        sourceClipRect: Qt.rect(row.atlasX, row.atlasY,
                                                row.frameWidth, row.frameHeight)
                        width: row.frameWidth * projected.unit * spriteScale
                        height: row.frameHeight * projected.unit * spriteScale
                        x: projected.width / 2 - row.pivotX * projected.unit * spriteScale
                        y: projected.height / 2 - row.pivotY * projected.unit * spriteScale
                        fillMode: Image.Stretch
                        smooth: false
                        asynchronous: false
                        cache: true
                    }
                }
            }
            // Pose label stays visible whether the actor has artwork or not.
            Text {
                visible: projected.actor && !!row.animationState
                anchors.horizontalCenter: parent.horizontalCenter
                y: projected.height + 2 * projected.unit
                text: row.animationState || ""
                color: "#fff4cf"
                font.pixelSize: Math.max(8, 10 * projected.unit)
            }
            Rectangle {
                anchors.fill: parent
                visible: projected.object
                radius: (row.label === "door" ? 3 : 7) * projected.unit
                color: row.open ? "#718c7f" : row.label === "door" ? "#a66f4d"
                            : row.label === "chest" ? "#c49b4c" : "#e5d18c"
                opacity: row.open ? .5 : 1
                border.color: "#f4dfaf"
                border.width: 2 * projected.unit
            }
        }
    }

    // The R3 renderer alone performs picking/camera unprojection.
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton
        onClicked: function(event) { renderer.pickAt(event.x, event.y) }
        onWheel: function(wheel) {
            renderer.zoomAt(wheel.angleDelta.y, wheel.x, wheel.y)
            wheel.accepted = true
        }
    }
}
