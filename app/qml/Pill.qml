import QtQuick

// 收起态顶部胶囊：agent logo → 会话摘要 → 通知入口
// 边框按主 agent 状态走：推理中/执行工具 渐变呼吸，已完成 绿色常亮，出错 红色常亮。
// 渐变描边是「外圈渐变矩形 + 内缩 1.5px 的玻璃」拼出来的：Qt 的 Rectangle 边框只支持单色，
// Shape 也没有渐变描边，这样叠一层既省事又能在圆角处保持干净。
//
// 宽度固定 = 面板宽度（theme.metrics.islandW），展开时窗口不会横向拉伸。
// 所以内容必须在 240 内自己让位：logo 22px、间距收紧、文字超出就省略。
Item {
    id: root

    property var bridge: null

    readonly property color primary: theme.colors.textPrimary
    readonly property color secondary: theme.colors.textSecondary
    readonly property color muted: theme.colors.textMuted
    readonly property int unread: bridge ? bridge.unread : 0

    readonly property string kind: bridge ? bridge.pillKind : "idle"
    // 有会话的 agent 列表（一个 agent 一个 logo），顺序按状态紧急度
    readonly property var logos: bridge ? bridge.pillAgents : []

    implicitHeight: theme.metrics.pillH
    implicitWidth: theme.metrics.islandW

    // ---- 边框：渐变两端稍暗、中段最亮，做出一点的流光感 ----
    // 单个 agent 的状态色也走这里，保证「胶囊外圈」和「图标描边环」永远是同一套颜色
    function ringColor(k) {
        switch (k) {
        case "think": return "#8B5CF6"
        case "tool":  return "#3B82F6"
        case "done":  return "#22A06B"
        case "wait":  return "#E08A2E"
        case "error": return "#D03A3A"
        default:      return "transparent"
        }
    }
    readonly property color ringA: ringColor(kind)
    readonly property color ringB: {
        switch (kind) {
        case "think": return "#C4A7FF"
        case "tool":  return "#7FB4FF"
        case "done":  return "#4BE39A"
        case "wait":  return "#FFC766"
        case "error": return "#FF7A7A"
        default:      return "transparent"
        }
    }
    // 进行中才呼吸；完成/出错常亮
    readonly property bool breathing: kind === "think" || kind === "tool" || kind === "wait"
    readonly property bool showRing: kind !== "idle"

    property real ringOpacity: 1

    SequentialAnimation {
        running: root.breathing
        loops: Animation.Infinite
        NumberAnimation {
            target: root; property: "ringOpacity"
            from: 0.42; to: 1.0; duration: 1300; easing.type: Easing.InOutSine
        }
        NumberAnimation {
            target: root; property: "ringOpacity"
            from: 1.0; to: 0.42; duration: 1300; easing.type: Easing.InOutSine
        }
        onStopped: root.ringOpacity = 1
    }

    Rectangle {
        visible: root.showRing
        anchors.fill: parent
        radius: height / 2
        opacity: root.ringOpacity
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.00; color: root.ringA }
            GradientStop { position: 0.50; color: root.ringB }
            GradientStop { position: 1.00; color: root.ringA }
        }
        Behavior on opacity {
            enabled: !root.breathing
            NumberAnimation { duration: theme.metrics.stateChange }
        }
    }

    GlassSurface {
        // 内缩让外面那 1.5px 的渐变露出来当描边
        anchors.fill: parent
        anchors.margins: root.showRing ? 1.5 : 0
        radius: height / 2
        edge: root.showRing ? "transparent" : theme.colors.border

        Row {
            id: content
            anchors.centerIn: parent
            spacing: 6

            // 有几个 agent 有会话就摆几个 logo，不再写「WinIsland」字样。
            // 每个 logo 外面一圈状态描边，一眼看出它此刻在推理 / 跑工具 / 已完成。
            Row {
                id: logos
                anchors.verticalCenter: parent.verticalCenter
                spacing: 4

                Repeater {
                    model: root.logos

                    delegate: Item {
                        width: 22
                        height: 22

                        // 每个 agent 一条状态描边（和胶囊外圈同一套语言），中间留 1.5px 玻璃缝：
                        // 用来解决「紫色 π 底板 + 紫色状态点」糊成一片的问题
                        Rectangle {
                            readonly property string st: modelData.kind || "idle"
                            anchors.fill: parent
                            radius: 7
                            color: "transparent"
                            visible: st !== "idle"
                            border.width: 1.5
                            border.color: root.ringColor(st)
                            opacity: 0.9
                        }

                        AppLogo {
                            anchors.centerIn: parent
                            product: modelData.product || ""
                            size: 17
                            showPlate: true
                            opacity: modelData.dim ? 0.55 : 1.0
                            Behavior on opacity { NumberAnimation { duration: theme.metrics.stateChange } }
                        }
                    }
                }
            }

            // 一个会话都没有时留个自有标，别让胶囊空成一条
            BrandMark {
                id: brand
                visible: root.logos.length === 0
                size: 18
                anchors.verticalCenter: parent.verticalCenter
                colorA: theme.colors.brandA
                colorB: theme.colors.brandB
            }

            Rectangle {
                id: divider
                anchors.verticalCenter: parent.verticalCenter
                width: 1
                height: 14
                color: theme.colors.divider
            }

            // 宽度被胶囊卡死：多出来的字数省略，绝不撑破圆角（固定 240 宽的前提）
            Text {
                id: label
                anchors.verticalCenter: parent.verticalCenter
                width: Math.min(implicitWidth,
                                Math.max(0, root.width - 24 - logos.width - brand.width
                                            - divider.width - bell.width - chevron.width
                                            - content.spacing * 5))
                text: root.bridge ? root.bridge.pillText : ""
                color: root.secondary
                font.pixelSize: 12
                elide: Text.ElideRight
                maximumLineCount: 1
            }

            // 通知入口：铃铛 + 数字角标
            Item {
                id: bell
                anchors.verticalCenter: parent.verticalCenter
                width: 15
                height: 15

                Icon {
                    name: "bell"
                    size: 14
                    color: root.primary
                    anchors.centerIn: parent
                }

                Rectangle {
                    visible: root.unread > 0
                    anchors.right: parent.right
                    anchors.rightMargin: -7
                    anchors.top: parent.top
                    anchors.topMargin: -6
                    width: Math.max(13, badgeText.implicitWidth + 6)
                    height: 13
                    radius: 6.5
                    color: theme.colors.accent
                    border.width: 1
                    border.color: theme.mode === "light" ? "#FFFFFF" : "#1B2029"

                    Text {
                        id: badgeText
                        anchors.centerIn: parent
                        text: root.unread > 99 ? "99+" : root.unread
                        color: "#FFFFFF"
                        font.pixelSize: 9
                        font.weight: Font.Bold
                    }
                }
            }

            Icon {
                id: chevron
                anchors.verticalCenter: parent.verticalCenter
                name: "chevron"
                size: 13
                color: root.muted
            }
        }
    }
}
