import QtQuick

// Shared R3 renderer rows + top-down projection. No scene-specific gameplay.
// Both this view and IsoViewport consume RendererController.items; all picking,
// camera transforms and tile culling stay in drawtemp.render.
Item {
    id: viewport
    clip: true
    readonly property var camera: renderer.cameraState
    readonly property bool topDown: renderer.projectionMode === "top_down"

    onWidthChanged: if (width > 0 && height > 0) renderer.resizeViewport(width, height)
    onHeightChanged: if (width > 0 && height > 0) renderer.resizeViewport(width, height)
    Component.onCompleted: if (width > 0 && height > 0)
                               renderer.resizeViewport(width, height)

    Rectangle { anchors.fill: parent; color: "#192c29" }

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
            readonly property real side: tile ? 64 : actor ? 40 : 30
            x: viewport.width / 2 + viewport.camera.panX + row.sx * unit - side * unit / 2
            y: viewport.height / 2 + viewport.camera.panY + row.sy * unit - side * unit / 2
            width: side * unit
            height: side * unit
            z: row.zOrder
            visible: viewport.topDown && (tile || actor || object)

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
                visible: projected.actor && !(actorImage.status === Image.Ready
                                               && !!row.imageUrl)
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
                // R36.B3: semantic pose comes from a committed-tick
                // animation binding; R28 sprite loading is still opt-in.
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.top: parent.bottom
                    text: row.animationState || ""
                    visible: text.length > 0
                    color: "#fff4cf"
                    font.pixelSize: Math.max(8, 10 * projected.unit)
                }
            }
            // R36.C1: the exact same R4/R3 PNG atlas crop contract used by
            // IsoViewport. The animation frame comes from committed ticks.
            // Keep the old silhouette when art is missing or decoder fails.
            Image {
                id: actorImage
                readonly property bool hasSprite: projected.actor && !!row.imageUrl
                readonly property real spriteScale: Math.min(
                    1.5, 64 / Math.max(1, row.frameWidth || 0, row.frameHeight || 0))
                visible: hasSprite && status === Image.Ready
                source: hasSprite ? row.imageUrl : ""
                sourceClipRect: hasSprite
                    ? Qt.rect(row.atlasX, row.atlasY,
                              row.frameWidth, row.frameHeight)
                    : Qt.rect(0, 0, 0, 0)
                width: hasSprite ? row.frameWidth * projected.unit * spriteScale : 0
                height: hasSprite ? row.frameHeight * projected.unit * spriteScale : 0
                x: projected.width / 2 - (row.pivotX || 0)
                     * projected.unit * spriteScale
                y: projected.height / 2 - (row.pivotY || 0)
                     * projected.unit * spriteScale
                fillMode: Image.Stretch
                smooth: false
                asynchronous: false
                cache: true
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
