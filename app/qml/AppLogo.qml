import QtQuick

// Agent / 消息来源标识。
// 有可信本地素材就显示真实 Logo（保持原始比例与品牌色）；没有素材的用「渐变圆角底 + 字标」占位，
// 看起来仍是一个 app icon，而不是一行裸字。
Item {
    id: root

    property string product: ""          // codex / pi / workbuddy / wechat / feishu / wecom
    property real size: 40
    property bool showPlate: true

    implicitWidth: size
    implicitHeight: size

    readonly property bool hasAsset: ["codex", "workbuddy", "wechat", "feishu", "wecom"].indexOf(product) >= 0
    // 自带圆角底色的图标（WorkBuddy 的 app icon）直接铺满，不再叠一层 plate
    readonly property bool fillsPlate: product === "workbuddy"
    readonly property string asset: {
        switch (product) {
        case "codex":
            return theme.mode === "light" ? "../../assets/agents/openai-light.svg"
                                          : "../../assets/agents/openai-dark.svg"
        case "workbuddy": return "../../assets/agents/workbuddy.png"
        case "wechat": return "../../assets/messaging/wechat.svg"
        case "feishu": return "../../assets/messaging/feishu.png"
        case "wecom":  return "../../assets/messaging/wecom.png"
        default: return ""
        }
    }
    readonly property string monogram: {
        switch (product) {
        case "pi": return "π"
        case "workbuddy": return "W"
        default: return "?"
        }
    }
    // 字标底色：给没有素材的 agent 一个可辨认的颜色身份
    readonly property color monoA: product === "pi" ? "#B69CFF" : theme.colors.brandA
    readonly property color monoB: product === "pi" ? "#7C5CF0" : theme.colors.brandB

    // codex 的花标在深色下是纯白色，垫默认的浅底板会把对比压掉；
    // 换成深色底板，既保住对比，又和其他 app 图标保持同样的圆角方块外形
    readonly property bool darkGlyph: product === "codex" && theme.mode !== "light"

    Rectangle {
        anchors.fill: parent
        visible: root.showPlate && !root.fillsPlate && root.hasAsset
        radius: Math.round(root.size * 0.3)
        color: root.darkGlyph ? "#5C000000" : theme.colors.logoPlate
        border.width: 1
        border.color: root.darkGlyph ? "#24FFFFFF" : theme.colors.border
    }

    // 无素材：渐变底，白字压在上面
    Rectangle {
        anchors.fill: parent
        visible: !root.hasAsset
        radius: Math.round(root.size * 0.28)
        gradient: Gradient {
            GradientStop { position: 0.0; color: root.monoA }
            GradientStop { position: 1.0; color: root.monoB }
        }
    }

    Image {
        visible: root.hasAsset
        source: root.hasAsset ? root.asset : ""
        anchors.centerIn: parent
        width: root.fillsPlate ? root.size : Math.round(root.size * 0.58)
        height: width
        fillMode: Image.PreserveAspectFit
        smooth: true
        mipmap: true
        // 素材是本地打包的，不联网
        cache: true
    }

    Text {
        visible: !root.hasAsset
        anchors.centerIn: parent
        text: root.monogram
        color: "#FFFFFF"
        font.pixelSize: Math.round(root.size * 0.52)
        font.weight: Font.Bold
    }
}
