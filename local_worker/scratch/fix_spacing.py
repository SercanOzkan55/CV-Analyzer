from pathlib import Path


def main():
    f = Path(r"c:\Users\ASUS\Desktop\cv-analyzer\local_worker\qml\Main.qml")
    content = f.read_text(encoding="utf-8")

    # Replace spacing:
    content = content.replace(
        "width: root.contentWidth(dashboardScroll.availableWidth)spacing: 16",
        "width: root.contentWidth(dashboardScroll.availableWidth)\n                        spacing: 16",
    )
    content = content.replace(
        "width: root.contentWidth(analyzeScroll.availableWidth)spacing: 18",
        "width: root.contentWidth(analyzeScroll.availableWidth)\n                        spacing: 18",
    )
    content = content.replace(
        "width: root.contentWidth(historyScroll.availableWidth)spacing: 18",
        "width: root.contentWidth(historyScroll.availableWidth)\n                        spacing: 18",
    )
    content = content.replace(
        "width: root.contentWidth(syncScroll.availableWidth)spacing: 18",
        "width: root.contentWidth(syncScroll.availableWidth)\n                        spacing: 18",
    )
    content = content.replace(
        "width: root.contentWidth(reportsScroll.availableWidth)spacing: 18",
        "width: root.contentWidth(reportsScroll.availableWidth)\n                        spacing: 18",
    )
    content = content.replace(
        "width: root.contentWidth(settingsScroll.availableWidth)spacing: 18",
        "width: root.contentWidth(settingsScroll.availableWidth)\n                        spacing: 18",
    )

    # Replace height:
    content = content.replace(
        "width: root.contentWidth(templatesScroll.availableWidth)height: templatesScroll.availableHeight - 56",
        "width: root.contentWidth(templatesScroll.availableWidth)\n                        height: templatesScroll.availableHeight - 56",
    )

    f.write_text(content, encoding="utf-8")
    print("SUCCESS: Spacing/height lines split successfully!")


if __name__ == "__main__":
    main()
