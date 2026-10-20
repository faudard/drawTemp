import QtQuick
import QtQuick.Controls

// Shared Player/Studio Qt Quick component. The Studio uses QQuickWidget;
// the standalone Player uses the exact same file inside its QML scene.
Item {
    id: canvas
    property var projection: ({})
    property bool allowActions: false
    property var permittedActions: []
    property bool highContrast: false
    property real textScale: 1.0
    signal intent(string action)
    property string focusedWidgetId: ""
    // Traverse the actual Qt Quick item tree: Repeater delegates are not
    // necessarily QObject children of ApplicationWindow.
    function findWidget(item, identifier) {
        if (!item) return null
        if (item.objectName === "r51-widget-" + identifier)
            return item
        var children = item.childItems || []
        for (var i = 0; i < children.length; ++i) {
            var found = findWidget(children[i], identifier)
            if (found) return found
        }
        return null
    }
    function shiftFocus(direction) {
        var order = projection.focus_order || []
        if (!allowActions || order.length === 0) return false
        var current = order.indexOf(focusedWidgetId)
        if (current === -1 && direction < 0) current = 0
        for (var i = 1; i <= order.length; ++i) {
            var next = (current + i * direction) % order.length
            if (next < 0) next += order.length
            var target = findWidget(tree, order[next])
            if (target && target.enabled && target.visible) {
                target.forceActiveFocus(Qt.TabFocusReason)
                focusedWidgetId = order[next]
                return true
            }
        }
        return false
    }
    implicitWidth: 340
    implicitHeight: 210

    Rectangle {
        anchors.fill: parent
        radius: 12
        color: canvas.highContrast ? "#000000" : "#202d3b"
        border.color: canvas.highContrast ? "#ffffff" : "#73818d"
        border.width: canvas.highContrast ? 2 : 1
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
            permittedActions: canvas.permittedActions
            highContrast: canvas.highContrast
            textScale: canvas.textScale
            onIntent: function(action) { canvas.intent(action) }
            onFocusMove: function(direction) { canvas.shiftFocus(direction) }
            onWidgetFocused: function(widgetId) { canvas.focusedWidgetId = widgetId }
        }
    }
}
