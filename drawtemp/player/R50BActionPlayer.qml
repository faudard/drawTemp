import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "../render"

// R50.B opt-in graphical slice. The renderer projects canonical Player R26.
// A tactical CT battle is shown as an explicit handoff, NOT falsely rendered
// as realtime combat. Its abandonment is an atomic GameSession intent.
ApplicationWindow {
    id: root
    property bool smokeMode: false
    visible: !smokeMode
    width: 1060
    height: 755
    minimumWidth: 760
    minimumHeight: 535
    color: "#142127"
    title: "DrawTemp R50.B — Player canonique (preview)"

    property var playerData: action.view
    property bool up: false
    property bool down: false
    property bool left: false
    property bool right: false
    property bool attackHeld: false
    property bool dodgeQueued: false
    property bool guardHeld: false
    property bool interactQueued: false

    readonly property bool actionReady:
        playerData.mode === "campaign" && !playerData.settled &&
        playerData.hero.alive && !playerData.paused

    Connections {
        target: action
        function onStateChanged() { root.playerData = action.view }
    }

    function clearInput() {
        up = false; down = false; left = false; right = false
        attackHeld = false; dodgeQueued = false
        guardHeld = false; interactQueued = false
    }

    Timer {
        id: inputClock
        interval: 16
        repeat: true
        running: !root.smokeMode && root.actionReady
        onTriggered: {
            const dx = (root.right ? 1 : 0) - (root.left ? 1 : 0)
            const dy = (root.down ? 1 : 0) - (root.up ? 1 : 0)
            action.pulse(dx, dy, root.attackHeld, root.dodgeQueued,
                         root.guardHeld, root.interactQueued)
            root.dodgeQueued = false
            root.interactQueued = false
        }
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
            else if (event.key === Qt.Key_P) {
                action.pause()
                root.clearInput()
            } else if (event.key === Qt.Key_F5) {
                action.save()
            } else if (event.key === Qt.Key_F9) {
                action.load()
                root.clearInput()
            } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                if (root.playerData.can_settle) {
                    action.settle()
                    root.clearInput()
                }
            } else if (event.key === Qt.Key_R) {
                if (root.playerData.mode === "battle") {
                    action.returnFromCt()
                    root.clearInput()
                }
            } else return
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
            id: viewportPanel
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: footer.top
            anchors.margins: 18
            radius: 12
            clip: true
            color: "#223b35"
            border.color: "#608d75"
            border.width: 2

            TopDownViewport { anchors.fill: parent }

            Rectangle {
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.margins: 14
                radius: 6
                width: hud.implicitWidth + 26
                height: hud.implicitHeight + 18
                color: "#dd142127"
                Text {
                    id: hud
                    anchors.centerIn: parent
                    color: "#fff0d0"
                    font.pixelSize: 16
                    font.bold: true
                    text: "PV " + root.playerData.hero.hp + "/" +
                          root.playerData.hero.max_hp +
                          "    Endurance " + root.playerData.hero.stamina +
                          "    Or campagne " + root.playerData.campaign_gold +
                          "    Tick " + root.playerData.tick
                }
            }

            Rectangle {
                anchors.centerIn: parent
                width: Math.min(parent.width - 50, 520)
                height: 132
                radius: 12
                color: "#e51c2830"
                visible: root.playerData.mode === "battle" ||
                         root.playerData.settled ||
                         root.playerData.paused || !root.playerData.hero.alive
                Column {
                    anchors.centerIn: parent
                    spacing: 10
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        color: "#ffedcf"
                        font.bold: true
                        font.pixelSize: 21
                        text: root.playerData.mode === "battle" ?
                              "Mission tactique CT démarrée" :
                              root.playerData.settled ? "Combat R26 terminé" :
                              !root.playerData.hero.alive ? "Défaite en action" :
                              "Pause"
                    }
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        color: "#c8dddc"
                        font.pixelSize: 14
                        text: root.playerData.mode === "battle" ?
                              "R : abandon CT explicite et retour à la clairière" :
                              root.playerData.settled ?
                              "Récompense attribuée : impossible de la rejouer" :
                              !root.playerData.hero.alive ?
                              "F9 : recharger. Aucun respawn implicite." :
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
            height: 196
            color: "#142127"
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 10
                Text {
                    Layout.fillWidth: true
                    color: "#e8f2ec"
                    font.pixelSize: 16
                    wrapMode: Text.WordWrap
                    text: root.playerData.message
                }
                Text {
                    Layout.fillWidth: true
                    color: "#9cbab5"
                    font.pixelSize: 13
                    wrapMode: Text.WordWrap
                    text: "ZQSD / WASD / flèches : bouger  ·  Espace : attaque  ·  Maj : esquive  ·  Ctrl : garde  ·  E : interaction"
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 9
                    Button {
                        text: root.playerData.paused ? "Reprendre (P)" : "Pause (P)"
                        focusPolicy: Qt.NoFocus
                        onClicked: { action.pause(); root.clearInput() }
                    }
                    Button {
                        text: "Sauvegarder (F5)"
                        focusPolicy: Qt.NoFocus
                        onClicked: action.save()
                    }
                    Button {
                        text: "Recharger (F9)"
                        focusPolicy: Qt.NoFocus
                        onClicked: { action.load(); root.clearInput() }
                    }
                    Button {
                        text: "Terminer R26 → CT"
                        enabled: root.playerData.can_settle && !root.playerData.paused
                        focusPolicy: Qt.NoFocus
                        onClicked: { action.settle(); root.clearInput() }
                    }
                    Button {
                        text: "Abandon CT et retour (R)"
                        enabled: root.playerData.mode === "battle" && !root.playerData.paused
                        focusPolicy: Qt.NoFocus
                        onClicked: { action.returnFromCt(); root.clearInput() }
                    }
                }
                Text {
                    Layout.fillWidth: true
                    color: "#9cbab5"
                    font.pixelSize: 12
                    wrapMode: Text.WordWrap
                    text: "Slot " + root.playerData.slot + " · Scène " +
                          root.playerData.route_scene +
                          " · Sauvegarde canonique R50.B, Player graphique expérimental — pas une release 9.0 certifiée"
                }
            }
        }
    }
}
