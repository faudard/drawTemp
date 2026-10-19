import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
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
    property real textScale: playerData.settings.display.text_scale
    property bool highContrast: playerData.settings.display.high_contrast
    property bool inputLocked: pausePopup.opened || optionsPopup.opened || Boolean(playerData.cinematic.id) ||
                               recoveryPopup.opened || recoveryErrorPopup.opened
    function binding(action) { return playerData.settings.bindings[action] || "" }
    onPlayerDataChanged: {
        if (smokeMode) return
        if (playerData.settings.display.fullscreen && visibility !== Window.FullScreen)
            showFullScreen()
        else if (!playerData.settings.display.fullscreen && visibility === Window.FullScreen)
            showNormal()
    }
    Component.onCompleted: {
        if (!smokeMode && playerData.settings.display.fullscreen) showFullScreen()
    }
    property color ivory: highContrast ? "#ffffff" : "#efe4d2"
    property color muted: highContrast ? "#f3ead6" : "#b2b8b8"
    property color gold: "#e7c78b"
    property bool tacticalOverlayEnabled: true

    // Non-puzzle maps keep their legacy tactical interactions unchanged.
    function legacyInteractions() {
        var objects = (playerData.battle && playerData.battle.objects) || []
        if (!playerData.puzzle.enabled) return objects
        var legacy = []
        for (var i = 0; i < objects.length; ++i) {
            var kind = objects[i].kind
            if (kind !== "door" && kind !== "switch" && kind !== "chest" &&
                kind !== "key" && kind !== "plate" && kind !== "block")
                legacy.push(objects[i])
        }
        return legacy
    }

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
        function onStateChanged() {
            root.playerData = player.view
            if (player.recoveryOffer.pending && !recoveryPopup.opened)
                recoveryPopup.open()
            if (player.recoveryNotice.active && !recoveryErrorPopup.opened)
                recoveryErrorPopup.open()
        }
    }

    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0; color: "#1a3039" }
            GradientStop { position: 1; color: "#0b131c" }
        }
    }

    // Window-level shortcuts remain active when buttons have keyboard focus.
    // Popups disable gameplay actions; QML never mutates tactical rules.
    Shortcut {
        sequence: root.binding("explore_up")
        enabled: root.playerData.screen === "exploration" && !root.inputLocked
        onActivated: player.exploreMove(0, -1)
    }
    Shortcut {
        sequence: "Up"
        enabled: root.playerData.screen === "exploration" && !root.inputLocked && root.binding("explore_up") !== "Up"
        onActivated: player.exploreMove(0, -1)
    }
    Shortcut {
        sequence: root.binding("explore_down")
        enabled: root.playerData.screen === "exploration" && !root.inputLocked
        onActivated: player.exploreMove(0, 1)
    }
    Shortcut {
        sequence: "Down"
        enabled: root.playerData.screen === "exploration" && !root.inputLocked && root.binding("explore_down") !== "Down"
        onActivated: player.exploreMove(0, 1)
    }
    Shortcut {
        sequence: root.binding("explore_left")
        enabled: root.playerData.screen === "exploration" && !root.inputLocked
        onActivated: player.exploreMove(-1, 0)
    }
    Shortcut {
        sequence: "Left"
        enabled: root.playerData.screen === "exploration" && !root.inputLocked && root.binding("explore_left") !== "Left"
        onActivated: player.exploreMove(-1, 0)
    }
    Shortcut {
        sequence: root.binding("explore_right")
        enabled: root.playerData.screen === "exploration" && !root.inputLocked
        onActivated: player.exploreMove(1, 0)
    }
    Shortcut {
        sequence: "Right"
        enabled: root.playerData.screen === "exploration" && !root.inputLocked && root.binding("explore_right") !== "Right"
        onActivated: player.exploreMove(1, 0)
    }
    Shortcut {
        sequence: root.binding("battle_up")
        enabled: root.playerData.screen === "battle" && !root.inputLocked
        onActivated: player.selectCell(root.playerData.selected[0] + 0, root.playerData.selected[1] + -1)
    }
    Shortcut {
        sequence: "Up"
        enabled: root.playerData.screen === "battle" && !root.inputLocked && root.binding("battle_up") !== "Up"
        onActivated: player.selectCell(root.playerData.selected[0] + 0, root.playerData.selected[1] + -1)
    }
    Shortcut {
        sequence: root.binding("battle_down")
        enabled: root.playerData.screen === "battle" && !root.inputLocked
        onActivated: player.selectCell(root.playerData.selected[0] + 0, root.playerData.selected[1] + 1)
    }
    Shortcut {
        sequence: "Down"
        enabled: root.playerData.screen === "battle" && !root.inputLocked && root.binding("battle_down") !== "Down"
        onActivated: player.selectCell(root.playerData.selected[0] + 0, root.playerData.selected[1] + 1)
    }
    Shortcut {
        sequence: root.binding("battle_left")
        enabled: root.playerData.screen === "battle" && !root.inputLocked
        onActivated: player.selectCell(root.playerData.selected[0] + -1, root.playerData.selected[1] + 0)
    }
    Shortcut {
        sequence: "Left"
        enabled: root.playerData.screen === "battle" && !root.inputLocked && root.binding("battle_left") !== "Left"
        onActivated: player.selectCell(root.playerData.selected[0] + -1, root.playerData.selected[1] + 0)
    }
    Shortcut {
        sequence: root.binding("battle_right")
        enabled: root.playerData.screen === "battle" && !root.inputLocked
        onActivated: player.selectCell(root.playerData.selected[0] + 1, root.playerData.selected[1] + 0)
    }
    Shortcut {
        sequence: "Right"
        enabled: root.playerData.screen === "battle" && !root.inputLocked && root.binding("battle_right") !== "Right"
        onActivated: player.selectCell(root.playerData.selected[0] + 1, root.playerData.selected[1] + 0)
    }
    Shortcut {
        sequence: root.binding("battle_move")
        enabled: root.playerData.screen === "battle" && !root.inputLocked
        onActivated: player.requestTarget("move", "")
    }
    Shortcut {
        sequence: root.binding("battle_attack")
        enabled: root.playerData.screen === "battle" && !root.inputLocked
        onActivated: player.requestTarget("attack", "")
    }
    Shortcut {
        sequence: root.binding("battle_end")
        enabled: root.playerData.screen === "battle" && !root.inputLocked
        onActivated: player.command("end")
    }
    Shortcut {
        sequence: root.binding("save")
        enabled: root.playerData.screen !== "title" && !root.inputLocked
        onActivated: player.saveGame(root.currentSlot)
    }
    Shortcut {
        sequence: "Return"
        enabled: root.playerData.screen === "battle" && !root.inputLocked &&
                 root.playerData.pending_target.valid === true
        onActivated: player.confirmTarget()
    }
    Shortcut {
        sequence: "Escape"
        enabled: root.playerData.screen === "battle" && !root.inputLocked &&
                 !!root.playerData.pending_target.kind
        onActivated: player.cancelTarget()
    }
    Shortcut {
        sequence: root.binding("pause")
        enabled: root.playerData.screen !== "title" && !root.inputLocked &&
                 !root.playerData.pending_target.kind
        onActivated: pausePopup.open()
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
                enabled: root.playerData.save_manager.continue_available
                onClicked: player.continueGame()
            }
            Label {
                text: root.playerData.save_manager.continue_available ?
                      "Reprendre : " + root.playerData.save_manager.continue_label : 
                      "Aucune sauvegarde valide"
                color: root.muted
                Layout.alignment: Qt.AlignHCenter
                font.pixelSize: 12 * root.textScale
            }
            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                Button {
                    text: "Charger autosauvegarde"
                    enabled: root.playerData.save_manager.autosave.status === "valid"
                    onClicked: player.loadAutosave()
                }
                Button {
                    text: "Restaurer auto (.bak)"
                    enabled: root.playerData.save_manager.autosave.recoverable &&
                             root.playerData.save_manager.autosave.status !== "valid"
                    objectName: "r17RequestAutosaveRecovery"
                    onClicked: player.requestRecovery(0)
                }
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
                    objectName: "r17RequestManualRecovery"
                    enabled: root.playerData.save_manager.sources.length > root.currentSlot &&
                             root.playerData.save_manager.sources[root.currentSlot].recoverable &&
                             root.playerData.save_manager.sources[root.currentSlot].status !== "valid"
                    onClicked: player.requestRecovery(root.currentSlot)
                }
            }
            Button {
                text: "Quitter"
                Layout.alignment: Qt.AlignHCenter
                onClicked: Qt.quit()
            }
            Label {
                text: (root.playerData.save_manager.warnings || []).join("\\n")
                visible: text.length > 0
                color: "#f5ad9a"
                wrapMode: Text.WordWrap
                Layout.preferredWidth: 510
                horizontalAlignment: Text.AlignHCenter
                Layout.alignment: Qt.AlignHCenter
                font.pixelSize: 12 * root.textScale
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
            Label {
                text: "Équipement de Jeanne — contenu R8"
                font.bold: true
                font.pixelSize: 17 * root.textScale
                color: root.gold
                Layout.alignment: Qt.AlignHCenter
            }
            Repeater {
                model: ["weapon", "armor", "accessory"]
                Button {
                    Layout.preferredWidth: 380
                    Layout.alignment: Qt.AlignHCenter
                    property string equippedId:
                        (root.playerData.gear.equipped || {})[modelData] || ""
                    text: modelData + ": " +
                          (equippedId ? equippedId + "  ·  Retirer" : "—")
                    enabled: equippedId !== ""
                    onClicked: player.unequipHero("jeanne", modelData)
                }
            }
            Repeater {
                model: root.playerData.gear.inventory || []
                Button {
                    Layout.preferredWidth: 380
                    Layout.alignment: Qt.AlignHCenter
                    text: "Équiper " + modelData.name + " (" +
                          modelData.slot + " · " + modelData.count + " disponible)"
                    enabled: modelData.count > 0
                    onClicked: player.equipHero("jeanne", modelData.id)
                }
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
                    tactical: root.playerData.tactical
                    animationPlan: player.animationPlan
                    showTacticalOverlay: root.tacticalOverlayEnabled
                    showGrid: root.playerData.settings.display.show_grid
                    showHeights: root.playerData.settings.display.show_heights
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
                            visible: renderer.characterOutfits.length > 1
                            text: "TENUE · aperçu visuel (non sauvegardé)"
                            color: root.gold
                            font.bold: true
                            Layout.fillWidth: true
                        }
                        ComboBox {
                            visible: renderer.characterOutfits.length > 1
                            Layout.fillWidth: true
                            model: renderer.characterOutfits
                            currentIndex: Math.max(0, renderer.characterOutfits.indexOf(
                                               renderer.characterCurrentOutfit))
                            onActivated: player.previewOutfit(renderer.characterId, currentText)
                        }
                        Label {
                            text: root.playerData.screen === "exploration" ?
                                  "Déplacement : " + root.binding("explore_up") + "/" +
                                  root.binding("explore_left") + "/" +
                                  root.binding("explore_down") + "/" +
                                  root.binding("explore_right") +
                                  " ou flèches. Cliquez sur une case adjacente." :
                                  "Objectif : " + (root.playerData.battle.objective || "")
                            color: root.ivory
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                        ColumnLayout {
                            visible: root.playerData.screen === "exploration" &&
                                     root.playerData.living_world !== null &&
                                     root.playerData.living_world !== undefined
                            Layout.fillWidth: true
                            spacing: 8
                            Label {
                                text: "MONDE VIVANT · JOUR " +
                                      (root.playerData.living_world ?
                                       root.playerData.living_world.day + 1 : 1)
                                color: root.gold
                                font.bold: true
                                Layout.fillWidth: true
                            }
                            Label {
                                text: {
                                    var w = root.playerData.living_world
                                    if (!w) return ""
                                    var h = Math.floor(w.minute / 60)
                                    var m = w.minute % 60
                                    return ("0" + h).slice(-2) + ":" +
                                           ("0" + m).slice(-2) + " · " +
                                           (w.npcs || []).length + " PNJ dans cette zone"
                                }
                                color: root.ivory
                                Layout.fillWidth: true
                            }
                            Button {
                                text: "Attendre 1 minute"
                                enabled: !root.inputLocked
                                Layout.fillWidth: true
                                onClicked: {
                                    var w = root.playerData.living_world
                                    if (w) {
                                        // Project ticks/minute is authored, not hardcoded.
                                        // worldMinuteWait is provided in the projection.
                                        player.worldWait(w.ticks_per_minute || 1)
                                    }
                                }
                            }
                            Repeater {
                                model: root.playerData.living_world ?
                                       (root.playerData.living_world.npcs || []) : []
                                Label {
                                    Layout.fillWidth: true
                                    wrapMode: Text.WordWrap
                                    color: root.muted
                                    text: modelData.id + " · " + modelData.activity
                                }
                            }
                        }
                        Label {
                            visible: root.playerData.screen !== "exploration"
                            text: "CT · tour " + (root.playerData.battle.tick || 0) +
                                  "\nUnité active : " + (root.playerData.battle.active || "—") +
                                  "\nCase sélectionnée : " + root.playerData.selected.join(", ") +
                                  "\nSélectionner ≠ agir : Déplacer/Attaquer, puis Confirmer (Entrée)" +
                                  "\nLa prévision n'est pas un résultat garanti."
                            color: root.ivory
                            Layout.fillWidth: true
                        }
                        ColumnLayout {
                            visible: root.playerData.screen === "battle" ||
                                     root.playerData.screen === "result"
                            Layout.fillWidth: true
                            Label {
                                text: "PRÉVISION TACTIQUE · MOTEUR"
                                color: root.gold
                                font.bold: true
                                font.pixelSize: 12 * root.textScale
                            }
                            Label {
                                Layout.fillWidth: true
                                wrapMode: Text.WordWrap
                                color: root.ivory
                                text: root.playerData.tactical.selection_summary || ""
                            }
                            Label {
                                Layout.fillWidth: true
                                wrapMode: Text.WordWrap
                                color: root.muted
                                text: root.playerData.tactical.focus ?
                                  (root.playerData.tactical.focus.line_of_sight === null ?
                                      "" : root.playerData.tactical.focus.line_of_sight ?
                                        "Ligne de vue : dégagée" : "Ligne de vue : obstruée")
                                  : ""
                            }
                            Label {
                                Layout.fillWidth: true
                                wrapMode: Text.WordWrap
                                color: root.gold
                                text: root.playerData.tactical.focus &&
                                      root.playerData.tactical.focus.move ?
                                  "Mouvement possible · coût " +
                                      root.playerData.tactical.focus.move.cost +
                                      " · risques sur le trajet : " +
                                      root.playerData.tactical.focus.move.risks.length :
                                  ""
                            }
                            Label {
                                Layout.fillWidth: true
                                wrapMode: Text.WordWrap
                                color: "#f4b5a5"
                                text: root.playerData.tactical.focus ?
                                      (root.playerData.tactical.focus.error || "") : ""
                            }
                            Repeater {
                                model: root.playerData.tactical.focus ?
                                       (root.playerData.tactical.focus.forecast || []) : []
                                Label {
                                    Layout.fillWidth: true
                                    wrapMode: Text.WordWrap
                                    color: root.ivory
                                    text: (modelData.kind || "effet") + " · " +
                                          modelData.unit + " · " + modelData.amount +
                                          (typeof modelData.chance === "number" ?
                                          " · probabilité " +
                                          Math.round(modelData.chance * 100) + "%" : "") +
                                          (modelData.redirected_to ?
                                          " · intercepté par " + modelData.redirected_to : "")
                                }
                            }
                            Repeater {
                                model: root.playerData.tactical.focus ?
                                       (root.playerData.tactical.focus.danger || []) : []
                                Label {
                                    Layout.fillWidth: true
                                    wrapMode: Text.WordWrap
                                    color: "#f2b88e"
                                    text: "⚠ " + modelData.kind + " · " +
                                          (modelData.certainty === "certain" ? "certain" :
                                           modelData.certainty === "scheduled" ? "programmé" :
                                           modelData.certainty === "armed" ? "réaction armée" :
                                           "possible, non garanti")
                                }
                            }
                        }
                        CheckBox {
                            visible: root.playerData.screen === "battle" ||
                                     root.playerData.screen === "result"
                            text: "Afficher portées et dangers"
                            checked: root.tacticalOverlayEnabled
                            onClicked: root.tacticalOverlayEnabled = checked
                        }
                        Label {
                            visible: root.playerData.screen === "battle"
                            text: "PROCHAINES ACTIVATIONS · CT ESTIMÉ"
                            color: root.gold
                            font.bold: true
                        }
                        Repeater {
                            model: root.playerData.tactical.timeline || []
                            Label {
                                Layout.fillWidth: true
                                wrapMode: Text.WordWrap
                                color: modelData.team === "enemy" ?
                                          "#f0aca8" : root.ivory
                                text: (modelData.active ? "▶ " : "") +
                                      modelData.unit + " · " +
                                      (modelData.active ? "ACTIF" :
                                       modelData.eta_ticks === null ? "bloqué" :
                                       "t+" + modelData.eta_ticks + " estimé")
                            }
                        }
                        Label {
                            visible: root.playerData.screen === "battle"
                            text: "MENACES OBSERVÉES / CONDITIONNELLES"
                            color: root.gold
                            font.bold: true
                        }
                        Repeater {
                            model: root.playerData.tactical.casts || []
                            Label {
                                Layout.fillWidth: true
                                wrapMode: Text.WordWrap
                                color: "#dbc0f3"
                                text: "Sort programmé · " + modelData.unit +
                                      " · " + modelData.skill + " · t-" +
                                      modelData.remaining_ticks
                            }
                        }
                        Repeater {
                            model: root.playerData.tactical.charges || []
                            Label {
                                Layout.fillWidth: true
                                wrapMode: Text.WordWrap
                                color: "#ead39b"
                                text: "Charge possible · " + modelData.unit +
                                      " → " + modelData.target +
                                      " (non garantie)"
                            }
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
                                text: "Cibler · " + modelData
                                onClicked: player.inspectSkill(modelData)
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
                            visible: root.playerData.screen === "battle" &&
                                     root.playerData.puzzle.enabled
                            text: "ÉNIGME · ACTIONS À PORTÉE"
                            color: root.gold
                            font.bold: true
                        }
                        Repeater {
                            model: root.playerData.screen === "battle" &&
                                   root.playerData.puzzle.enabled ?
                                   root.playerData.puzzle.actions : []
                            Button {
                                Layout.fillWidth: true
                                objectName: "r27PuzzleAction"
                                text: (modelData.selected ? "◆ " : "") +
                                      modelData.label +
                                      (!modelData.enabled && modelData.reason ?
                                       " — " + modelData.reason : "")
                                enabled: modelData.enabled && !root.inputLocked
                                onClicked: player.puzzleAction(modelData.id)
                                Accessible.description: modelData.reason || modelData.label
                            }
                        }
                        Label {
                            visible: root.playerData.screen === "battle" &&
                                     root.playerData.puzzle.enabled
                            text: "ÉTAT DE L'ÉNIGME · SAUVEGARDE CANONIQUE"
                            color: root.gold
                            font.bold: true
                        }
                        Repeater {
                            model: root.playerData.screen === "battle" &&
                                   root.playerData.puzzle.enabled ?
                                   root.playerData.puzzle.status : []
                            Label {
                                Layout.fillWidth: true
                                wrapMode: Text.WordWrap
                                color: root.muted
                                text: modelData.label + " : " + modelData.detail
                            }
                        }
                        Label {
                            visible: root.playerData.screen === "battle" &&
                                     !root.playerData.puzzle.enabled
                            text: "INTERACTIONS"
                            color: root.gold
                        }
                        Repeater {
                            model: root.playerData.screen === "battle" ?
                                   root.legacyInteractions() : []
                            Button {
                                Layout.fillWidth: true
                                text: modelData.kind + " · " + modelData.id
                                onClicked: modelData.kind === "door" ?
                                           player.toggleDoor(modelData.id) :
                                           player.interactObject(modelData.id)
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
            Button {
                objectName: "r18RequestMove"
                text: "Déplacer"
                onClicked: player.requestTarget("move", "")
            }
            Button {
                objectName: "r18RequestAttack"
                text: "Attaquer"
                onClicked: player.requestTarget("attack", "")
            }
            Button { text: "Aperçu déplacement"; onClicked: player.preview("move") }
            Button { text: "Prévision attaque"; onClicked: player.preview("attack") }
            Button {
                text: "Utiliser " + (root.playerData.tactical.skill || "attaque")
                enabled: !!(root.playerData && root.playerData.tactical &&
                            root.playerData.tactical.focus &&
                            root.playerData.tactical.focus.can_target === true)
                onClicked: {
                    if (root.playerData.tactical.skill === "attack")
                        player.requestTarget("attack", "")
                    else
                        player.requestTarget("skill", root.playerData.tactical.skill)
                }
            }
            Button { text: "Fin du tour  " + root.binding("battle_end"); onClicked: player.command("end") }
            Button { text: "Tour ennemi"; onClicked: player.enemyTurn() }
            Item { Layout.fillWidth: true }
        }

        Rectangle {
            objectName: "r18TargetConfirmation"
            visible: root.playerData.screen === "battle" &&
                     !!root.playerData.pending_target.kind
            Layout.fillWidth: true
            implicitHeight: targetPanel.implicitHeight + 20
            radius: 8
            color: "#263b43"
            border.color: root.playerData.pending_target.valid ? "#e7c78b" : "#f0aca8"
            RowLayout {
                id: targetPanel
                anchors.fill: parent
                anchors.margins: 10
                spacing: 12
                Label {
                    text: "Action : " + (root.playerData.pending_target.kind || "") +
                          " · case " + (root.playerData.pending_target.cell || []).join(", ") +
                          "\n" + (root.playerData.pending_target.details || "") +
                          (root.playerData.pending_target.valid ? "" :
                           "\nLe tour a changé : annulez et choisissez une nouvelle action.")
                    color: root.ivory
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    font.pixelSize: 13 * root.textScale
                    Accessible.name: text
                }
                Button {
                    objectName: "r18ConfirmTarget"
                    text: "Confirmer · Entrée"
                    enabled: root.playerData.pending_target.valid === true
                    onClicked: player.confirmTarget()
                    Accessible.name: "Confirmer l'action ciblée"
                }
                Button {
                    objectName: "r18CancelTarget"
                    text: "Annuler · Échap"
                    onClicked: player.cancelTarget()
                    Accessible.name: "Annuler l'action ciblée"
                }
            }
        }

        RowLayout {
            visible: root.playerData.screen === "battle" &&
                     ((root.playerData.battle.level_links || []).length > 0)
            Layout.fillWidth: true
            spacing: 8
            Label { text: "Étage cible"; color: root.ivory }
            ComboBox {
                id: targetFloor
                model: ["Sol", "Étage 1", "Étage 2", "Étage 3"]
                Layout.preferredWidth: 130
            }
            Label {
                text: "Case " + root.playerData.selected[0] + "," +
                      root.playerData.selected[1]
                color: root.muted
            }
            Button {
                text: "Escaliers"
                onClicked: player.levelMove(targetFloor.currentIndex,
                                            root.playerData.selected[0],
                                            root.playerData.selected[1])
            }
            Button {
                text: "Tir vertical"
                onClicked: player.levelAttack(targetFloor.currentIndex,
                                              root.playerData.selected[0],
                                              root.playerData.selected[1])
            }
            Label {
                text: "Niveau de l'unité : " + (
                    (root.playerData.battle.unit_levels || {})[
                        root.playerData.battle.active] || 0)
                color: root.muted
            }
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
                text: root.playerData.autosave_warning ||
                      root.playerData.forecast || root.playerData.message ||
                      root.binding("save") + " : sauvegarder · " + root.binding("pause") + " : pause"
                color: root.playerData.autosave_warning ? "#f5ad9a" : root.gold
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            Button {
                objectName: "r14SaveGame"
                text: "Sauvegarder · " + root.binding("save")
                onClicked: player.saveGame(root.currentSlot)
            }
        }
    }

    // R17.11: every recovery is a separate explicit user decision. The
    // approved bytes are SHA-bound in R1 under the single-writer lock.
    Popup {
        id: recoveryPopup
        objectName: "r17RecoveryDialog"
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape
        anchors.centerIn: Overlay.overlay
        width: Math.min(root.width - 48, 530)
        height: 300
        padding: 22
        onClosed: player.cancelRecovery()
        background: Rectangle {
            radius: 10
            color: "#1d3039"
            border.color: "#dbb67e"
        }
        ColumnLayout {
            anchors.fill: parent
            spacing: 12
            Label {
                text: "Confirmer la restauration"
                color: root.gold
                font.pixelSize: 22 * root.textScale
                font.bold: true
                Layout.fillWidth: true
            }
            Label {
                text: player.recoveryOffer.title || ""
                color: root.ivory
                font.pixelSize: 16 * root.textScale
            }
            Label {
                text: player.recoveryOffer.description || ""
                color: root.ivory
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                Layout.fillHeight: true
                Accessible.name: text
            }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                Button {
                    objectName: "r17CancelRecovery"
                    text: "Annuler"
                    onClicked: recoveryPopup.close()
                }
                Button {
                    objectName: "r17ConfirmRecovery"
                    text: "Restaurer le secours vérifié"
                    enabled: player.recoveryOffer.pending
                    onClicked: {
                        player.confirmRecovery()
                        recoveryPopup.close()
                    }
                }
            }
        }
    }

    Popup {
        id: recoveryErrorPopup
        objectName: "r17RecoveryError"
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape
        anchors.centerIn: Overlay.overlay
        width: Math.min(root.width - 48, 515)
        height: 295
        padding: 22
        onClosed: player.dismissRecoveryNotice()
        background: Rectangle {
            radius: 10
            color: "#26323b"
            border.color: "#ed9b8c"
        }
        ColumnLayout {
            anchors.fill: parent
            spacing: 12
            Label {
                text: player.recoveryNotice.title || "Action impossible"
                color: "#ffb1a2"
                font.bold: true
                font.pixelSize: 22 * root.textScale
                Layout.fillWidth: true
            }
            Label {
                text: player.recoveryNotice.advice || ""
                color: root.ivory
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Label {
                    text: player.recoveryNotice.detail || ""
                    width: parent.width
                    color: root.muted
                    wrapMode: Text.Wrap
                    Accessible.name: text
                }
            }
            Button {
                objectName: "r17DismissRecoveryError"
                text: "Compris"
                Layout.alignment: Qt.AlignRight
                onClicked: recoveryErrorPopup.close()
            }
        }
    }

    // R20.C.1: a presentation-only cinematic overlay, projected with the
    // shared R11 frame_payload. Engine choices remain blocked until the next
    // clip is acknowledged in the canonical campaign checkpoint.
    Shortcut {
        sequence: "Escape"
        enabled: cinematicOverlay.visible && !pausePopup.opened && !optionsPopup.opened
        onActivated: player.cinematicSkip()
    }

    Rectangle {
        id: cinematicOverlay
        objectName: "r20CinematicOverlay"
        property var clip: root.playerData.cinematic || ({})
        property var frameData: clip.frame || ({})
        anchors.fill: parent
        visible: Boolean(clip.id) && !root.smokeMode
        z: 100
        color: frameData.background || "#101a2b"
        border.color: "#987f61"
        border.width: 2

        // Capture clicks over the campaign and tactical scene during playback.
        MouseArea { anchors.fill: parent }

        Timer {
            interval: 40
            repeat: true
            running: cinematicOverlay.visible && Boolean(cinematicOverlay.clip.playing)
            onTriggered: player.cinematicTick()
        }

        Label {
            anchors.top: parent.top
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.topMargin: 30
            text: cinematicOverlay.clip.title || "Jeanne d'Arc"
            color: "#efdcad"
            font.pixelSize: 28 * root.textScale
            font.family: "serif"
            font.bold: true
        }

        Item {
            id: cinematicCanvas
            anchors.fill: parent
            anchors.topMargin: 82
            anchors.bottomMargin: 205
            clip: true
            Repeater {
                model: cinematicOverlay.frameData.actors || []
                delegate: Item {
                    width: 90
                    height: 120
                    x: (0.5 + (modelData.x - 0.5 -
                        (cinematicOverlay.frameData.cameraX || 0)) *
                        (cinematicOverlay.frameData.zoom || 1)) * cinematicCanvas.width - width/2
                    y: (0.5 + (modelData.y - 0.5 -
                        (cinematicOverlay.frameData.cameraY || 0)) *
                        (cinematicOverlay.frameData.zoom || 1)) * cinematicCanvas.height - height/2
                    Image {
                        anchors.fill: parent
                        source: modelData.image || ""
                        fillMode: Image.PreserveAspectFit
                        visible: Boolean(modelData.image)
                    }
                    Rectangle {
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: 58; height: 70; radius: 29
                        color: "#baa27a"
                        border.color: "#f1e2b8"
                        visible: !modelData.image
                        Label {
                            anchors.centerIn: parent
                            text: modelData.name.slice(0, 2).toUpperCase()
                            font.bold: true
                            color: "#1b2531"
                        }
                    }
                    Label {
                        anchors.bottom: parent.bottom
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: modelData.name
                        color: "#f4e7ca"
                        font.pixelSize: 14 * root.textScale
                    }
                }
            }
        }

        Rectangle {
            id: cinematicDialogue
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: cinematicControls.top
            anchors.leftMargin: 36; anchors.rightMargin: 36
            anchors.bottomMargin: 16
            height: 132
            color: "#121d2c"
            border.color: "#c1a878"
            border.width: 1
            radius: 8
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 17
                Label {
                    text: cinematicOverlay.frameData.speaker || cinematicOverlay.clip.title
                    font.bold: true
                    color: "#f5ca91"
                    font.pixelSize: 17 * root.textScale
                }
                Label {
                    text: cinematicOverlay.frameData.dialogue || "..."
                    color: "#f5ead5"
                    font.pixelSize: 18 * root.textScale
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                }
            }
        }

        Rectangle {
            anchors.fill: parent
            color: cinematicOverlay.frameData.transition === "dissolve" ? "#101a2b" : "#000000"
            opacity: Math.max(cinematicOverlay.frameData.transitionOpacity || 0,
                              cinematicOverlay.frameData.fadeOpacity || 0)
            visible: opacity > 0
        }

        RowLayout {
            id: cinematicControls
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: 25
            spacing: 14
            Button {
                objectName: "r20CinematicPause"
                text: cinematicOverlay.clip.playing ? "Pause" : "Lire"
                onClicked: cinematicOverlay.clip.playing ? player.cinematicPause() :
                           player.cinematicPlay()
            }
            Slider {
                id: cinematicSeek
                Layout.fillWidth: true
                from: 0
                to: cinematicOverlay.clip.durationMs || 1
                value: cinematicOverlay.frameData.timeMs || 0
                onMoved: player.cinematicSeek(Math.round(value))
            }
            Label {
                text: Math.round((cinematicOverlay.frameData.timeMs || 0)/1000) +
                      " / " + Math.round((cinematicOverlay.clip.durationMs || 0)/1000) + " s"
                color: "#f5ead5"
            }
            Button {
                objectName: "r20CinematicSkip"
                text: "Passer la cinématique  Esc"
                onClicked: player.cinematicSkip()
            }
        }
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
        width: Math.min(root.width - 36, 570)
        height: Math.min(root.height - 40, 690)
        padding: 20
        closePolicy: Popup.CloseOnEscape
        background: Rectangle {
            color: "#1e3039"
            border.color: "#819087"
            radius: 12
        }
        ColumnLayout {
            anchors.fill: parent
            spacing: 10
            Label {
                text: "OPTIONS DU PLAYER"
                color: root.gold
                font.bold: true
                font.pixelSize: 23 * root.textScale
            }
            Label {
                text: "Préférences conservées indépendamment de vos sauvegardes."
                color: root.muted
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                contentWidth: availableWidth
                ColumnLayout {
                    width: parent.width
                    spacing: 10
                    Label {
                        text: "AFFICHAGE ET ACCESSIBILITÉ"
                        color: root.gold
                        font.bold: true
                        font.letterSpacing: 1
                    }
                    Label { text: "Taille des textes"; color: root.ivory }
                    Slider {
                        id: scaleSlider
                        Layout.fillWidth: true
                        from: 0.85; to: 1.35; stepSize: 0.05
                        value: root.playerData.settings.display.text_scale
                        onPressedChanged: {
                            if (!pressed) player.setTextScale(Math.round(value * 20) / 20)
                        }
                    }
                    CheckBox {
                        text: "Contraste renforcé"
                        checked: root.highContrast
                        onClicked: player.setDisplayBool("high_contrast", checked)
                    }
                    CheckBox {
                        text: "Plein écran"
                        checked: root.playerData.settings.display.fullscreen
                        onClicked: player.setDisplayBool("fullscreen", checked)
                    }
                    CheckBox {
                        text: "Quadrillage de la carte"
                        checked: root.playerData.settings.display.show_grid
                        onClicked: player.setDisplayBool("show_grid", checked)
                    }
                    CheckBox {
                        text: "Afficher les hauteurs"
                        checked: root.playerData.settings.display.show_heights
                        onClicked: player.setDisplayBool("show_heights", checked)
                    }
                    Rectangle {
                        Layout.fillWidth: true; height: 1; color: "#556d6c"
                    }
                    Label {
                        text: "COMMANDES"
                        color: root.gold
                        font.bold: true
                        font.letterSpacing: 1
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Label {
                            text: "Disposition du clavier"
                            color: root.ivory
                            Layout.fillWidth: true
                        }
                        ComboBox {
                            model: ["azerty", "qwerty"]
                            currentIndex: root.playerData.settings.profile === "azerty" ? 0 : 1
                            onActivated: player.selectProfile(currentText)
                        }
                    }
                    Label {
                        text: "Les flèches restent disponibles pour les déplacements. Un raccourci ne peut pas être utilisé deux fois dans le même contexte."
                        color: root.muted
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                    Repeater {
                        model: root.playerData.settings.rows
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            Label {
                                text: modelData.label
                                color: root.ivory
                                font.pixelSize: 13 * root.textScale
                                Layout.fillWidth: true
                            }
                            ComboBox {
                                Layout.preferredWidth: 150
                                model: root.playerData.settings.keyChoices
                                currentIndex: root.playerData.settings.keyChoices.indexOf(modelData.key)
                                onActivated: player.rebind(modelData.action, currentText)
                            }
                        }
                    }
                    Button {
                        text: "Réinitialiser les touches de ce profil"
                        Layout.fillWidth: true
                        onClicked: player.resetBindings()
                    }
                }
            }
            Label {
                text: root.playerData.message || ""
                color: root.gold
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                visible: text.length > 0
            }
            Button {
                text: "Fermer"
                Layout.alignment: Qt.AlignRight
                onClicked: optionsPopup.close()
            }
        }
    }
}
