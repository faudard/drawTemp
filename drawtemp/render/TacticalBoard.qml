import QtQuick

// Shared Qt Quick scene-graph boundary used by the Player (and future Studio).
// Terrain and unit positions come from Simulation snapshots, never a parallel map.
Item {
    id: board
    property var battle: ({})
    property var exploration: ({})
    property var selected: [0, 0]
    property real zoom: 1.0
    signal cellSelected(int x, int y)

    readonly property bool exploring: exploration && exploration.width > 0
    readonly property int cols: exploring ? exploration.width : (battle.width || 0)
    readonly property int rows: exploring ? exploration.height : (battle.height || 0)
    readonly property real halfW: 30 * zoom
    readonly property real halfH: 15 * zoom
    readonly property real originX: width * 0.5
    readonly property real originY: Math.max(80, height * 0.5 - (cols + rows) * halfH * 0.5)

    function at(x, y) {
        return [originX + (x - y) * halfW,
                originY + (x + y) * halfH]
    }

    function tileFromPointer(px, py) {
        var u = (px - originX) / halfW
        var v = (py - originY) / halfH
        return [Math.round((u + v) / 2), Math.round((v - u) / 2)]
    }

    onBattleChanged: scene.requestPaint()
    onExplorationChanged: scene.requestPaint()
    onSelectedChanged: scene.requestPaint()
    onZoomChanged: scene.requestPaint()
    onWidthChanged: scene.requestPaint()
    onHeightChanged: scene.requestPaint()

    Canvas {
        id: scene
        anchors.fill: parent
        antialiasing: true
        onPaint: {
            var g = getContext("2d")
            g.clearRect(0, 0, width, height)
            if (board.cols < 1 || board.rows < 1)
                return

            var tiles = (board.battle && board.battle.tiles) || []
            var lookup = {}
            for (var t = 0; t < tiles.length; ++t) {
                var tile = tiles[t]
                lookup[tile.pos[0] + "," + tile.pos[1]] = tile
            }
            var blocked = {}
            if (board.exploring) {
                var walls = board.exploration.blocked || []
                for (var k = 0; k < walls.length; ++k)
                    blocked[walls[k][0] + "," + walls[k][1]] = true
            }
            var color = {
                grass: "#56765b", dirt: "#967958", sand: "#b6a17a",
                stone: "#747778", cobble: "#858986", water: "#375a75",
                road: "#9a8064", rock: "#5d6765"
            }
            // Painter traversal is diagonal; actors appear over their own ground.
            for (var depth = 0; depth <= board.cols + board.rows - 2; ++depth) {
                for (var x = 0; x < board.cols; ++x) {
                    var y = depth - x
                    if (y < 0 || y >= board.rows) continue
                    var p = board.at(x, y)
                    var data = lookup[x + "," + y] || {}
                    var isBlocked = blocked[x + "," + y] || data.blocked
                    var current = board.selected && board.selected[0] === x && board.selected[1] === y
                    var terrain = String(data.surface || "grass").toLowerCase()
                    g.beginPath()
                    g.moveTo(p[0], p[1] - board.halfH)
                    g.lineTo(p[0] + board.halfW, p[1])
                    g.lineTo(p[0], p[1] + board.halfH)
                    g.lineTo(p[0] - board.halfW, p[1])
                    g.closePath()
                    g.fillStyle = isBlocked ? "#495254" : (color[terrain] || "#61735e")
                    g.fill()
                    g.strokeStyle = current ? "#fbd284" : "#283c39"
                    g.lineWidth = current ? 3 : 1
                    g.stroke()
                    if (data.feature || isBlocked) {
                        g.fillStyle = isBlocked ? "#273d3d" : "#b1bc8e"
                        g.fillRect(p[0] - 4 * board.zoom, p[1] - 11 * board.zoom,
                                   8 * board.zoom, 9 * board.zoom)
                    }
                }
            }
            var actors = board.exploring ? [{
                id: "Jeanne", team: "player", pos: board.exploration.position
            }] : (board.battle.units || [])
            if (board.exploring)
                actors = actors.concat(board.exploration.actors || [])
            for (var a = 0; a < actors.length; ++a) {
                var actor = actors[a]
                if (!actor.pos) continue
                var center = board.at(actor.pos[0], actor.pos[1])
                var radius = 9 * board.zoom
                g.beginPath()
                g.arc(center[0], center[1] - 11 * board.zoom, radius, 0, Math.PI * 2)
                g.fillStyle = actor.team === "enemy" ? "#c96059" : "#f3d9a1"
                g.fill()
                g.strokeStyle = "#28313e"
                g.lineWidth = 2
                g.stroke()
                g.fillStyle = "#f4f0dc"
                g.textAlign = "center"
                g.font = "bold " + Math.max(10, 11 * board.zoom) + "px sans-serif"
                g.fillText(actor.name || actor.id || "?", center[0],
                           center[1] - 24 * board.zoom)
            }
            if (board.exploring) {
                var points = board.exploration.interactions || []
                for (var n = 0; n < points.length; ++n) {
                    var point = points[n]
                    if (!point.pos) continue
                    var q = board.at(point.pos[0], point.pos[1])
                    g.fillStyle = point.visited ? "#9ea99f" : "#ffd48b"
                    g.fillRect(q[0] - 4, q[1] - 20 * board.zoom, 8, 8)
                }
            }
        }
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton
        onClicked: function(mouse) {
            var cell = board.tileFromPointer(mouse.x, mouse.y)
            if (cell[0] >= 0 && cell[0] < board.cols &&
                cell[1] >= 0 && cell[1] < board.rows)
                board.cellSelected(cell[0], cell[1])
        }
        onWheel: function(wheel) {
            board.zoom = Math.min(2.0, Math.max(0.65,
                         board.zoom + (wheel.angleDelta.y > 0 ? 0.1 : -0.1)))
        }
    }
}
