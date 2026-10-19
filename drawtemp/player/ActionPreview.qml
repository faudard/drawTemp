import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "../render"

// R26 experimental top-down Player composition. It is intentionally opt-in.
// The scene delegates and camera come from the common R3 RendererController,
// while GameSession SceneRouter integration and production GPU parity remain gates.
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
        // The timer only polls input and wall-clock. Python's R26 fixed-step
        // accumulator emits exactly 60 logical ticks per elapsed second,
        // independent of this timer's refresh frequency or GPU frame rate.
        interval: 8
        repeat: true
        running: !root.smokeMode && !root.actionData.paused && root.actionData.hero.alive
        onTriggered: {
            var dx = (root.right ? 1 : 0) - (root.left ? 1 : 0)
            var dy = (root.down ? 1 : 0) - (root.up ? 1 : 0)
            action.pulse(dx, dy, root.attackHeld, root.dodgeQueued,
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

            TopDownViewport {
                id: sharedViewport
                anchors.fill: parent
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
