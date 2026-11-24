import QtQuick
import QtQuick.Window

// 材质实验：彩色背景窗 + 玻璃窗叠放，用于判断系统模糊是否真的作用在背景上
Window {
    id: root
    width: 1180
    height: 720
    visible: true
    color: "#101216"
    title: "material-probe-bg"
    property alias glassWin: glass

    Image {
        anchors.fill: parent
        source: "file:///" + bgPath
        fillMode: Image.PreserveAspectCrop
        // 放大一点，让纹理更密，模糊是否生效一眼能看出来
        scale: 1.6
    }

    Window {
        id: glass
        width: 424
        height: 420
        x: 240
        y: 120
        visible: true
        color: "transparent"
        flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.NoDropShadowWindowHint
        title: "material-probe-glass"

        Rectangle {
            anchors.fill: parent
            radius: 22
            // 关键：QML 不填半透明底色，颜色交给系统 tint，否则两层 alpha 叠加会变不透明
            color: "transparent"
            border.width: 1
            border.color: "#40FFFFFF"

            Rectangle {
                anchors.fill: parent
                anchors.margins: 1
                radius: 21
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#1FFFFFFF" }
                    GradientStop { position: 0.45; color: "#00FFFFFF" }
                }
            }

            Column {
                anchors.left: parent.left
                anchors.leftMargin: 20
                anchors.top: parent.top
                anchors.topMargin: 20
                spacing: 10
                Text {
                    text: "GLASS PROBE"
                    color: "#F3F5F8"
                    font.pixelSize: 18
                    font.bold: true
                    font.letterSpacing: 2
                }
                Text {
                    text: "背后的彩色图是否被模糊？"
                    color: "#DCE2EC"
                    font.pixelSize: 13
                }
            }
        }
    }
}
