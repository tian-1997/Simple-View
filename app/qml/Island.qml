import QtQuick

// 岛容器：收起态胶囊 ⇄ 展开态面板，窗口尺寸跟着内容走
Item {
    id: root

    property var bridge: null

    readonly property bool expanded: bridge ? bridge.expanded : false
    readonly property int dur: expanded ? theme.metrics.expand : theme.metrics.collapse

    width: expanded ? panel.width : pill.width
    height: expanded ? panel.height : pill.height

    // 宽度两边都是 islandW，不变；只有高度做展开/收起动画
    Behavior on height { NumberAnimation { duration: root.dur; easing.type: Easing.OutCubic } }

    // 点击 / 拖动分离用 MouseArea 自带的 drag.threshold，不要手算位移：
    // 窗口展开收起时自身会移动，mouseX/mouseY 会连续变化甚至归零，手算会把点击误判成拖动。
    component TapDragArea: MouseArea {
        id: tda

        property var bridgeRef: null
        signal tapped()

        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton

        drag.target: dragProxy
        drag.threshold: 6
        drag.onActiveChanged: if (drag.active && tda.bridgeRef) tda.bridgeRef.beginDrag()

        onClicked: tda.tapped()

        Item {
            id: dragProxy
            width: 1
            height: 1
            visible: false
        }
    }

    // ---------- 收起态 ----------
    Pill {
        id: pill
        x: (root.width - width) / 2
        y: 0
        bridge: root.bridge
        visible: opacity > 0
        opacity: root.expanded ? 0 : 1
        scale: root.expanded ? 0.96 : 1
        Behavior on opacity { NumberAnimation { duration: root.expanded ? 120 : 180 } }
        Behavior on scale { NumberAnimation { duration: root.dur; easing.type: Easing.OutCubic } }

        TapDragArea {
            anchors.fill: parent
            bridgeRef: root.bridge
            onTapped: if (root.bridge) root.bridge.toggle()
        }
    }

    // ---------- 展开态 ----------
    Panel {
        id: panel
        x: (root.width - width) / 2
        y: 0
        bridge: root.bridge
        visible: opacity > 0
        opacity: root.expanded ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: root.expanded ? theme.metrics.panelIn : 120 } }

        // 拖动手柄：整块面板空白处都能拖（z 放到底层，避免吃掉头部按钮的点击）
        MouseArea {
            width: parent.width
            height: parent.height
            x: 0
            y: 0
            z: -1
            cursorShape: Qt.SizeAllCursor
            onPressed: if (root.bridge) root.bridge.beginDrag()
            onPositionChanged: if (root.bridge) root.bridge.dragMove()
        }
    }

    // ---------- 展开态的顶栏热区 ----------
    // 展开后胶囊隐去，但原来胶囊那一带就是面板顶栏：再点一下就收起。
    // 右侧留给面板自己的三个按钮（3×24 + 2×2 = 76）再加上 pad 和一点余量，热区不能盖住它们。
    TapDragArea {
        id: collapseArea
        visible: root.expanded
        x: panel.x
        y: 0
        width: Math.max(0, panel.width - theme.metrics.pad - 92)
        height: theme.metrics.pad + 28 + 4
        z: 3
        bridgeRef: root.bridge
        onTapped: if (root.bridge) root.bridge.toggle()
    }
}
