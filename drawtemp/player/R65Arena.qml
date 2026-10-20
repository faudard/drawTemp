import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "../render"

// R65.C opt-in prototype. R3 TopDownViewport renders canonical R65 world.
// GPU frame frequency never becomes an input to the fixed 60 Hz simulation.
ApplicationWindow {
    id: root
    property bool smokeMode: false
    visible: !smokeMode
    width: 1060
    height: 750
    minimumWidth: 780
    minimumHeight: 580
    color: "#111b21"
    title: "DrawTemp — R65.C Action Arena (prototype)"

    property var state: arena.view
    property bool north: false
    property bool south: false
    property bool west: false
    property bool east: false
    property bool strike: false
    property bool shooting: false
    property bool guarding: false
    property bool dodgeEdge: false
    property bool parryEdge: false
    property bool reducedMotion: false

    readonly property bool runningCombat: state.hero.alive && !state.victory &&
                                            !state.paused
    function clearInput() {
        north = south = west = east = false
        strike = shooting = guarding = false
        dodgeEdge = parryEdge = false
    }
    Connections {
        target: arena
        function onStateChanged() { root.state = arena.view }
    }
    Timer {
        interval: 8
        repeat: true
        running: !root.smokeMode && root.runningCombat
        onTriggered: {
            const dx = (root.east ? 1 : 0) - (root.west ? 1 : 0)
            const dy = (root.south ? 1 : 0) - (root.north ? 1 : 0)
            arena.pulse(dx, dy, root.strike, root.dodgeEdge, root.guarding,
                        false, root.shooting, root.parryEdge)
            root.dodgeEdge = false
            root.parryEdge = false
        }
    }

    Item {
        anchors.fill: parent
        focus: true
        Keys.onPressed: function(event) {
            if (event.isAutoRepeat) return
            if (event.key === Qt.Key_Z || event.key === Qt.Key_W || event.key === Qt.Key_Up)
                north = true
            else if (event.key === Qt.Key_S || event.key === Qt.Key_Down)
                south = true
            else if (event.key === Qt.Key_Q || event.key === Qt.Key_A || event.key === Qt.Key_Left)
                west = true
            else if (event.key === Qt.Key_D || event.key === Qt.Key_Right)
                east = true
            else if (event.key === Qt.Key_Space) strike = true
            else if (event.key === Qt.Key_F) shooting = true
            else if (event.key === Qt.Key_Control) guarding = true
            else if (event.key === Qt.Key_Shift) dodgeEdge = true
            else if (event.key === Qt.Key_C) parryEdge = true
            else if (event.key === Qt.Key_M) reducedMotion = !reducedMotion
            else if (event.key === Qt.Key_P) { arena.pause(); clearInput() }
            else if (event.key === Qt.Key_F5) arena.save()
            else if (event.key === Qt.Key_F9) { arena.load(); clearInput() }
            else if (event.key === Qt.Key_R && !root.state.hero.alive) {
                arena.restart()
                clearInput()
            } else return
            event.accepted = true
        }
        Keys.onReleased: function(event) {
            if (event.isAutoRepeat) return
            if (event.key === Qt.Key_Z || event.key === Qt.Key_W || event.key === Qt.Key_Up)
                north = false
            else if (event.key === Qt.Key_S || event.key === Qt.Key_Down)
                south = false
            else if (event.key === Qt.Key_Q || event.key === Qt.Key_A || event.key === Qt.Key_Left)
                west = false
            else if (event.key === Qt.Key_D || event.key === Qt.Key_Right)
                east = false
            else if (event.key === Qt.Key_Space) strike = false
            else if (event.key === Qt.Key_F) shooting = false
            else if (event.key === Qt.Key_Control) guarding = false
            else return
            event.accepted = true
        }

        Rectangle {
            id: viewportPanel
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: footer.top
            anchors.margins: 16
            color: "#293b36"
            radius: 10
            border.color: "#577d72"
            border.width: 2
            clip: true

            TopDownViewport {
                anchors.fill: parent
            }

            // Lightweight event-free projectile indicators, on the same R3
            // camera projection as world actors; omitted in reduced motion.
            Item {
                id: projectileLayer
                anchors.fill: parent
                visible: !root.reducedMotion
                Repeater {
                    model: root.state.arena.projectiles || []
                    delegate: Rectangle {
                        required property var modelData
                        readonly property real zoomFactor: renderer.cameraState.zoom
                        width: 13 * zoomFactor
                        height: width
                        radius: width / 2
                        color: "#ff947a"
                        border.width: 1
                        border.color: "#ffe4b2"
                        x: projectileLayer.width / 2 + renderer.cameraState.panX
                           + (modelData.pos[0] / 1000 - .5) * 64 * zoomFactor - width / 2
                        y: projectileLayer.height / 2 + renderer.cameraState.panY
                           + (modelData.pos[1] / 1000 - .5) * 64 * zoomFactor - height / 2
                    }
                }
                Repeater {
                    model: root.state.r65.projectiles || []
                    delegate: Rectangle {
                        required property var modelData
                        readonly property real zoomFactor: renderer.cameraState.zoom
                        width: 9 * zoomFactor
                        height: width
                        radius: width / 2
                        color: "#7ddcf4"
                        x: projectileLayer.width / 2 + renderer.cameraState.panX
                           + (modelData.pos[0] / 1000 - .5) * 64 * zoomFactor - width / 2
                        y: projectileLayer.height / 2 + renderer.cameraState.panY
                           + (modelData.pos[1] / 1000 - .5) * 64 * zoomFactor - height / 2
                    }
                }
            }

            Rectangle {
                x: 15
                y: 15
                width: panel.implicitWidth + 24
                height: panel.implicitHeight + 20
                radius: 8
                color: "#ec18252d"
                Column {
                    id: panel
                    x: 12
                    y: 10
                    spacing: 4
                    Text {
                        color: "#fff0da"
                        font.pixelSize: 16
                        font.bold: true
                        text: "PV " + root.state.hero.hp + "/" +
                              root.state.hero.max_hp +
                              "   Endurance " + root.state.hero.stamina +
                              "   Tick " + root.state.tick
                    }
                    Text {
                        color: "#ebc798"
                        font.pixelSize: 14
                        text: "Boss — phase " + root.state.arena.boss.phase +
                              " / 2    |    PV " +
                              root.state.enemies[root.state.arena.boss_id].hp
                    }
                    Text {
                        color: "#a7dec9"
                        font.pixelSize: 13
                        text: "Gardes : " +
                              root.state.enemies[root.state.arena.flanker_ids[0]].hp +
                              " / " +
                              root.state.enemies[root.state.arena.flanker_ids[1]].hp
                    }
                }
            }

            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top
                anchors.topMargin: 30
                width: 440
                height: 42
                radius: 8
                color: "#cf76372b"
                visible: root.state.arena.boss.casting
                Text {
                    anchors.centerIn: parent
                    text: "BOSS — " + root.state.hint +
                          " (" + root.state.arena.boss.windup + " ticks)"
                    color: "#ffffff"
                    font.bold: true
                }
            }

            Rectangle {
                anchors.centerIn: parent
                width: 480
                height: 128
                radius: 14
                color: "#ee17232b"
                visible: root.state.victory || !root.state.hero.alive || root.state.paused
                Column {
                    anchors.centerIn: parent
                    spacing: 10
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        color: "#fff1c8"
                        font.bold: true
                        font.pixelSize: 22
                        text: root.state.victory ? "Arène remportée" :
                              !root.state.hero.alive ? "Défaite" : "Pause"
                    }
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        color: "#d3e1d9"
                        font.pixelSize: 14
                        text: root.state.victory ? "Sauvegarde disponible (F5)" :
                              !root.state.hero.alive ? "R : revenir au checkpoint" :
                              "P : reprendre"
                    }
                }
            }
        }
        Rectangle {
            id: footer
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 154
            color: "#101b21"
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 7
                Text {
                    Layout.fillWidth: true
                    color: "#f1e5cc"
                    font.pixelSize: 15
                    wrapMode: Text.WordWrap
                    text: root.state.message
                }
                Text {
                    Layout.fillWidth: true
                    color: "#b5ccc7"
                    font.pixelSize: 13
                    text: "ZQSD / WASD : bouger   Espace : combo   F : projectile   C : parade   Maj : esquive   Ctrl : garde"
                }
                RowLayout {
                    spacing: 9
                    Button {
                        text: root.state.paused ? "Reprendre (P)" : "Pause (P)"
                        focusPolicy: Qt.NoFocus
                        onClicked: { arena.pause(); root.clearInput() }
                    }
                    Button {
                        text: "Sauvegarder (F5)"
                        focusPolicy: Qt.NoFocus
                        onClicked: arena.save()
                    }
                    Button {
                        text: "Recharger (F9)"
                        focusPolicy: Qt.NoFocus
                        onClicked: { arena.load(); root.clearInput() }
                    }
                    CheckBox {
                        text: "Réduire les mouvements (M)"
                        checked: root.reducedMotion
                        onToggled: root.reducedMotion = checked
                    }
                }
                Text {
                    Layout.fillWidth: true
                    color: "#9cbab5"
                    font.pixelSize: 12
                    text: "R65.C prototype PC — replay v3 séparé · Renderer R3 partagé · GPU / export non certifiés"
                }
            }
        }
    }
}
