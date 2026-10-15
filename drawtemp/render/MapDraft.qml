import QtQuick

// R5 preview viewport: temporary authoring canvas until the shared R3 GPU
// scene graph is merged. No project or terrain rules are duplicated in QML.
Rectangle {
    id: root
    color: "#161e2b"
    property real scaleFactor: 1
    property real panX: 0
    property real panY: 0
    property int hoveredX: -1
    property int hoveredY: -1
    property bool panning: false
    property real lastX: 0
    property real lastY: 0
    property var mapData: ({ width: 0, height: 0, tiles: [], units: [] })

    function refreshData() {
        try { mapData = JSON.parse(mapBridge.sceneJSON) }
        catch(e) { mapData = ({ width: 0, height: 0, tiles: [], units: [] }) }
        picture.requestPaint()
    }
    function tileWidth() { return 70 * scaleFactor }
    function tileHeight() { return 36 * scaleFactor }
    function originX() {
        return width / 2 - (mapData.width - mapData.height) * tileWidth() / 4 + panX
    }
    function originY() { return 68 + panY }
    function point(x, y) {
        return { x: originX() + (x-y)*tileWidth()/2,
                 y: originY() + (x+y)*tileHeight()/2 }
    }
    function cellAt(px, py) {
        const a = (px-originX()) / (tileWidth()/2)
        const b = (py-originY()) / (tileHeight()/2)
        const x = Math.round((a+b)/2)
        const y = Math.round((b-a)/2)
        if (x < 0 || y < 0 || x >= mapData.width || y >= mapData.height)
            return null
        return { x: x, y: y }
    }
    Component.onCompleted: refreshData()
    Connections {
        target: mapBridge
        function onSceneChanged() { root.refreshData() }
    }

    gradient: Gradient {
        GradientStop { position: 0.0; color: "#293e54" }
        GradientStop { position: 1.0; color: "#121b27" }
    }

    Canvas {
        id: picture
        anchors.fill: parent
        renderStrategy: Canvas.Cooperative
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            const ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            const w = root.tileWidth(), h = root.tileHeight()
            const colors = {
                grass: "#678f68", dirt: "#947753", sand: "#bcaa76",
                stone: "#838c91", cobble: "#9e9688", water: "#387d9c",
                bridge: "#a18a60", rock: "#6c6d75", snow: "#dadbd4",
                mud: "#696449", lava: "#bc5c33"
            }
            const tiles = root.mapData.tiles || []
            for (let i = 0; i < tiles.length; i++) {
                const t = tiles[i]
                const p = root.point(t.x, t.y)
                const top = p.y - h/2
                const base = colors[t.surface] || "#829482"
                const elev = Math.min(5, t.height || 0) * 3 * root.scaleFactor
                ctx.beginPath()
                ctx.moveTo(p.x, top-elev)
                ctx.lineTo(p.x+w/2, p.y-elev)
                ctx.lineTo(p.x, p.y+h/2-elev)
                ctx.lineTo(p.x-w/2, p.y-elev)
                ctx.closePath()
                ctx.fillStyle = base
                ctx.fill()
                if (root.mapData.grid) {
                    ctx.strokeStyle = "rgba(12,28,35,.30)"
                    ctx.lineWidth = 1
                    ctx.stroke()
                }
                if (t.surface === "water") {
                    ctx.strokeStyle = "rgba(186,226,238,.57)"
                    ctx.beginPath()
                    ctx.moveTo(p.x-w/6, p.y-3*root.scaleFactor)
                    ctx.lineTo(p.x+w/6, p.y-3*root.scaleFactor)
                    ctx.stroke()
                }
                if (t.surface === "bridge") {
                    ctx.lineWidth = 2
                    ctx.strokeStyle = "#584b36"
                    ctx.beginPath()
                    ctx.moveTo(p.x-w/3,p.y)
                    ctx.lineTo(p.x+w/3,p.y)
                    ctx.stroke()
                }
                if (t.feature === "tree") {
                    ctx.fillStyle = "#4b3529"
                    ctx.fillRect(p.x-3, p.y-h*.45-elev, 6, h*.40)
                    ctx.beginPath()
                    ctx.arc(p.x,p.y-h*.58-elev,h*.32,0,Math.PI*2)
                    ctx.fillStyle = "#3f7558"
                    ctx.fill()
                } else if (t.feature === "stone_wall") {
                    ctx.fillStyle = "#626b72"
                    ctx.fillRect(p.x-w*.24,p.y-h*.70-elev,w*.48,h*.4)
                    ctx.fillStyle = "#a8afb5"
                    ctx.fillRect(p.x-w*.24,p.y-h*.72-elev,w*.48,h*.12)
                }
                if (root.mapData.blocked && t.blocked) {
                    ctx.strokeStyle = "#e36b6b"
                    ctx.lineWidth = 2
                    ctx.strokeRect(p.x-5,p.y-5-elev,10,10)
                }
                if (root.mapData.heights && t.height > 0) {
                    ctx.fillStyle = "#ffffff"
                    ctx.font = "bold 10px sans-serif"
                    ctx.fillText(String(t.height),p.x+4,p.y-4-elev)
                }
                if (t.goal) {
                    ctx.fillStyle = "#efcf6d"
                    ctx.beginPath()
                    ctx.arc(p.x,p.y-5-elev,4.5,0,Math.PI*2)
                    ctx.fill()
                }
                if (t.hazard > 0) {
                    ctx.fillStyle = "#d87549"
                    ctx.fillRect(p.x-3,p.y-3-elev,6,6)
                }
            }
            const units = root.mapData.units || []
            for (let j = 0; j < units.length; j++) {
                const u = units[j]
                const p = root.point(u.pos[0],u.pos[1])
                ctx.fillStyle = "rgba(0,0,0,.3)"
                ctx.beginPath()
                ctx.arc(p.x,p.y+4,6,0,Math.PI*2)
                ctx.fill()
                ctx.fillStyle = u.team === "player" ? "#e0d2a2" : "#ce776c"
                ctx.beginPath()
                ctx.arc(p.x,p.y-17,9,0,Math.PI*2)
                ctx.fill()
                ctx.fillStyle = "#ffffff"
                ctx.font = "bold 11px sans-serif"
                ctx.textAlign = "center"
                ctx.fillText((u.name || u.id).slice(0,11),p.x,p.y-32)
                ctx.textAlign = "left"
            }
            if (root.hoveredX >= 0) {
                const p = root.point(root.hoveredX,root.hoveredY)
                ctx.beginPath()
                ctx.moveTo(p.x,p.y-h/2)
                ctx.lineTo(p.x+w/2,p.y)
                ctx.lineTo(p.x,p.y+h/2)
                ctx.lineTo(p.x-w/2,p.y)
                ctx.closePath()
                ctx.fillStyle = "rgba(245,211,116,.23)"
                ctx.fill()
                ctx.strokeStyle = "#f6d690"
                ctx.lineWidth = 2
                ctx.stroke()
            }
        }
    }

    MouseArea {
        id: surface
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onPressed: function(mouse) {
            root.panning = mouse.button === Qt.RightButton
            root.lastX = mouse.x
            root.lastY = mouse.y
            if (!root.panning) {
                const cell = root.cellAt(mouse.x,mouse.y)
                if (cell) mapBridge.begin(cell.x,cell.y)
            }
        }
        onPositionChanged: function(mouse) {
            if (root.panning) {
                root.panX += mouse.x-root.lastX
                root.panY += mouse.y-root.lastY
                root.lastX = mouse.x
                root.lastY = mouse.y
            }
            const cell = root.cellAt(mouse.x,mouse.y)
            root.hoveredX = cell ? cell.x : -1
            root.hoveredY = cell ? cell.y : -1
            if (pressed && !root.panning && cell) mapBridge.extend(cell.x,cell.y)
            picture.requestPaint()
        }
        onReleased: function(mouse) {
            if (!root.panning) {
                const cell = root.cellAt(mouse.x,mouse.y)
                if (cell) mapBridge.finish(cell.x,cell.y)
                else if (root.hoveredX >= 0) mapBridge.finish(root.hoveredX,root.hoveredY)
            }
            root.panning = false
        }
        onWheel: function(wheel) {
            const factor = wheel.angleDelta.y > 0 ? 1.12 : 1 / 1.12
            root.scaleFactor = Math.max(.5,Math.min(2.5,root.scaleFactor*factor))
            picture.requestPaint()
        }
    }
    Rectangle {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.margins: 14
        color: "#263649"
        radius: 7
        width: legend.width + 22
        height: legend.height + 14
        opacity: .92
        Text {
            id: legend
            anchors.centerIn: parent
            color: "#e9e3d7"
            text: "CARTE ISOMÉTRIQUE   •   MOLETTE : ZOOM   •   CLIC DROIT : PAN"
            font.pixelSize: 11
            font.bold: true
        }
    }
}
