import QtQuick
import QtQuick.Window
import QtQuick.Shapes

Item {
    id: root
    width: 960
    height: 640
    clip: true
    readonly property var camera: renderer.cameraState

    Rectangle {
        anchors.fill: parent
        color: "#1d2831"
        gradient: Gradient {
            GradientStop { position: 0; color: "#263c45" }
            GradientStop { position: 1; color: "#151e29" }
        }
    }

    // Source coordinates and depth order come from the shared Python scene model.
    // Delegates are QSG-backed Shape/Image/Rectangle nodes, not Canvas painting.
    Repeater {
        model: renderer.items
        delegate: Loader {
            id: renderDelegate
            required property var modelData
            property var row: modelData
            property real scaleFactor: root.camera.zoom
            property bool isTile: row.kind === "tile"
            property bool isActor: row.kind === "actor"
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
            width: 96
            height: 48
            Shape {
                anchors.fill: parent
                ShapePath {
                    strokeWidth: tile.selected ? 2 : 0.5
                    strokeColor: tile.selected ? "#ffda77" : tile.color
                    fillColor: tile.color
                    startX: 48; startY: 0
                    PathLine { x: 96; y: 24 }
                    PathLine { x: 48; y: 48 }
                    PathLine { x: 0; y: 24 }
                    PathLine { x: 48; y: 0 }
                }
            }
            Image {
                anchors.fill: parent
                visible: renderer.atlasUrl !== ""
                source: renderer.atlasUrl
                sourceClipRect: Qt.rect(tile.atlasX, 0, 96, 48)
                fillMode: Image.Stretch
                smooth: false
                asynchronous: false
            }
            Shape {
                visible: tile.selected
                anchors.fill: parent
                ShapePath {
                    strokeWidth: 3
                    strokeColor: "#ffe080"
                    fillColor: "transparent"
                    startX: 48; startY: 0
                    PathLine { x: 96; y: 24 }
                    PathLine { x: 48; y: 48 }
                    PathLine { x: 0; y: 24 }
                    PathLine { x: 48; y: 0 }
                }
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
                color: actor.alive ? (actor.team === "player" ? "#496cbb" : "#af6556") : "#777c85"
                border.width: 2
                border.color: "#e2d7c4"
            }
            Rectangle {
                width: 19; height: 19; radius: 10
                x: 10; y: 5
                color: "#eacaa1"
                border.color: "#62504b"
            }
            Text {
                text: actor.id
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
                color: entry.label === "door" ? "#866445" : "#6b807c"
                border.color: "#d0bd92"; border.width: 2
            }
            Text {
                anchors.centerIn: parent
                text: entry.label === "door" ? "P" : entry.label === "switch" ? "L" : "•"
                color: "#faf0de"; font.bold: true
            }
        }
    }

    Rectangle {
        height: 34; width: legend.implicitWidth + 28
        anchors { left: parent.left; top: parent.top; margins: 14 }
        radius: 7; color: "#aa121d2a"
        Text {
            id: legend
            anchors.centerIn: parent
            color: "#f7efd9"; font.pixelSize: 13
            text: "Jeanne d'Arc • " + Math.round(root.camera.zoom * 100) + "%  |  Glisser : déplacer  •  Molette : zoom"
        }
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        property real lastX: 0
        property real lastY: 0
        property real downX: 0
        property real downY: 0
        onPressed: function(mouse) {
            lastX = mouse.x; lastY = mouse.y
            downX = mouse.x; downY = mouse.y
        }
        onPositionChanged: function(mouse) {
            if (mouse.buttons !== Qt.NoButton) {
                renderer.panBy(mouse.x - lastX, mouse.y - lastY)
                lastX = mouse.x; lastY = mouse.y
            }
        }
        onReleased: function(mouse) {
            if (Math.abs(mouse.x - downX) + Math.abs(mouse.y - downY) < 6)
                renderer.pickAt(mouse.x, mouse.y)
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
