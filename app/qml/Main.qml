import QtQuick
import QtQuick.Window

// 顶层窗口：无边框、置顶、不抢焦点；窗口尺寸跟随内容，玻璃材质由 Python 侧应用
Window {
    id: win

    width: island.width
    height: island.height
    visible: true
    color: "transparent"
    title: "WinIsland"
    flags: Qt.FramelessWindowHint
         | Qt.WindowStaysOnTopHint
         | Qt.Tool
         | Qt.NoDropShadowWindowHint
         | Qt.WindowDoesNotAcceptFocus

    Behavior on height { NumberAnimation { duration: island.dur; easing.type: Easing.OutCubic } }

    // 宽度不再变化（展开态和收起态同为 theme.metrics.islandW = 240），
    // 所以不需要再钉中心：窗口只向下长高度，左上角原地不动，视觉上就是「从胶囊底下抽出来」。

    Island {
        id: island
        x: 0
        y: 0
        bridge: islandBridge
    }
}
