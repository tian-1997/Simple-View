import QtQuick

// 消息通知行（面板宽度固定 240：两行紧凑排版）
// 第 1 行：来源 · 发送者 …… 时间；第 2 行：正文。
// 正文只显示真实抓到的内容；抓不到正文时由数据层置空，不编造。
Item {
    id: row

    property string product: ""      // wechat / feishu / wecom
    property string appLabel: ""     // 微信 / 飞书 / 企微
    property string chat: ""         // 会话名
    property string sender: ""       // 发送者
    property string body: ""
    property string time: ""
    property bool unread: false
    property var bridge: null

    signal openRequested()

    readonly property color primary: theme.colors.textPrimary
    readonly property color secondary: theme.colors.textSecondary
    readonly property color muted: theme.colors.textMuted
    readonly property string who: sender ? (appLabel + " · " + sender)
                                         : (chat ? appLabel + " · " + chat : appLabel)
    readonly property int colX: theme.metrics.logo + 8

    implicitHeight: theme.metrics.notifyRowH
    height: implicitHeight
    opacity: unread ? 1.0 : 0.62

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
        product: row.product
        size: theme.metrics.logo
        anchors.verticalCenter: parent.verticalCenter
        x: 0
    }

    // ---- 第 1 行：来源 · 发送者 …… 未读点 + 时间 ----
    Text {
        id: whoText
        x: row.colX
        y: 6
        height: 18
        width: Math.max(0, timeText.x - x - (dot.visible ? 14 : 6))
        verticalAlignment: Text.AlignVCenter
        text: row.who
        color: row.primary
        font.pixelSize: 12
        font.weight: Font.Bold
        elide: Text.ElideRight
        maximumLineCount: 1
    }

    Rectangle {
        id: dot
        visible: row.unread
        width: 6
        height: 6
        radius: 3
        color: theme.colors.accent
        anchors.right: timeText.left
        anchors.rightMargin: 6
        y: 12
    }

    Text {
        id: timeText
        anchors.right: parent.right
        anchors.rightMargin: 2
        y: 6
        height: 18
        verticalAlignment: Text.AlignVCenter
        text: row.time
        color: row.muted
        font.pixelSize: 10
    }

    // ---- 第 2 行：正文 ----
    Text {
        x: row.colX
        y: 29
        height: 17
        width: row.width - row.colX
        verticalAlignment: Text.AlignVCenter
        text: row.body
        color: row.secondary
        font.pixelSize: 12
        elide: Text.ElideRight
        maximumLineCount: 1
    }
}
