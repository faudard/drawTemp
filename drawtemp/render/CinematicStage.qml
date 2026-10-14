import QtQuick

// R11: Studio and Player instantiate this exact scene from a common frame.
Rectangle {
    id: scene
    width: 960
    height: 540
    clip: true
    color: frame.background || "#101a2b"
    property var frame: cinematic.frame

    Rectangle {
        anchors.fill: parent
        color: "#18283b"
        opacity: 0.28
    }
    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: parent.height * 0.28
        color: "#283f45"
        opacity: 0.65
    }

    Item {
        id: sceneActors
        anchors.fill: parent
        x: {
            var effects = scene.frame.effects || []
            for (var i=0; i<effects.length; i++) {
                if (effects[i].kind === "camera_shake")
                    return Math.sin((scene.frame.timeMs + effects[i].seed) / 23) * 5 * effects[i].power
            }
            return 0
        }
        Repeater {
            model: scene.frame.actors || []
            delegate: Item {
                required property var modelData
                x: scene.width * (0.5 + (modelData.x - 0.5 - scene.frame.cameraX) * scene.frame.zoom)
                y: scene.height * (0.5 + (modelData.y - 0.5 - scene.frame.cameraY) * scene.frame.zoom)
                width: 100; height: 120
                transform: Translate { x: -50; y: -84 }
                Image {
                    id: sprite
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: parent.bottom
                    width: 92; height: 104
                    source: modelData.image
                    visible: status === Image.Ready
                    fillMode: Image.PreserveAspectFit
                    smooth: false
                }
                Rectangle {
                    visible: !sprite.visible
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: parent.bottom
                    width: 46; height: 70
                    radius: 20
                    color: "#cfab83"
                    border.color: "#f3ddb5"
                    border.width: 2
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.top: parent.bottom
                    text: modelData.name
                    color: "#f6eedb"
                    font.pixelSize: 14
                    font.bold: true
                }
            }
        }
    }

    // Seed/time anchored procedural presentation: seeking gives the same image.
    Repeater {
        model: scene.frame.effects || []
        delegate: Item {
            required property var modelData
            x: scene.width * modelData.x
            y: scene.height * modelData.y
            width: scene.width
            height: scene.height
            Repeater {
                model: (modelData.kind === "rain" || modelData.kind === "smoke" ||
                        modelData.kind === "fire" || modelData.kind === "fog") ? 24 : 1
                delegate: Rectangle {
                    required property int index
                    property real offset: (index * 0.6180339 + modelData.seed * 0.007) % 1
                    property real elapsed: scene.frame.timeMs * (modelData.kind === "rain" ? 0.0007 : 0.00012)
                    x: (offset * scene.width + (modelData.kind === "smoke" ? elapsed * 50 : 0)) % scene.width - scene.width * modelData.x
                    y: ((index * 0.381966 + elapsed + modelData.seed * 0.011) % 1) * scene.height - scene.height * modelData.y
                    width: modelData.kind === "rain" ? 2 : modelData.kind === "fog" ? 120 : 8
                    height: modelData.kind === "rain" ? 25 : modelData.kind === "fog" ? 46 : 14
                    radius: width / 2
                    color: modelData.kind === "fire" ? "#ff8d36" :
                           modelData.kind === "rain" ? "#a4d3f5" :
                           modelData.kind === "light" ? "#fff2ae" : "#a1a7ae"
                    opacity: modelData.power * (modelData.kind === "fog" ? 0.11 : 0.5)
                }
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        visible: scene.frame.transition !== ""
        color: "#101a2b"
        opacity: scene.frame.transitionOpacity || 0
    }
    Rectangle {
        anchors.fill: parent
        color: scene.frame.fadeColor || "#000000"
        opacity: scene.frame.fadeOpacity || 0
    }
    Text {
        text: scene.frame.shot || ""
        visible: text !== ""
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: 18
        color: "#d6e0e8"
        font.pixelSize: 12
    }

    Rectangle {
        id: dialogueBox
        visible: (scene.frame.speaker || "") !== ""
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 22
        height: 150
        radius: 12
        color: "#e80c1c30"
        border.color: "#c8a781"
        border.width: 2
        Image {
            id: portrait
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.margins: 12
            width: visible ? 108 : 0
            source: scene.frame.portrait || ""
            fillMode: Image.PreserveAspectFit
            visible: status === Image.Ready
        }
        Column {
            anchors.left: portrait.visible ? portrait.right : parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.margins: 16
            spacing: 10
            Text {
                text: (scene.frame.speaker || "") + (scene.frame.expression === "neutral" ?
                      "" : " · " + scene.frame.expression)
                color: "#f3cb92"
                font.pixelSize: 21
                font.bold: true
            }
            Text {
                text: scene.frame.dialogue || ""
                color: "#f4f4f1"
                font.pixelSize: 20
                wrapMode: Text.WordWrap
                width: parent.width
            }
        }
    }
}
