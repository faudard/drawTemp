import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../render"

ApplicationWindow {
    id: root
    // A CI smoke must instantiate and bind the full QML tree without
    // exposing a native window or starting its renderer.
    property bool smokeMode: false
    visible: !smokeMode
    width: 1280
    height: 800
    minimumWidth: 850
    minimumHeight: 580
    title: "DrawTemp 5.0 — " + playerData.title
    color: "#131c25"
    property var playerData: player.view
    property int currentSlot: 1
    property real textScale: 1
    property bool highContrast: false
    property color ivory: highContrast ? "#ffffff" : "#efe4d2"
    property color muted: highContrast ? "#f3ead6" : "#b2b8b8"
    property color gold: "#e7c78b"

    function activeSkills() {
        var units = (playerData.battle && playerData.battle.units) || []
        for (var i = 0; i < units.length; ++i)
            if (units[i].id === playerData.battle.active &&
                units[i].team === "player")
                return units[i].skills || []
        return []
    }

    Connections {
        target: player
        function onStateChanged() { root.playerData = player.view }
    }

    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0; color: "#1a3039" }
            GradientStop { position: 1; color: "#0b131c" }
        }
    }

    // Global commands. The viewport's arrows never intercept input from dialogs.
    Item {
        anchors.fill: parent
        focus: true
        Keys.onPressed: function(event) {
            if (pausePopup.opened || optionsPopup.opened)
                return
            if (event.key === Qt.Key_Escape) {
                if (root.playerData.screen !== "title")
                    pausePopup.open()
                event.accepted = true
                return
            }
            var screen = root.playerData.screen
            if (screen === "exploration") {
                if (event.key === Qt.Key_Up || event.key === Qt.Key_Z || event.key === Qt.Key_W)
                    player.exploreMove(0, -1)
                else if (event.key === Qt.Key_Down || event.key === Qt.Key_S)
                    player.exploreMove(0, 1)
                else if (event.key === Qt.Key_Left || event.key === Qt.Key_Q || event.key === Qt.Key_A)
                    player.exploreMove(-1, 0)
                else if (event.key === Qt.Key_Right || event.key === Qt.Key_D)
                    player.exploreMove(1, 0)
                else
                    return
                event.accepted = true
            } else if (screen === "battle") {
                var cell = root.playerData.selected
                if (event.key === Qt.Key_Left)
                    player.selectCell(cell[0] - 1, cell[1])
                else if (event.key === Qt.Key_Right)
                    player.selectCell(cell[0] + 1, cell[1])
                else if (event.key === Qt.Key_Up)
                    player.selectCell(cell[0], cell[1] - 1)
                else if (event.key === Qt.Key_Down)
                    player.selectCell(cell[0], cell[1] + 1)
                else if (event.key === Qt.Key_Space)
                    player.command("end")
                else
                    return
                event.accepted = true
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            spacing: 16
            Label {
                text: "✦  JEANNE D'ARC"
                color: root.gold
                font.bold: true
                font.letterSpacing: 3
                font.pixelSize: 19 * root.textScale
            }
            Label {
                text: "LES CENDRES DU ROYAUME  ·  PLAYER 5.0"
                color: root.muted
                font.pixelSize: 11 * root.textScale
                Layout.fillWidth: true
            }
            Label {
                text: "Révision " + root.playerData.revision
                visible: root.playerData.screen !== "title"
                color: root.muted
            }
            Button {
                text: "Options"
                onClicked: optionsPopup.open()
            }
            Button {
                objectName: "r14PauseMenu"
                text: "Menu  Esc"
                enabled: root.playerData.screen !== "title"
                onClicked: pausePopup.open()
            }
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: "#6d6860" }

        ColumnLayout {
            visible: root.playerData.screen === "title"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.alignment: Qt.AlignHCenter | Qt.AlignVCenter
            spacing: 17

            Item { Layout.fillHeight: true }
            Label {
                text: "JEANNE D'ARC"
                Layout.alignment: Qt.AlignHCenter
                color: root.gold
                font.pixelSize: 54 * root.textScale
                font.family: "serif"
                font.bold: true
            }
            Label {
                text: "Les Cendres du Royaume"
                Layout.alignment: Qt.AlignHCenter
                font.pixelSize: 25 * root.textScale
                color: root.ivory
                font.family: "serif"
            }
            Label {
                text: "Dans les champs de Domrémy, une voix appelle."
                color: root.muted
                Layout.alignment: Qt.AlignHCenter
                font.pixelSize: 15 * root.textScale
            }
            Item { Layout.preferredHeight: 38 }
            Button {
                objectName: "r14NewGame"
                text: "Nouvelle partie"
                Layout.preferredWidth: 290
                Layout.preferredHeight: 46
                Layout.alignment: Qt.AlignHCenter
                onClicked: player.newGame()
            }
            Button {
                objectName: "r14Continue"
                text: "Continuer"
                Layout.preferredWidth: 290
                Layout.alignment: Qt.AlignHCenter
                enabled: root.playerData.slots.length > 0
                onClicked: player.loadGame(root.playerData.slots[0])
            }
            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                Label { text: "Emplacement"; color: root.muted }
                ComboBox {
                    id: slotMenu
                    model: ["1", "2", "3"]
                    currentIndex: 0
                    onCurrentIndexChanged: root.currentSlot = currentIndex + 1
                }
                Button {
                    text: "Charger"
                    enabled: root.playerData.slots.indexOf(root.currentSlot) !== -1
                    onClicked: player.loadGame(root.currentSlot)
                }
                Button {
                    text: "Restaurer secours"
                    enabled: root.playerData.backups.indexOf(root.currentSlot) !== -1
                    onClicked: player.restoreBackup(root.currentSlot)
                }
            }
            Button {
                text: "Quitter"
                Layout.alignment: Qt.AlignHCenter
                onClicked: Qt.quit()
            }
            Label {
                text: root.playerData.message || ""
                visible: text.length > 0
                color: root.gold
                wrapMode: Text.WordWrap
                Layout.preferredWidth: 400
                horizontalAlignment: Text.AlignHCenter
                Layout.alignment: Qt.AlignHCenter
            }
            Item { Layout.fillHeight: true }
        }

        RowLayout {
            visible: root.playerData.screen === "dialogue"
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 30
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 12
                color: "#263a40"
                border.color: "#626d6b"
                ColumnLayout {
                    anchors.centerIn: parent
                    width: parent.width - 80
                    spacing: 18
                    Label {
                        text: root.playerData.scene.title || "Une rencontre"
                        color: root.gold
                        font.family: "serif"
                        font.pixelSize: 30 * root.textScale
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                    Label {
                        text: root.playerData.scene.speaker || "Narrateur"
                        color: root.gold
                        font.bold: true
                        font.pixelSize: 15 * root.textScale
                    }
                    Label {
                        text: root.playerData.scene.text || ""
                        color: root.ivory
                        font.pixelSize: 19 * root.textScale
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }
            }
            ColumnLayout {
                Layout.preferredWidth: 330
                Layout.fillHeight: true
                Label {
                    text: "VOTRE DÉCISION"
                    color: root.muted
                    font.bold: true
                    font.letterSpacing: 2
                }
                Repeater {
                    model: root.playerData.choices || []
                    Button {
                        Layout.fillWidth: true
                        objectName: "r14Choice-" + modelData.id
                        text: modelData.label || modelData.id
                        onClicked: player.choose(modelData.id)
                    }
                }
                Label {
                    text: root.playerData.choices.length === 0 ?
                          "Explorez les lieux pour poursuivre le récit." : ""
                    color: root.muted
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
                Item { Layout.fillHeight: true }
            }
        }

        ColumnLayout {
            visible: root.playerData.screen === "campaign"
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 18
            Item { Layout.fillHeight: true }
            Label {
                text: "Carnet de campagne"
                color: root.gold
                font.family: "serif"
                font.pixelSize: 40 * root.textScale
                Layout.alignment: Qt.AlignHCenter
            }
            Label {
                text: "Choisissez une mission accessible pour poursuivre le récit."
                color: root.ivory
                Layout.alignment: Qt.AlignHCenter
            }
            Repeater {
                model: root.playerData.missions
                Button {
                    objectName: "r14Mission-" + modelData
                    text: "Commencer · " + modelData
                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredWidth: 380
                    onClicked: player.startMission(modelData)
                }
            }
            Label {
                text: root.playerData.missions.length === 0 ?
                      "Aucune mission accessible ; vérifiez les décisions de campagne." : ""
                color: root.muted
                Layout.alignment: Qt.AlignHCenter
            }
            Item { Layout.fillHeight: true }
        }

        RowLayout {
            visible: ["exploration", "battle", "result"].indexOf(root.playerData.screen) !== -1
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 18
            Rectangle {
                color: "#162a30"
                radius: 10
                border.color: "#4e6260"
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                TacticalBoard {
                    id: board
                    anchors.fill: parent
                    anchors.margins: 8
                    battle: root.playerData.battle
                    exploration: root.playerData.screen === "exploration" ?
                                     root.playerData.exploration : ({})
                    selected: root.playerData.selected
                    onCellSelected: function(x, y) {
                        if (root.playerData.screen === "exploration") {
                            var pos = root.playerData.exploration.position
                            if (Math.abs(pos[0] - x) + Math.abs(pos[1] - y) === 1)
                                player.exploreMove(x - pos[0], y - pos[1])
                        } else
                            player.selectCell(x, y)
                    }
                }
                Rectangle {
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.margins: 13
                    width: zoomLabel.implicitWidth + 20
                    height: 34
                    color: "#b91b2630"
                    radius: 5
                    Label {
                        id: zoomLabel
                        anchors.centerIn: parent
                        text: Math.round(board.zoom * 100) + "%  ·  molette pour zoomer"
                        color: root.ivory
                    }
                }
            }
            Rectangle {
                color: "#23333c"
                radius: 10
                border.color: "#56645f"
                Layout.preferredWidth: 310
                Layout.fillHeight: true
                ScrollView {
                    anchors.fill: parent
                    anchors.margins: 14
                    contentWidth: availableWidth
                    ColumnLayout {
                        width: 282
                        spacing: 14
                        Label {
                            text: root.playerData.screen === "exploration" ?
                                  (root.playerData.exploration.title || "Exploration") :
                                  (root.playerData.battle.mission_id || "Combat")
                            color: root.gold
                            font.bold: true
                            font.pixelSize: 20 * root.textScale
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                        Label {
                            text: root.playerData.screen === "exploration" ?
                                  "Flèches / ZQSD / WASD : se déplacer. Cliquez sur une case adjacente." :
                                  "Objectif : " + (root.playerData.battle.objective || "")
                            color: root.ivory
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                        Label {
                            visible: root.playerData.screen !== "exploration"
                            text: "CT · tour " + (root.playerData.battle.tick || 0) +
                                  "\nUnité active : " + (root.playerData.battle.active || "—") +
                                  "\nCible : " + root.playerData.selected.join(", ")
                            color: root.ivory
                            Layout.fillWidth: true
                        }
                        Repeater {
                            model: root.playerData.screen === "exploration" ?
                                   (root.playerData.exploration.interactions || []) : []
                            Button {
                                Layout.fillWidth: true
                                text: (modelData.visited ? "✓ " : "◇ ") + modelData.title
                                enabled: !modelData.visited
                                onClicked: player.exploreInteract(modelData.id)
                            }
                        }
                        Repeater {
                            model: root.playerData.screen === "exploration" ?
                                   (root.playerData.exploration.actors || []) : []
                            Button {
                                Layout.fillWidth: true
                                text: modelData.kind === "civilian" ?
                                      "Secourir · " + modelData.name :
                                      "Parler · " + modelData.name
                                enabled: modelData.status === "active"
                                onClicked: player.exploreActor(modelData.id,
                                              modelData.kind === "civilian" ? "rescue" : "talk")
                            }
                        }
                        Label {
                            visible: root.playerData.screen === "battle"
                            text: "COMPÉTENCES"
                            color: root.gold
                        }
                        Repeater {
                            model: root.playerData.screen === "battle" ?
                                   root.activeSkills() : []
                            Button {
                                Layout.fillWidth: true
                                text: "Utiliser · " + modelData
                                onClicked: player.useSkill(modelData)
                            }
                        }
                        Label {
                            visible: root.playerData.screen === "battle"
                            text: "OBJETS"
                            color: root.gold
                        }
                        Repeater {
                            model: root.playerData.screen === "battle" ?
                                   Object.keys((root.playerData.battle.inventory || {}).player || {}) : []
                            Button {
                                Layout.fillWidth: true
                                text: modelData + " ×" + root.playerData.battle.inventory.player[modelData]
                                enabled: root.playerData.battle.inventory.player[modelData] > 0
                                onClicked: player.useItem(modelData)
                            }
                        }
                        Label {
                            visible: root.playerData.screen === "battle"
                            text: "INTERACTIONS"
                            color: root.gold
                        }
                        Repeater {
                            model: root.playerData.screen === "battle" ?
                                   (root.playerData.battle.objects || []) : []
                            Button {
                                Layout.fillWidth: true
                                text: modelData.kind + " · " + modelData.id
                                onClicked: player.interactObject(modelData.id)
                            }
                        }
                        Repeater {
                            model: root.playerData.screen === "exploration" ? [] :
                                   (root.playerData.battle.units || [])
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 58
                                color: modelData.id === root.playerData.battle.active ?
                                       "#46565c" : "#283840"
                                radius: 5
                                Column {
                                    anchors.fill: parent
                                    anchors.margins: 6
                                    Label {
                                        text: (modelData.team === "enemy" ? "⚔ " : "◆ ") +
                                              (modelData.name || modelData.id)
                                        color: root.ivory
                                        font.bold: true
                                    }
                                    Label {
                                        text: "PV " + modelData.hp + "/" + modelData.max_hp +
                                              "  ·  PM " + modelData.mp +
                                              "  ·  CT " + modelData.ct
                                        color: root.muted
                                        font.pixelSize: 12 * root.textScale
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        RowLayout {
            visible: root.playerData.screen === "battle"
            Layout.fillWidth: true
            spacing: 8
            Button {
                text: "Démarrer le combat"
                visible: root.playerData.battle.deploying === true
                onClicked: player.command("deploy")
            }
            Button { text: "Déplacer"; onClicked: player.command("move") }
            Button { text: "Attaquer"; onClicked: player.command("attack") }
            Button { text: "Aperçu déplacement"; onClicked: player.preview("move") }
            Button { text: "Aperçu attaque"; onClicked: player.preview("attack") }
            Button { text: "Fin du tour  Espace"; onClicked: player.command("end") }
            Button { text: "Tour ennemi"; onClicked: player.enemyTurn() }
            Item { Layout.fillWidth: true }
        }

        RowLayout {
            visible: root.playerData.screen === "result"
            Layout.fillWidth: true
            Label {
                text: "Combat terminé · " + (root.playerData.battle.result || "")
                color: root.gold
                font.pixelSize: 19 * root.textScale
                Layout.fillWidth: true
            }
            Button {
                text: "Retour en campagne"
                onClicked: player.finishBattle()
            }
        }

        RowLayout {
            visible: root.playerData.screen !== "title"
            Layout.fillWidth: true
            Label {
                text: root.playerData.forecast || root.playerData.message ||
                      "F5 : sauvegarder · Esc : pause"
                color: root.gold
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            Button {
                objectName: "r14SaveGame"
                text: "Sauvegarder · F5"
                onClicked: player.saveGame(root.currentSlot)
            }
        }
    }

    Shortcut {
        sequence: "F5"
        enabled: root.playerData.screen !== "title"
        onActivated: player.saveGame(root.currentSlot)
    }

    Popup {
        id: pausePopup
        modal: true
        focus: true
        anchors.centerIn: Overlay.overlay
        width: 310
        padding: 22
        ColumnLayout {
            anchors.fill: parent
            Label { text: "PAUSE"; font.pixelSize: 26; font.bold: true }
            Button { text: "Reprendre"; Layout.fillWidth: true; onClicked: pausePopup.close() }
            Button {
                text: "Sauvegarder"
                Layout.fillWidth: true
                onClicked: { player.saveGame(root.currentSlot); pausePopup.close() }
            }
            Button {
                text: "Options"
                Layout.fillWidth: true
                onClicked: { pausePopup.close(); optionsPopup.open() }
            }
            Button {
                objectName: "r14TitleFromPause"
                text: "Menu principal"
                Layout.fillWidth: true
                onClicked: { pausePopup.close(); player.titleScreen() }
            }
            Button { text: "Quitter"; Layout.fillWidth: true; onClicked: Qt.quit() }
        }
    }

    Popup {
        id: optionsPopup
        modal: true
        focus: true
        anchors.centerIn: Overlay.overlay
        width: 400
        padding: 20
        ColumnLayout {
            anchors.fill: parent
            spacing: 14
            Label { text: "OPTIONS · ACCESSIBILITÉ"; font.bold: true; font.pixelSize: 20 }
            Label { text: "Taille des textes" }
            Slider {
                Layout.fillWidth: true
                from: 0.85; to: 1.35; stepSize: 0.05
                value: root.textScale
                onMoved: root.textScale = value
            }
            CheckBox {
                text: "Contraste élevé"
                checked: root.highContrast
                onToggled: root.highContrast = checked
            }
            Label {
                text: "Zoom carte : molette · Déplacement : flèches / ZQSD / WASD\n" +
                      "Combat : clic pour sélectionner, espace pour terminer le tour."
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            Button {
                text: "Fermer"
                Layout.alignment: Qt.AlignRight
                onClicked: optionsPopup.close()
            }
        }
    }
}
