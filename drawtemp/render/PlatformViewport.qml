import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// R40.B.5: side-view presentation of the canonical R32 PlatformPhysics
// snapshot. The Canvas paints authored AABBs only; no scene physics, AI,
// physics timer, reward, quest ledger or save state exists in QML.
Item {
    id: root
    objectName: "r40PlatformViewport"
    property var platform: ({})
    property bool suspended: false
    property bool smokeMode: false
    property bool leftHeld: false
    property bool rightHeld: false
    property bool jumpHeld: false
    property bool attackHeld: false
    readonly property var world: platform.world || ({})
    readonly property var game: platform.state || ({})
    readonly property var boss: game.boss || ({})
    readonly property bool lost: !!boss.player_defeated
    readonly property bool won: !!boss.defeated
    signal pulse(int move, bool jump, bool attack)
    signal travel(string linkId)
    signal resetClock()

    focus: visible && !smokeMode
    onVisibleChanged: {
        leftHeld = false
        rightHeld = false
        jumpHeld = false
        attackHeld = false
        resetClock()
        if (visible && !smokeMode) forceActiveFocus()
    }
    onSuspendedChanged: resetClock()
    onPlatformChanged: worldCanvas.requestPaint()

    Keys.onPressed: function(event) {
        if (root.suspended || root.smokeMode || root.lost || root.won)
            return
        if (event.key === Qt.Key_A || event.key === Qt.Key_Left)
            root.leftHeld = true
        else if (event.key === Qt.Key_D || event.key === Qt.Key_Right)
            root.rightHeld = true
        else if (event.key === Qt.Key_Space)
            root.jumpHeld = true
        else if (event.key === Qt.Key_F)
            root.attackHeld = true
        else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            if (!event.isAutoRepeat && root.game.available_routes &&
                    root.game.available_routes.length)
                root.travel(root.game.available_routes[0])
        } else return
        event.accepted = true
    }
    Keys.onReleased: function(event) {
        if (event.key === Qt.Key_A || event.key === Qt.Key_Left)
            root.leftHeld = false
        else if (event.key === Qt.Key_D || event.key === Qt.Key_Right)
            root.rightHeld = false
        else if (event.key === Qt.Key_Space)
            root.jumpHeld = false
        else if (event.key === Qt.Key_F)
            root.attackHeld = false
        else return
        event.accepted = true
    }

    Timer {
        id: fixedPulse
        interval: 16
        repeat: true
        running: root.visible && !root.suspended && !root.smokeMode &&
                 !root.lost && !root.won
        onTriggered: {
            // Python ActionStepClock accumulates monotonic nanoseconds and
            // decides how many logical 60 Hz R32 ticks are due. A QML render
            // pulse itself is never treated as an authoritative physics tick.
            var move = Number(root.rightHeld || rightControl.down) -
                       Number(root.leftHeld || leftControl.down)
            root.pulse(move,
                       root.jumpHeld || jumpControl.down,
                       root.attackHeld || attackControl.down)
        }
    }

    Rectangle {
        anchors.fill: parent
        radius: 8
        color: "#132331"
        border.color: "#546a75"
    }

    Canvas {
        id: worldCanvas
        objectName: "r40PlatformCanvas"
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: commands.top
        anchors.margins: 10
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()

        onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            ctx.fillStyle = "#142735"
            ctx.fillRect(0, 0, width, height)
            if (!root.world.width || !root.world.height || !root.game.actor)
                return
            var sx = width / root.world.width
            var sy = height / root.world.height
            function block(rect, color) {
                ctx.fillStyle = color
                ctx.fillRect(rect[0] * sx, rect[1] * sy,
                             rect[2] * sx, rect[3] * sy)
            }
            var disabled = root.game.disabled_colliders || []
            var movers = root.game.movers || ({})
            var colliders = root.world.colliders || []
            for (var i = 0; i < colliders.length; ++i) {
                var row = colliders[i]
                if (disabled.indexOf(row.id) >= 0) continue
                var rect = row.rect.slice()
                if (movers[row.id]) rect[0] = movers[row.id].x
                block(rect, row.trigger ? "#9871c1" :
                            row.one_way ? "#54b8a5" : "#526c86")
            }
            if (root.boss.id && !root.boss.defeated) {
                if (root.boss.window === "telegraph")
                    block(root.boss.attack_rect, "rgba(244,177,60,0.30)")
                else if (root.boss.window === "strike")
                    block(root.boss.attack_rect, "rgba(224,64,65,0.45)")
                block(root.boss.rect,
                      root.boss.window === "recover" ? "#eeaf77" : "#b76d9c")
            }
            var actor = root.game.actor
            var size = root.world.hero.size
            block([actor.x, actor.y, size[0], size[1]], "#f4d283")
        }
    }

    ColumnLayout {
        id: commands
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 10
        spacing: 6
        Label {
            objectName: "r40PlatformStatus"
            Layout.fillWidth: true
            color: "#e8e0cf"
            wrapMode: Text.WordWrap
            text: root.boss.id ?
                  "GARDIEN · Phase " + root.boss.phase +
                  " · PV " + root.boss.hp + "/" + root.boss.max_hp +
                  " · Héros " + root.boss.hero_hp +
                  " · " + root.boss.window +
                  (root.won ? " · VICTOIRE" : root.lost ? " · DÉFAITE" : "") :
                  "Exploration physique 60 Hz · tick " + (root.game.tick || 0) +
                  (root.game.air_jumps_left !== undefined ?
                    " · sauts aériens : " + root.game.air_jumps_left : "")
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            Button {
                id: leftControl
                objectName: "r40PlatformLeft"
                text: "◀ Gauche"
                enabled: !root.suspended && !root.lost && !root.won
                Accessible.name: "Maintenir pour aller à gauche"
                Layout.fillWidth: true
            }
            Button {
                id: rightControl
                objectName: "r40PlatformRight"
                text: "Droite ▶"
                enabled: !root.suspended && !root.lost && !root.won
                Accessible.name: "Maintenir pour aller à droite"
                Layout.fillWidth: true
            }
            Button {
                id: jumpControl
                objectName: "r40PlatformJump"
                text: "Sauter"
                enabled: !root.suspended && !root.lost && !root.won
                Accessible.name: "Sauter ou double-sauter"
                Layout.fillWidth: true
            }
            Button {
                id: attackControl
                objectName: "r40PlatformAttack"
                text: "Attaquer"
                visible: !!root.boss.id
                enabled: !root.suspended && !root.lost && !root.won
                Accessible.name: "Frapper pendant la récupération du gardien"
                Layout.fillWidth: true
            }
        }
        Repeater {
            model: root.game.available_routes || []
            Button {
                objectName: "r40PhysicalPortal-" + modelData
                Layout.fillWidth: true
                text: "Emprunter le portail · " + modelData
                enabled: !root.suspended && !root.lost
                Accessible.description: "Passage physique valide : " + modelData
                onClicked: root.travel(modelData)
            }
        }
        Label {
            visible: root.lost
            color: "#f2adad"
            text: "Défaite : rechargez une sauvegarde antérieure ou commencez une nouvelle partie."
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
        }
    }
}
