import QtQuick
import QtQuick.Window

// 设计评审用的背景窗：只在窗口背后铺一小块壁纸，不铺满整屏。
// 壁纸按 1:1 屏幕映射裁剪（sourceClipRect），这样玻璃采样到的颜色
// 和真实桌面一致，不会因为窗口小而被放大成一片怪色。
Window {
    id: backdrop

    property real clipX: 0
    property real clipY: 0
    property real imgScale: 1

    width: 520
    height: 720
    x: 0
    y: 0
    visible: true
    color: "#0E1116"
    title: "winisland-backdrop"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint

    Image {
        anchors.fill: parent
        source: "file:///" + bgPath
        // 剪裁矩形用图片像素坐标：屏幕逻辑坐标 × (图片宽 / 屏幕宽)
        sourceClipRect: Qt.rect(clipX * imgScale, clipY * imgScale,
                                width * imgScale, height * imgScale)
        fillMode: Image.Stretch
        smooth: true
    }
}
