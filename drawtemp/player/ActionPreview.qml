import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

// R26 experimental top-down Player composition. It is intentionally opt-in.
// The R25 shared projection contract must replace this preview presentation
// before claiming Studio/Player rendering parity or production release.
ApplicationWindow {
    id: root
    property bool smokeMode: false
    visible: !smokeMode
    width: 1000
    height: 730
    minimumWidth: 720
    minimumHeight: 520
    title: "DrawTemp — Action Adventure (R26 preview)"
    color: "#101c22"
    property var actionData: action.view

    property bool up: false
    property bool down: false
    property bool left: false
    property bool right: false
    property bool attackHeld: false
    property bool dodgeQueued: false
    property bool guardHeld: false
    property bool interactQueued: false

    Connections {
        target: action
        function onStateChanged() { root.actionData = action.view }
    }

    Timer {
        id: tickClock
        interval: 16
        repeat: true
        running: !root.smokeMode && !root.actionData.paused && root.actionData.hero.alive
        onTriggered: {
            var dx = (root.right ? 1 : 0) - (root.left ? 1 : 0)
            var dy = (root.down ? 1 : 0) - (root.up ? 1 : 0)
            action.tick(dx, dy, root.attackHeld, root.dodgeQueued,
                        root.guardHeld, root.interactQueued)
            root.dodgeQueued = false
            root.interactQueued = false
        }
    }

    Rectangle {
        anchors.fill: parent
        color: "#101c22"
    }

    Item {
        id: keyboard
        anchors.fill: parent
        focus: true
        Keys.onPressed: function(event) {
            if (event.isAutoRepeat) return
            if (event.key === Qt.Key_Up || event.key === Qt.Key_Z || event.key === Qt.Key_W)
                root.up = true
            else if (event.key === Qt.Key_Down || event.key === Qt.Key_S)
                root.down = true
            else if (event.key === Qt.Key_Left || event.key === Qt.Key_Q || event.key === Qt.Key_A)
                root.left = true
            else if (event.key === Qt.Key_Right || event.key === Qt.Key_D)
                root.right = true
            else if (event.key === Qt.Key_Space)
                root.attackHeld = true
            else if (event.key === Qt.Key_Shift)
                root.dodgeQueued = true
            else if (event.key === Qt.Key_Control)
                root.guardHeld = true
            else if (event.key === Qt.Key_E)
                root.interactQueued = true
            else if (event.key === Qt.Key_P)
                action.pause()
            else if (event.key === Qt.Key_F5)
                action.save()
            else if (event.key === Qt.Key_F9)
                action.load()
            else if (event.key === Qt.Key_R)
                action.respawn()
            else
                return
            event.accepted = true
        }
        Keys.onReleased: function(event) {
            if (event.isAutoRepeat) return
            if (event.key === Qt.Key_Up || event.key === Qt.Key_Z || event.key === Qt.Key_W)
                root.up = false
            else if (event.key === Qt.Key_Down || event.key === Qt.Key_S)
                root.down = false
            else if (event.key === Qt.Key_Left || event.key === Qt.Key_Q || event.key === Qt.Key_A)
                root.left = false
            else if (event.key === Qt.Key_Right || event.key === Qt.Key_D)
                root.right = false
            else if (event.key === Qt.Key_Space)
                root.attackHeld = false
            else if (event.key === Qt.Key_Control)
                root.guardHeld = false
            else return
            event.accepted = true
        }

        Rectangle {
            id: viewportFrame
            anchors.fill: parent
            anchors.margins: 20
            anchors.bottomMargin: 128
            color: "#223831"
            radius: 14
            clip: true
            border.width: 2
            border.color: "#658572"

            Item {
                id: world
                anchors.fill: parent
                property real tileSize: Math.max(32, Math.min(width / 8, height / 7))
                property real offsetX: width / 2 - root.actionData.hero.pos[0] / 1000 * tileSize
                property real offsetY: height / 2 - root.actionData.hero.pos[1] / 1000 * tileSize

                Repeater {
                    model: root.actionData.width * root.actionData.height
                    delegate: Rectangle {
                        property int tileX: index % root.actionData.width
                        property int tileY: Math.floor(index / root.actionData.width)
                        x: world.offsetX + tileX * world.tileSize
                        y: world.offsetY + tileY * world.tileSize
                        width: world.tileSize
                        height: world.tileSize
                        color: (tileX + tileY) % 2 === 0 ? "#385648" : "#3d5d4d"
                        border.width: 1
                        border.color: "#496b59"
                    }
                }
                Repeater {
                    model: root.actionData.walls
                    delegate: Rectangle {
                        x: world.offsetX + modelData[0] * world.tileSize
                        y: world.offsetY + modelData[1] * world.tileSize
                        width: world.tileSize
                        height: world.tileSize
                        radius: 6
                        color: "#687675"
                        border.color: "#899592"
                        border.width: 3
                    }
                }
                Repeater {
                    model: root.actionData.items
                    delegate: Rectangle {
                        property var obj: modelData
                        property bool opened: root.actionData.objects[obj.id].opened
                        x: world.offsetX + (obj.pos[0] + .2) * world.tileSize
                        y: world.offsetY + (obj.pos[1] + .2) * world.tileSize
                        width: world.tileSize * .6
                        height: world.tileSize * .6
                        radius: obj.kind === "chest" ? 4 : 10
                        color: obj.kind === "door" ? (opened ? "#477c72" : "#965f47")
                              : obj.kind === "chest" ? (opened ? "#59624e" : "#b88b41")
                              : "#e0c782"
                        border.color: opened ? "#849584" : "#ebd3a0"
                        border.width: 2
                        opacity: opened ? .55 : 1.0
                    }
                }
                Repeater {
                    model: Object.keys(root.actionData.enemies).sort()
                    delegate: Rectangle {
                        property var enemy: root.actionData.enemies[modelData]
                        x: world.offsetX + enemy.pos[0] / 1000 * world.tileSize - width / 2
                        y: world.offsetY + enemy.pos[1] / 1000 * world.tileSize - height / 2
                        width: world.tileSize * .52
                        height: world.tileSize * .52
                        radius: width / 2
                        color: enemy.hp > 0 ? "#c65c56" : "#524e50"
                        opacity: enemy.hp > 0 ? 1 : .3
                        border.color: enemy.state === "attack" ? "#ffe28e" : "#8c3434"
                        border.width: 2
                    }
                }
                Rectangle {
                    id: heroMark
                    x: world.offsetX + root.actionData.hero.pos[0] / 1000 * world.tileSize - width / 2
                    y: world.offsetY + root.actionData.hero.pos[1] / 1000 * world.tileSize - height / 2
                    width: world.tileSize * .55
                    height: width
                    radius: width / 2
                    color: root.actionData.hero.alive ? "#efcc72" : "#765757"
                    border.width: 3
                    border.color: root.actionData.hero.invulnerable > 0 ? "#ffffff" : "#4b4035"
                    Text {
                        anchors.centerIn: parent
                        text: "★"
                        color: "#403d32"
                        font.pixelSize: parent.width / 2
                    }
                }
            }
            Rectangle {
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.margins: 14
                radius: 7
                width: hud.implicitWidth + 22
                height: hud.implicitHeight + 14
                color: "#b0112020"
                Text {
                    id: hud
                    anchors.centerIn: parent
                    text: "PV " + root.actionData.hero.hp + "/" + root.actionData.hero.max_hp
                        + "     Endurance " + root.actionData.hero.stamina
                        + "     Tick " + root.actionData.tick
                    color: "#fff4dd"
                    font.pixelSize: 17
                    font.bold: true
                }
            }
            Rectangle {
                anchors.centerIn: parent
                width: 320
                height: 96
                radius: 10
                color: "#dd12191b"
                visible: root.actionData.paused || !root.actionData.hero.alive
                Text {
                    anchors.centerIn: parent
                    text: !root.actionData.hero.alive ? "Défaite — R pour réapparaître" : "PAUSE — P pour reprendre"
                    font.pixelSize: 19
                    color: "#fff4dd"
                }
            }
        }

        ColumnLayout {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: 22
            spacing: 8
            Text {
                color: "#f5ebd1"
                font.pixelSize: 17
                text: root.actionData.prompt ? "E — Interagir : " + root.actionData.prompt : root.actionData.message
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }
            Text {
                color: "#a9c5bc"
                text: "ZQSD / WASD / flèches : bouger   |   Espace : attaquer   |   Maj : esquiver   |   Ctrl : parer   |   E : interagir"
                font.pixelSize: 13
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }
            Text {
                color: "#a9c5bc"
                text: "P : pause    F5 : sauvegarde action    F9 : recharger    R : réapparaître    Inventaire : "
                      + JSON.stringify(root.actionData.inventory)
                font.pixelSize: 13
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }
        }
    }
}
