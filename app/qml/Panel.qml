import QtQuick

// 展开面板：Header → Agent 会话 → 消息通知 → 底部操作区（纵向堆叠）
// 全部用显式 y 定位：Repeater 创建的行会追加到子项末尾，靠 Column 的声明顺序不可靠。
Item {
    id: panel

    property var bridge: null

    readonly property int pad: theme.metrics.pad
    readonly property var agents: bridge ? bridge.agents : []
    readonly property var notifs: bridge ? bridge.notifs : []
    readonly property int running: bridge ? bridge.agentsRunning : 0
    readonly property int unread: bridge ? bridge.unread : 0
    readonly property bool hasNotifs: notifs.length > 0
    readonly property int rowW: width - pad * 2

    readonly property int rowH: theme.metrics.agentRowH
    readonly property int noteH: theme.metrics.notifyRowH

    // ---- 纵向分区 ----
    // 宽度和收起态一致（240），所以到处都得省着点用：表头 28、行 60、底部 32
    readonly property int yAgentHead: 28 + theme.metrics.sectionGap      // 40
    readonly property int yAgent0: yAgentHead + 20                        // 60
    readonly property int yNotifSep: yAgent0 + agents.length * rowH
    readonly property int yNotifHead: yNotifSep + (hasNotifs ? 24 : 0)
    readonly property int yNotif0: yNotifHead + (hasNotifs ? 20 : 0)
    readonly property int yFootSep: yNotif0 + notifs.length * noteH + 10
    readonly property int yFooter: yFootSep + 10

    width: theme.metrics.panelW
    height: yFooter + 32 + pad * 2
    implicitHeight: height
    clip: true

    // 玻璃底材（含圆角、描边、内高光、背景模糊）
    GlassSurface {
        anchors.fill: parent
        z: -1
        radius: theme.metrics.panelRadius
        edge: panel.bridge && panel.bridge.attention
              ? Qt.rgba(theme.statusColor("wait").r, theme.statusColor("wait").g, theme.statusColor("wait").b, 0.45)
              : theme.colors.border
        Behavior on edge { ColorAnimation { duration: theme.metrics.stateChange } }
    }

    // ================= 头部图标按钮 =================
    component HeadButton: Item {
        id: btn
        property string icon: "bell"
        property color tint: theme.colors.textSecondary
        signal clicked()

        width: 24
        height: 24

        Rectangle {
            anchors.fill: parent
            radius: 7
            color: theme.colors.controlHover
            opacity: ma.containsMouse ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: theme.metrics.hover } }
        }

        Icon {
            name: btn.icon
            size: 14
            color: btn.tint
            anchors.centerIn: parent
        }

        MouseArea {
            id: ma
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: btn.clicked()
        }
    }

    // ================= 区块标题 =================
    component SectionHead: Item {
        id: head
        property string title: ""
        property string rightText: ""
        property bool clickable: true
        signal rightClicked()

        height: 20

        Rectangle {
            width: 3
            height: 12
            radius: 1.5
            y: 4
            color: theme.colors.accent
        }

        Text {
            x: 10
            height: head.height
            verticalAlignment: Text.AlignVCenter
            text: head.title
            color: theme.colors.textPrimary
            font.pixelSize: 13
            font.weight: Font.Bold
        }

        Row {
            anchors.right: parent.right
            height: head.height
            spacing: 2

            Text {
                height: head.height
                verticalAlignment: Text.AlignVCenter
                text: head.rightText
                color: theme.colors.textMuted
                font.pixelSize: 11
            }

            Icon {
                name: "chevronRight"
                size: 11
                color: theme.colors.textMuted
                anchors.verticalCenter: parent.verticalCenter
                visible: head.clickable
            }
        }

        MouseArea {
            anchors.fill: parent
            enabled: head.clickable
            hoverEnabled: true
            cursorShape: head.clickable ? Qt.PointingHandCursor : Qt.ArrowCursor
            onClicked: head.rightClicked()
        }
    }

    // ================= 底部操作项 =================
    component FootAction: Item {
        id: fa
        property string icon: "settings"
        property string label: ""
        property bool primary: false
        signal clicked()

        height: 32

        Rectangle {
            anchors.fill: parent
            radius: 7
            color: theme.colors.controlHover
            opacity: faMa.containsMouse ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: theme.metrics.hover } }
        }

        Row {
            anchors.centerIn: parent
            spacing: 4

            Icon {
                name: fa.icon
                size: 14
                color: fa.primary ? theme.colors.textPrimary : theme.colors.textSecondary
                anchors.verticalCenter: parent.verticalCenter
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: fa.label
                color: fa.primary ? theme.colors.textPrimary : theme.colors.textSecondary
                font.pixelSize: 11
            }
        }

        MouseArea {
            id: faMa
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: fa.clicked()
        }
    }

    // ================= Header =================
    Item {
        x: panel.pad
        y: panel.pad
        width: panel.rowW
        height: 28

        BrandMark {
            size: 20
            anchors.verticalCenter: parent.verticalCenter
            colorA: theme.colors.brandA
            colorB: theme.colors.brandB
        }

        Text {
            x: 26
            anchors.verticalCenter: parent.verticalCenter
            text: "WinIsland"
            color: theme.colors.textPrimary
            font.pixelSize: 15
            font.weight: Font.Bold
        }

        Row {
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            spacing: 2

            HeadButton {
                icon: theme.mode === "light" ? "sun" : "moon"
                onClicked: if (panel.bridge) panel.bridge.toggleTheme()
            }

            HeadButton {
                icon: "settings"
                onClicked: if (panel.bridge) panel.bridge.openMenu()
            }

            HeadButton {
                icon: "close"
                onClicked: if (panel.bridge) panel.bridge.hideWindow()
            }
        }
    }

    // ================= Agent 会话 =================
    SectionHead {
        x: panel.pad
        y: panel.pad + panel.yAgentHead
        width: panel.rowW
        title: "活动会话"
        rightText: panel.agents.length === 0
                   ? "无会话"
                   : (panel.running > 0 ? panel.running + " 个运行中" : panel.agents.length + " 个会话")
        clickable: false
    }

    Repeater {
        model: panel.agents

        AgentRow {
            required property var modelData
            required property int index
            x: panel.pad
            y: panel.pad + panel.yAgent0 + index * panel.rowH
            width: panel.rowW
            agentName: modelData.name || ""
            product: panel.bridge ? panel.bridge.productOf(modelData.name || "") : ""
            title: modelData.title || ""
            proj: modelData.proj || ""
            action: modelData.action || ""
            status: modelData.status || ""
            elapsed: modelData.elapsed || ""
            running: !!modelData.running
            kind: theme.kindOf(modelData.status || "")
            bridge: panel.bridge
            onOpenRequested: if (panel.bridge)
                panel.bridge.openAgent(panel.bridge.productOf(modelData.name || ""),
                                       modelData.cwd || "", modelData.pid || 0)
        }
    }

    // ================= 消息通知 =================
    Item {
        x: panel.pad
        y: panel.pad + panel.yNotifSep
        width: panel.rowW
        height: 1
        visible: panel.hasNotifs

        Rectangle {
            anchors.fill: parent
            color: theme.colors.divider
        }
    }

    SectionHead {
        x: panel.pad
        y: panel.pad + panel.yNotifHead
        width: panel.rowW
        visible: panel.hasNotifs
        title: "消息通知"
        rightText: panel.unread > 0 ? "全部已读" : "已全部读完"
        clickable: panel.unread > 0
        onRightClicked: if (panel.bridge) panel.bridge.markAllRead()
    }

    Repeater {
        model: panel.notifs

        NotifyRow {
            required property var modelData
            required property int index
            x: panel.pad
            y: panel.pad + panel.yNotif0 + index * panel.noteH
            width: panel.rowW
            product: panel.bridge ? panel.bridge.notifyProduct(modelData.app || "") : ""
            appLabel: modelData.app || ""
            chat: modelData.chat || ""
            sender: modelData.sender || ""
            body: modelData.body || ""
            time: modelData.time || ""
            unread: !!modelData.unread
            bridge: panel.bridge
            onOpenRequested: if (panel.bridge)
                panel.bridge.openIm(panel.bridge.notifyProduct(modelData.app || ""))
        }
    }

    // ================= 底部操作区 =================
    Item {
        x: panel.pad
        y: panel.pad + panel.yFootSep
        width: panel.rowW
        height: 1

        Rectangle {
            anchors.fill: parent
            color: theme.colors.divider
        }
    }

    Item {
        x: panel.pad
        y: panel.pad + panel.yFooter
        width: panel.rowW
        height: 32

        Row {
            anchors.fill: parent

            FootAction {
                width: (panel.rowW - 2) / 3
                icon: "settings"
                label: "设置"
                onClicked: if (panel.bridge) panel.bridge.openMenu()
            }

            Rectangle {
                width: 1
                height: 14
                y: 9
                color: theme.colors.divider
            }

            FootAction {
                width: (panel.rowW - 2) / 3
                icon: "focus"
                label: panel.bridge && panel.bridge.focusMode ? "退出专注" : "专注"
                primary: panel.bridge ? panel.bridge.focusMode : false
                onClicked: if (panel.bridge) panel.bridge.toggleFocus()
            }

            Rectangle {
                width: 1
                height: 14
                y: 9
                color: theme.colors.divider
            }

            FootAction {
                width: (panel.rowW - 2) / 3
                icon: "trash"
                label: "清已读"
                onClicked: if (panel.bridge) panel.bridge.clearRead()
            }
        }
    }
}
