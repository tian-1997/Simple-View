import QtQuick

// WinIsland 自有品牌标：两道斜杠，圆角端点。矢量绘制，任意尺寸都清晰，不依赖位图。
Item {
    id: root

    property real size: 24
    property color colorA: "#67B2FF"
    property color colorB: "#2E7BF0"

    implicitWidth: Math.round(size * 1.16)
    implicitHeight: size

    component Bar: Rectangle {
        width: Math.round(root.size * 0.29)
        height: Math.round(root.size * 0.93)
        radius: width / 2
        y: Math.round(root.size * 0.04)
        rotation: 15
        gradient: Gradient {
            GradientStop { position: 0.0; color: root.colorA }
            GradientStop { position: 1.0; color: root.colorB }
        }
    }

    Bar {
        x: Math.round(root.size * 0.00)
    }

    Bar {
        x: Math.round(root.size * 0.57)
        opacity: 0.86
    }
}
