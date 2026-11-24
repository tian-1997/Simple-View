import QtQuick
import QtQuick.Shapes

// 统一线性功能图标：24 视图盒手写路径，不依赖系统字体图标（缺字体会变豆腐块）
Item {
    id: root

    property string name: "bell"
    property color color: "#FFFFFF"
    property real size: 16
    property real strokeWidth: 1.6

    implicitWidth: size
    implicitHeight: size

    readonly property var _paths: ({
        bell: [
            "M12 3.3a5.1 5.1 0 0 0-5.1 5.1v3.4L5.1 15.4h13.8l-1.8-3.6V8.4A5.1 5.1 0 0 0 12 3.3Z",
            "M10.2 17.8a1.9 1.9 0 0 0 3.6 0"
        ],
        chevron: ["M6.6 9.6 12 15l5.4-5.4"],
        chevronRight: ["M10 7.4 14.6 12 10 16.6"],
        moon: ["M20.3 14.7A8.7 8.7 0 0 1 9.3 3.7a8.7 8.7 0 1 0 11 11Z"],
        sun: [
            "M12 7.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9Z",
            "M12 2.4v2.1M12 19.5v2.1M4.4 12h-2M21.6 12h-2M6.6 6.6 5.1 5.1M18.9 18.9l-1.5-1.5M6.6 17.4l-1.5 1.5M18.9 5.1l-1.5 1.5"
        ],
        close: ["M6.9 6.9 17.1 17.1", "M17.1 6.9 6.9 17.1"],
        settings: [
            "M4.2 8.2h8.4M17.4 8.2h2.4M4.2 15.8h4.4M13.4 15.8h6.4",
            "M15 6.4a1.8 1.8 0 1 0 0 3.6 1.8 1.8 0 0 0 0-3.6Z",
            "M11 14a1.8 1.8 0 1 0 0 3.6 1.8 1.8 0 0 0 0-3.6Z"
        ],
        focus: [
            "M4.2 8.2V6.4a2.2 2.2 0 0 1 2.2-2.2h1.8M15.8 4.2h1.8a2.2 2.2 0 0 1 2.2 2.2v1.8M19.8 15.8v1.8a2.2 2.2 0 0 1-2.2 2.2h-1.8M8.2 19.8H6.4a2.2 2.2 0 0 1-2.2-2.2v-1.8",
            "M12 8.7a3.3 3.3 0 1 0 0 6.6 3.3 3.3 0 0 0 0-6.6Z"
        ],
        trash: [
            "M4.8 7h14.4M9.4 7V5.3h5.2V7M6.7 7l.9 12.1h8.8l.9-12.1",
            "M10.5 10.7v5.2M13.5 10.7v5.2"
        ],
        dot: ["M12 11.2a.8.8 0 1 0 0 1.6.8.8 0 0 0 0-1.6Z"]
    })

    Repeater {
        model: root._paths[root.name] !== undefined ? root._paths[root.name] : []

        Shape {
            width: 24
            height: 24
            scale: root.size / 24
            transformOrigin: Item.TopLeft
            // 只做描边绘制，不参与命中测试
            enabled: false

            ShapePath {
                strokeColor: root.color
                strokeWidth: root.strokeWidth
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                joinStyle: ShapePath.RoundJoin
                PathSvg { path: modelData }
            }
        }
    }
}
