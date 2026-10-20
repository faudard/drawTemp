import QtQuick

// R68.B1: optional on-screen touch controls over the EXISTING Qt Quick Player.
// Demonstrates multi-touch input; it is not an Android package or certification.
// Centers here intentionally mirror drawtemp.player.r68_touch._ACTION_CENTERS.
Item {
    id: pad
    signal samples(var points, int viewportWidth, int viewportHeight)
    signal cleared()

    property var activePoints: ({})

    function emitPoints() {
        var points = []
        for (var key in activePoints)
            points.push(activePoints[key])
        samples(points, Math.round(width), Math.round(height))
    }

    function track(points, replace) {
        var next = ({})
        if (!replace) {
            for (var key in activePoints)
                next[key] = activePoints[key]
        }
        for (var i = 0; i < points.length; i++) {
            var point = points[i]
            next[String(point.pointId)] = {
                "id": point.pointId, "x": point.x, "y": point.y
            }
        }
        activePoints = next
        emitPoints()
    }

    function drop(points) {
        var next = ({})
        for (var key in activePoints)
            next[key] = activePoints[key]
        for (var i = 0; i < points.length; i++)
            delete next[String(points[i].pointId)]
        activePoints = next
        emitPoints()
    }

    function clear() {
        activePoints = ({})
        cleared()
    }

    Rectangle {
        width: Math.min(156, parent.width * .34)
        height: width
        x: parent.width * .20 - width / 2
        y: parent.height * .75 - height / 2
        radius: width / 2
        color: "#803b5760"
        border.width: 2
        border.color: "#ccd9e7"
        Text {
            anchors.centerIn: parent
            text: "↑\n←   →\n↓"
            color: "white"
            font.pixelSize: 23
            horizontalAlignment: Text.AlignHCenter
        }
    }
    Repeater {
        model: [
            {"name":"UTIL.", "cx":.67, "cy":.59},
            {"name":"ATTAQ.", "cx":.84, "cy":.63},
            {"name":"GARDE", "cx":.67, "cy":.83},
            {"name":"ESQUIVE", "cx":.85, "cy":.86}
        ]
        delegate: Rectangle {
            required property var modelData
            width: Math.min(108, Math.max(65, pad.width * .14))
            height: Math.min(108, Math.max(65, pad.height * .18))
            x: pad.width * modelData.cx - width / 2
            y: pad.height * modelData.cy - height / 2
            radius: Math.min(width, height) / 2
            color: "#a0375c6d"
            border.color: "#edf8fb"
            border.width: 2
            Text {
                anchors.centerIn: parent
                text: modelData.name
                color: "#ffffff"
                font.bold: true
                font.pixelSize: 13
            }
        }
    }
    MultiPointTouchArea {
        anchors.fill: parent
        minimumTouchPoints: 1
        maximumTouchPoints: 10
        mouseEnabled: true
        onPressed: function(points) { pad.track(points, false) }
        onUpdated: function(points) { pad.track(points, false) }
        onTouchUpdated: function(points) { pad.track(points, true) }
        onReleased: function(points) { pad.drop(points) }
        onCanceled: function(points) { pad.clear() }
    }
}
