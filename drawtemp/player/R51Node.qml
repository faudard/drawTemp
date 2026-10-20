import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Presentation-only recursive node. Types and bindings are validated in Python.
// Text is always plain text; arbitrary authored QML/JS is never evaluated.
Item {
    id: nodeItem
    property var spec: ({})
    property int responsiveColumns: 1
    property bool allowActions: false
    property var permittedActions: []
    property bool highContrast: false
    property real textScale: 1.0
    signal intent(string action)
    signal focusMove(int direction)
    signal widgetFocused(string widgetId)

    implicitWidth: body.implicitWidth
    implicitHeight: body.implicitHeight
    width: implicitWidth
    height: implicitHeight

    Loader {
        id: body
        width: parent.width
        sourceComponent: nodeItem.spec.type === "row" ? rowView :
                         nodeItem.spec.type === "column" ? columnView :
                         nodeItem.spec.type === "button" ? buttonView :
                         nodeItem.spec.type === "gauge" ? gaugeView : textView
    }
    Component {
        id: rowView
        RowLayout {
            spacing: 10
            Repeater {
                model: nodeItem.spec.children || []
                delegate: R51Node {
                    spec: modelData
                    responsiveColumns: 1
                    allowActions: nodeItem.allowActions
                    permittedActions: nodeItem.permittedActions
                    highContrast: nodeItem.highContrast
                    textScale: nodeItem.textScale
                    onIntent: function(action) { nodeItem.intent(action) }
                    onFocusMove: function(direction) { nodeItem.focusMove(direction) }
                    onWidgetFocused: function(widgetId) { nodeItem.widgetFocused(widgetId) }
                }
            }
        }
    }
    Component {
        id: columnView
        GridLayout {
            columns: Math.max(1, nodeItem.responsiveColumns)
            rowSpacing: 12
            columnSpacing: 16
            Repeater {
                model: nodeItem.spec.children || []
                delegate: R51Node {
                    spec: modelData
                    responsiveColumns: 1
                    allowActions: nodeItem.allowActions
                    permittedActions: nodeItem.permittedActions
                    highContrast: nodeItem.highContrast
                    textScale: nodeItem.textScale
                    onIntent: function(action) { nodeItem.intent(action) }
                    onFocusMove: function(direction) { nodeItem.focusMove(direction) }
                    onWidgetFocused: function(widgetId) { nodeItem.widgetFocused(widgetId) }
                }
            }
        }
    }
    Component {
        id: textView
        Label {
            objectName: "r51-widget-" + nodeItem.spec.id
            color: nodeItem.highContrast ? "#ffffff" : "#f2f2f2"
            textFormat: Text.PlainText
            text: nodeItem.spec.value === undefined ?
                  (nodeItem.spec.text || "") : String(nodeItem.spec.value)
            wrapMode: Text.Wrap
            font.pixelSize: Math.round(15 * Math.max(0.85, Math.min(1.35, nodeItem.textScale)))
            Accessible.name: text
        }
    }
    Component {
        id: buttonView
        Button {
            objectName: "r51-widget-" + nodeItem.spec.id
            text: nodeItem.spec.text || ""
            enabled: nodeItem.allowActions &&
                     nodeItem.permittedActions.indexOf(nodeItem.spec.action) !== -1
            activeFocusOnTab: true
            implicitHeight: Math.max(44, contentItem.implicitHeight + topPadding + bottomPadding)
            font.pixelSize: Math.round(15 * Math.max(0.85, Math.min(1.35, nodeItem.textScale)))
            Accessible.name: text
            Accessible.description: enabled ?
                ("Action : " + nodeItem.spec.action) :
                ("Action indisponible : " + nodeItem.spec.action)
            background: Rectangle {
                radius: 6
                color: nodeItem.highContrast ? "#000000" : "#32465d"
                border.width: parent.activeFocus ? 3 : (nodeItem.highContrast ? 2 : 1)
                border.color: nodeItem.highContrast ? "#ffffff" :
                              (parent.activeFocus ? "#e7c78b" : "#9eacbe")
            }
            onClicked: nodeItem.intent(nodeItem.spec.action)
            onActiveFocusChanged: {
                if (activeFocus) nodeItem.widgetFocused(nodeItem.spec.id)
            }
            Keys.onPressed: function(event) {
                if (!enabled) return
                if (event.key === Qt.Key_Down || event.key === Qt.Key_Right ||
                    event.key === Qt.Key_Tab) {
                    nodeItem.focusMove(1)
                    event.accepted = true
                } else if (event.key === Qt.Key_Up || event.key === Qt.Key_Left ||
                           event.key === Qt.Key_Backtab) {
                    nodeItem.focusMove(-1)
                    event.accepted = true
                }
            }
        }
    }
    Component {
        id: gaugeView
        ColumnLayout {
            spacing: 4
            Label {
                color: nodeItem.highContrast ? "#ffffff" : "#f2f2f2"
                font.pixelSize: Math.round(15 * Math.max(0.85, Math.min(1.35, nodeItem.textScale)))
                textFormat: Text.PlainText
                text: String(nodeItem.spec.value || 0) + " / " +
                      String(nodeItem.spec.max_value || 0)
            }
            ProgressBar {
                objectName: "r51-widget-" + nodeItem.spec.id
                from: 0
                to: Math.max(1, Number(nodeItem.spec.max_value || 0))
                value: Math.max(0, Number(nodeItem.spec.value || 0))
                Layout.preferredWidth: 180
                Accessible.name: "Jauge de progression : " +
                                 String(nodeItem.spec.value || 0) + " sur " +
                                 String(nodeItem.spec.max_value || 0)
            }
        }
    }
}
