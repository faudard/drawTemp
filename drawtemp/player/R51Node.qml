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
    signal intent(string action)

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
                    onIntent: function(action) { nodeItem.intent(action) }
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
                    onIntent: function(action) { nodeItem.intent(action) }
                }
            }
        }
    }
    Component {
        id: textView
        Label {
            objectName: "r51-widget-" + nodeItem.spec.id
            color: "#f2f2f2"
            textFormat: Text.PlainText
            text: nodeItem.spec.value === undefined ?
                  (nodeItem.spec.text || "") : String(nodeItem.spec.value)
            wrapMode: Text.Wrap
            font.pixelSize: 15
            Accessible.name: text
        }
    }
    Component {
        id: buttonView
        Button {
            objectName: "r51-widget-" + nodeItem.spec.id
            text: nodeItem.spec.text || ""
            enabled: nodeItem.allowActions
            activeFocusOnTab: true
            Accessible.name: text
            onClicked: nodeItem.intent(nodeItem.spec.action)
        }
    }
    Component {
        id: gaugeView
        ColumnLayout {
            spacing: 4
            Label {
                color: "#f2f2f2"
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
                Accessible.name: "Jauge de progression"
            }
        }
    }
}
