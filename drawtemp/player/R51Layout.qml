import QtQuick
import QtQuick.Controls

// Shared Player/Studio Qt Quick component. The Studio uses QQuickWidget;
// the standalone Player uses the exact same file inside its QML scene.
Item {
    id: canvas
    property var projection: ({})
    property bool allowActions: false
    signal intent(string action)
    implicitWidth: 340
    implicitHeight: 210

    Rectangle {
        anchors.fill: parent
        radius: 12
        color: "#202d3b"
        border.color: "#73818d"
    }
    ScrollView {
        anchors.fill: parent
        anchors.margins: 14
        clip: true
        R51Node {
            id: tree
            spec: canvas.projection.root || {
                "id": "empty", "type": "text",
                "text": "Aucun layout à prévisualiser"
            }
            responsiveColumns: Math.max(1, Number(canvas.projection.columns || 1))
            allowActions: canvas.allowActions
            onIntent: function(action) { canvas.intent(action) }
        }
    }
}
