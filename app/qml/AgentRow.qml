import QtQuick

// Agent 会话行（面板宽度固定 240，所以是三行紧凑排版）
// 第 1 行：agent 名 + 状态 chip；第 2 行：会话名；第 3 行：项目 · 最近动作 + 时长。
// 整行可点：点了就跳到那个 agent 的窗口（找不到就开项目目录，见 app/launcher.py）。
Item {
    id: row

    property string agentName: ""
    property string product: ""        // 用于取 Logo
    property string title: ""          // 会话名（首条用户指令摘要）
    property string proj: ""
    property string action: ""
    property string status: ""
    property string elapsed: ""
    property string kind: "idle"       // think / tool / wait / done / error / idle
    property bool running: false
    property var bridge: null          // 用于按住拖动窗口

    signal openRequested()

    readonly property color stateColor: theme.statusColor(kind)
    readonly property color primary: theme.colors.textPrimary
    readonly property color secondary: theme.colors.textSecondary
    readonly property color muted: theme.colors.textMuted

    // logo(36) + 8 间隙：所有文字列的起点
    readonly property int colX: theme.metrics.logo + 8

    implicitHeight: theme.metrics.agentRowH
    height: implicitHeight

    Rectangle {
        id: hover
        anchors.fill: parent
        radius: 10
        color: theme.colors.rowHover
        opacity: mouse.containsMouse ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: theme.metrics.hover } }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton
        cursorShape: Qt.PointingHandCursor

        // 用 Qt 自带的拖动阈值区分点击/拖动：窗口自己移动时手算 mouseX 位移会误判
        drag.target: dragProxy
        drag.threshold: 6
        drag.onActiveChanged: if (drag.active && row.bridge) row.bridge.beginDrag()

        onClicked: row.openRequested()

        Item {
            id: dragProxy
            width: 1
            height: 1
            visible: false
        }
    }

    AppLogo {
        id: logo
        product: row.product
        size: theme.metrics.logo
        anchors.verticalCenter: parent.verticalCenter
        x: 0
    }

    // ---- 第 1 行：agent 名 …… 状态 chip ----
    Text {
        id: nameText
        x: row.colX
        y: 4
        height: 20
        width: Math.max(0, chip.x - x - 6)
        verticalAlignment: Text.AlignVCenter
        text: row.agentName
        color: row.primary
        font.pixelSize: 13
        font.weight: Font.Bold
        elide: Text.ElideRight
        maximumLineCount: 1
    }

    Rectangle {
        id: chip
        anchors.right: parent.right
        y: 5
        height: 18
        width: chipText.implicitWidth + 10
        radius: 6
        // 已完成 / 空闲用中性灰 + 描边，避免和运行态的彩色 chip 抢注意力
        readonly property bool neutral: row.kind === "done" || row.kind === "idle"
        color: neutral ? "transparent"
                       : Qt.rgba(row.stateColor.r, row.stateColor.g, row.stateColor.b, 0.15)
        border.width: neutral || row.kind === "wait" ? 1 : 0
        border.color: neutral
                      ? theme.colors.border
                      : Qt.rgba(row.stateColor.r, row.stateColor.g, row.stateColor.b, 0.45)

        Text {
            id: chipText
            anchors.centerIn: parent
            text: row.status
            color: chip.neutral ? theme.colors.textSecondary : row.stateColor
            font.pixelSize: 11
            font.weight: row.kind === "wait" ? Font.Bold : Font.Normal
        }
    }

    // ---- 第 2 行：会话名 ----
    Text {
        id: titleText
        x: row.colX
        y: 26
        height: 17
        width: row.width - row.colX
        verticalAlignment: Text.AlignVCenter
        text: row.title
        color: row.secondary
        font.pixelSize: 12
        elide: Text.ElideRight
        maximumLineCount: 1
    }

    // ---- 第 3 行：项目 · 最近动作 …… 时长 ----
    Text {
        id: projText
        x: row.colX
        y: 45
        height: 15
        width: Math.max(0, row.width - row.colX - elapsedText.width - 8)
        verticalAlignment: Text.AlignVCenter
        text: row.proj + (row.action ? " · " + row.action : "")
        color: row.muted
        font.pixelSize: 11
        elide: Text.ElideRight
        maximumLineCount: 1
    }

    Text {
        id: elapsedText
        anchors.right: parent.right
        anchors.rightMargin: 2
        y: 45
        height: 15
        verticalAlignment: Text.AlignVCenter
        text: row.elapsed
        color: row.muted
        font.pixelSize: 10
        font.family: "Cascadia Mono"
    }
}
