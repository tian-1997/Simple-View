import QtQuick
import QtQuick.Effects

// 玻璃底材：真实背景（已抓取）→ 模糊 → 圆角遮罩 → 着色 → 内高光 → 1px 描边
// 为什么不用系统 acrylic：DWM 的模糊层不受 SetWindowRgn 约束，圆角外面会露出方角底（实测）。
Item {
    id: surface

    property real radius: 20
    property bool live: backdrop ? backdrop.hasFrame : false
    property var sampler: backdrop
    property color edge: theme.colors.border
    property real blur: theme.glassBlur

    // 内容放进来就会被圆角裁掉
    default property alias content: holder.data

    // ---- 兜底：抓不到背景时用不透明底色，保证可读 ----
    Rectangle {
        anchors.fill: parent
        radius: surface.radius
        color: theme.colors.fallbackFill
        visible: !surface.live
        border.width: 1
        border.color: surface.edge
    }

    // ---- 玻璃层：模糊 + 遮罩 ----
    Item {
        id: glass
        anchors.fill: parent
        visible: surface.live
        layer.enabled: true
        layer.effect: MultiEffect {
            maskEnabled: true
            maskSource: maskShape
        }

        Image {
            anchors.fill: parent
            source: surface.live ? surface.sampler.source : ""
            // 采样图是降采样的，拉回来要平滑插值，否则会有硬边
            fillMode: Image.Stretch
            smooth: true
            layer.enabled: true
            layer.smooth: true
            layer.effect: MultiEffect {
                blurEnabled: true
                blur: surface.blur
                blurMax: 48
                saturation: 0.78
            }
        }

        // 着色：把壁纸压成可读的底色
        Rectangle {
            anchors.fill: parent
            color: theme.glassTint
        }

        // 内高光：只在顶部，模拟玻璃受光
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0.0; color: theme.mode === "light" ? "#66FFFFFF" : "#2BFFFFFF" }
                GradientStop { position: 0.45; color: "#00FFFFFF" }
            }
        }
    }

    // ---- 遮罩形状：必须独立于被遮罩内容，且自己带 layer ----
    Item {
        id: maskShape
        anchors.fill: parent
        visible: false
        layer.enabled: true

        Rectangle {
            anchors.fill: parent
            radius: surface.radius
            color: "white"
        }
    }

    // ---- 描边：单像素，压在最上层，圆角处不会发灰 ----
    Rectangle {
        anchors.fill: parent
        radius: surface.radius
        color: "transparent"
        border.width: 1
        border.color: surface.edge
    }

    Item {
        id: holder
        anchors.fill: parent
    }
}
