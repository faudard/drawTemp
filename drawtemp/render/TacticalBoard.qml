import QtQuick
import QtQuick.Shapes

// R12 adds an overlay on the exact R3 isometric projection. R3 still owns
// terrain, actors, camera, zoom and hit-testing; no second tile renderer.
IsoViewport {
    id: board
    property var battle: ({})
    property var exploration: ({})
    property var selected: [0, 0]
    property var tactical: ({})
    property bool showTacticalOverlay: true
    readonly property real zoom: renderer.cameraState.zoom
    interactionMode: "select"
    showLegend: false
    // R3.C repositions the *actual* atlas/actor delegate, not a duplicate ghost.
    activeVisualClip: board.playing ? board.currentClip : ({})
    activeVisualPhase: board.phase

    // R12.7: animation clips represent *committed* GameSession events. The
    // R3 scene is already authoritative at the final state; this temporary
    // ghost is not a second actor nor a second game clock.
    property var animationPlan: ({serial: 0, clips: []})
    property var currentClip: ({})
    property int runningSerial: -1
    property int clipIndex: -1
    property bool playing: false
    property real phase: 0

    function beginPlan() {
        if (!animationPlan || animationPlan.serial === runningSerial)
            return
        runningSerial = animationPlan.serial
        playing = false
        tween.stop()
        concealedActorIds = []
        clipIndex = -1
        currentClip = ({})
        if (animationPlan.clips && animationPlan.clips.length > 0)
            nextClip()
    }

    function nextClip() {
        // A new scene, save/load, or player action resets the serial and
        // immediately discards any callbacks from an older plan.
        if (!animationPlan || runningSerial !== animationPlan.serial) {
            playing = false
            concealedActorIds = []
            return
        }
        clipIndex += 1
        if (!animationPlan.clips || clipIndex >= animationPlan.clips.length) {
            playing = false
            concealedActorIds = []
            currentClip = ({})
            return
        }
        currentClip = animationPlan.clips[clipIndex]
        phase = 0
        playing = true
        // For a real hit pose also hide the idle frame, preventing double
        // Jeanne on top of a genuine impact animation.
        var artHit = currentClip.kind === "impact" &&
                     !!renderer.animationFrame(currentClip.actor, "south", "hit", 0).imageUrl
        concealedActorIds = (currentClip.kind === "move" ||
                             currentClip.kind === "attack" || artHit) ?
                             [currentClip.actor] : []
        tween.duration = currentClip.duration_ms
        tween.restart()
    }

    onAnimationPlanChanged: beginPlan()
    Component.onCompleted: beginPlan()
    NumberAnimation {
        id: tween
        target: board
        property: "phase"
        from: 0
        to: 1
        duration: 250
        easing.type: Easing.InOutCubic
        onStopped: {
            if (board.playing && board.runningSerial === board.animationPlan.serial)
                board.nextClip()
        }
    }

    function elevation(point) {
        if (!point || !battle || !battle.tiles) return 0
        for (var i = 0; i < battle.tiles.length; ++i) {
            var t = battle.tiles[i]
            if (t.pos[0] === Math.round(point[0]) &&
                t.pos[1] === Math.round(point[1]))
                return t.height || 0
        }
        return 0
    }
    function clipCell() {
        if (!playing || !currentClip.start) return [0, 0]
        var start = currentClip.start
        var end = currentClip.end || start
        var fraction = currentClip.kind === "move" ? phase :
                       currentClip.kind === "attack" ?
                           0.25 * Math.sin(Math.PI * phase) : 0
        return [start[0] + (end[0] - start[0]) * fraction,
                start[1] + (end[1] - start[1]) * fraction]
    }
    function scenePoint(point) {
        var zoom = renderer.cameraState.zoom
        return [board.width / 2 + renderer.cameraState.panX +
                (point[0] - point[1]) * 48 * zoom,
                board.height / 2 + renderer.cameraState.panY +
                ((point[0] + point[1]) * 24 - elevation(point) * 12) * zoom]
    }

    // No separate fake character: R3's Image/actor node follows the same
    // validated R12 animation clip while remaining at the correct feet depth.

    // The exact R4 asset frames are resolved by the R3 renderer. Movement
    // and attacks use their authored directional poses; missing bindings keep
    // the original abstract silhouette, never guess another character's art.
    function actionDirection() {
        if (!currentClip.start || !currentClip.end) return "south"
        var dx = currentClip.end[0] - currentClip.start[0]
        var dy = currentClip.end[1] - currentClip.start[1]
        if (Math.abs(dx) > Math.abs(dy)) return dx >= 0 ? "east" : "west"
        if (Math.abs(dy) > 0) return dy >= 0 ? "south" : "north"
        return "south"
    }
    function actionPose() {
        if (currentClip.kind === "move") return "move"
        if (currentClip.kind === "attack" || currentClip.kind === "cast") return "attack"
        if (currentClip.kind === "impact") return "hit"
        return "idle"
    }

    Item {
        id: motionGhost
        objectName: "r12-motion-ghost"
        readonly property var sprite:
            board.playing && board.currentClip.actor ?
            renderer.animationFrame(board.currentClip.actor,
                                    board.actionDirection(), board.actionPose(),
                                    Math.floor(board.phase *
                                               (board.currentClip.duration_ms || 250))) : ({})
        readonly property bool hasArt: !!sprite.imageUrl
        visible: board.playing &&
                 (board.currentClip.kind === "move" ||
                  board.currentClip.kind === "attack" ||
                  (board.currentClip.kind === "impact" && hasArt))
        readonly property var pos: board.scenePoint(board.clipCell())
        readonly property real ratio: renderer.cameraState.zoom
        x: pos[0] - (hasArt ? sprite.pivotX : 20) * ratio
        y: pos[1] - (hasArt ? sprite.pivotY : 68) * ratio
        width: (hasArt ? sprite.frameWidth : 40) * ratio
        height: (hasArt ? sprite.frameHeight : 68) * ratio
        z: (board.clipCell()[0] + board.clipCell()[1]) * 100 + 75
        Image {
            id: actionSprite
            objectName: "r12-action-sprite"
            anchors.fill: parent
            visible: motionGhost.hasArt && status !== Image.Error
            source: motionGhost.hasArt ? motionGhost.sprite.imageUrl : ""
            sourceClipRect: motionGhost.hasArt ?
               Qt.rect(motionGhost.sprite.atlasX, motionGhost.sprite.atlasY,
                       motionGhost.sprite.frameWidth, motionGhost.sprite.frameHeight) :
               Qt.rect(0, 0, 0, 0)
            fillMode: Image.Stretch
            smooth: false
            asynchronous: false
            cache: true
        }
        Rectangle {
            visible: !motionGhost.hasArt || actionSprite.status === Image.Error
            x: 3 * motionGhost.ratio
            y: 57 * motionGhost.ratio
            width: 34 * motionGhost.ratio
            height: 9 * motionGhost.ratio
            radius: 5 * motionGhost.ratio
            color: "#10191c"
            opacity: 0.45
        }
        Rectangle {
            visible: !motionGhost.hasArt || actionSprite.status === Image.Error
            x: 6 * motionGhost.ratio
            y: 19 * motionGhost.ratio
            width: 28 * motionGhost.ratio
            height: 38 * motionGhost.ratio
            radius: 9 * motionGhost.ratio
            color: board.currentClip.team === "enemy" ? "#af6556" : "#496cbb"
            border.width: 2 * motionGhost.ratio
            border.color: "#e2d7c4"
        }
        Rectangle {
            visible: !motionGhost.hasArt || actionSprite.status === Image.Error
            x: 10 * motionGhost.ratio
            y: 5 * motionGhost.ratio
            width: 19 * motionGhost.ratio
            height: 19 * motionGhost.ratio
            radius: 10 * motionGhost.ratio
            color: "#eacaa1"
            border.color: "#62504b"
        }
        Rectangle {
            visible: (!motionGhost.hasArt || actionSprite.status === Image.Error) &&
                     board.currentClip.kind === "attack"
            x: 28 * motionGhost.ratio
            y: 20 * motionGhost.ratio
            width: 23 * motionGhost.ratio
            height: 4 * motionGhost.ratio
            color: "#efddb7"
            rotation: -25
            opacity: 0.6 + 0.4 * Math.sin(Math.PI * board.phase)
        }
    }

    Item {
        id: impactVisual
        objectName: "r12-impact-effect"
        visible: board.playing && ["impact", "heal", "miss", "cast",
                                    "interrupt"].indexOf(board.currentClip.kind) >= 0
        readonly property var position: board.scenePoint(board.currentClip.start || [0, 0])
        readonly property real ratio: renderer.cameraState.zoom
        readonly property bool healing: board.currentClip.kind === "heal"
        readonly property color accent: healing ? "#8cdbad" :
                                       board.currentClip.kind === "miss" ? "#d9d7c7" :
                                       board.currentClip.kind === "cast" ? "#b3a0ea" :
                                       board.currentClip.kind === "interrupt" ? "#e3b66e" :
                                       "#f47b5d"
        x: position[0] - 25 * ratio
        y: position[1] - 50 * ratio
        width: 50 * ratio
        height: 50 * ratio
        z: 99999
        opacity: 1 - board.phase
        Rectangle {
            anchors.centerIn: parent
            width: parent.width * (0.4 + 0.6 * board.phase)
            height: width
            radius: width / 2
            color: "transparent"
            border.width: 3 * impactVisual.ratio
            border.color: impactVisual.accent
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            y: -18 * impactVisual.ratio - board.phase * 22 * impactVisual.ratio
            text: board.currentClip.kind === "impact" ?
                      "−" + (board.currentClip.amount === null ? "!" : board.currentClip.amount) :
                  board.currentClip.kind === "heal" ?
                      "+" + (board.currentClip.amount === null ? "♥" : board.currentClip.amount) :
                  board.currentClip.kind === "miss" ? "ESQUIVE" :
                  board.currentClip.kind === "interrupt" ? "INTERROMPU" : "SORT"
            color: impactVisual.accent
            font.bold: true
            font.pixelSize: Math.max(12, 16 * impactVisual.ratio)
            style: Text.Outline
            styleColor: "#202730"
        }
    }

    Repeater {
        model: board.showTacticalOverlay && board.tactical && board.tactical.markers ?
                   board.tactical.markers : []
        delegate: Item {
            id: highlight
            required property var modelData
            readonly property real ratio: renderer.cameraState.zoom
            readonly property int cellX: modelData.x
            readonly property int cellY: modelData.y
            width: 96 * ratio
            height: 48 * ratio
            x: board.width / 2 + renderer.cameraState.panX +
               (cellX - cellY) * 48 * ratio - 48 * ratio
            y: board.height / 2 + renderer.cameraState.panY +
               ((cellX + cellY) * 24 - (modelData.height || 0) * 12) * ratio -
               24 * ratio
            z: (cellX + cellY) * 100 + 12
            visible: x + width > 0 && y + height > 0 &&
                     x < board.width && y < board.height

            readonly property color tint:
                modelData.kind === "hazard" ? "#df6e44" :
                modelData.kind === "prepared" ? "#dc636b" :
                modelData.kind === "cast" ? "#b678d6" :
                modelData.kind === "charge" ? "#ebbb63" : "#6fcdbd"
            Shape {
                anchors.fill: parent
                ShapePath {
                    strokeColor: highlight.tint
                    strokeWidth: Math.max(1, 2 * highlight.ratio)
                    // Unknown enemy charges remain dashed/low-opacity overlays.
                    strokeStyle: highlight.modelData.certainty === "possible" ?
                                     ShapePath.DashLine : ShapePath.SolidLine
                    fillColor: highlight.modelData.kind === "reachable" ?
                                   "#186fcdbd" : "#32da6e44"
                    startX: highlight.width / 2; startY: 0
                    PathLine { x: highlight.width; y: highlight.height / 2 }
                    PathLine { x: highlight.width / 2; y: highlight.height }
                    PathLine { x: 0; y: highlight.height / 2 }
                    PathLine { x: highlight.width / 2; y: 0 }
                }
            }
        }
    }
}
