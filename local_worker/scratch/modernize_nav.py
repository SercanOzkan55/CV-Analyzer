import re
from pathlib import Path

def main():
    f = Path(r"c:\Users\ASUS\Desktop\cv-analyzer\local_worker\qml\Main.qml")
    content = f.read_text(encoding="utf-8")
    
    # 1. Replace StackLayout with Item
    content = content.replace("            StackLayout {", "            Item {")
    
    # 2. Modernize each of the 8 pages
    pages = [
        ("dashboardScroll", 0, "ColumnLayout"),
        ("analyzeScroll", 1, "ColumnLayout"),
        ("historyScroll", 3, "ColumnLayout"),
        ("syncScroll", 4, "ColumnLayout"),
        ("reportsScroll", 5, "ColumnLayout"),
        ("templatesScroll", 6, "RowLayout"),
        ("settingsScroll", 7, "ColumnLayout")
    ]
    
    for scroll_id, idx, layout_type in pages:
        # Find the ScrollView declaration
        scroll_pattern = rf'(ScrollView\s*{{\s*id:\s*{scroll_id}\s*(?:clip:\s*true\s*)?}})'
        # Replace it with our modernized ScrollView
        replacement = (
            f"ScrollView {{\n"
            f"                    id: {scroll_id}\n"
            f"                    anchors.fill: parent\n"
            f"                    visible: opacity > 0.01\n"
            f"                    enabled: visible\n"
            f"                    opacity: root.pageIndex === {idx} ? 1 : 0\n"
            f"                    y: root.pageIndex === {idx} ? 0 : 12\n"
            f"                    Behavior on opacity {{ NumberAnimation {{ duration: 280; easing.type: Easing.OutCubic }} }}\n"
            f"                    Behavior on y {{ NumberAnimation {{ duration: 280; easing.type: Easing.OutCubic }} }}\n"
            f"                    clip: true"
        )
        content = re.sub(scroll_pattern, replacement, content)
        
        # Now find the inner layout pattern and remove its opacity and y transitions
        layout_pattern = (
            rf'({layout_type}\s*{{\s*'
            rf'x:\s*root\.contentX\({scroll_id}\.availableWidth\)\s*\n\s*'
            rf'y:\s*28\s*\+\s*\(root\.pageIndex\s*===\s*{idx}\s*\?\s*0\s*:\s*8\)\s*\n\s*'
            rf'width:\s*root\.contentWidth\({scroll_id}\.availableWidth\)\s*\n\s*'
            rf'opacity:\s*root\.pageIndex\s*===\s*{idx}\s*\?\s*1\s*:\s*0\s*\n\s*'
            rf'Behavior on opacity\s*{{\s*NumberAnimation\s*{{\s*duration:\s*200;\s*easing\.type:\s*Easing\.OutCubic\s*}}\s*}}\s*\n\s*'
            rf'Behavior on y\s*{{\s*NumberAnimation\s*{{\s*duration:\s*200;\s*easing\.type:\s*Easing\.OutCubic\s*}}\s*}}\s*)'
        )
        
        layout_replacement = (
            f"{layout_type} {{\n"
            f"                        x: root.contentX({scroll_id}.availableWidth)\n"
            f"                        y: 28\n"
            f"                        width: root.contentWidth({scroll_id}.availableWidth)"
        )
        
        content = re.sub(layout_pattern, layout_replacement, content)

    # 3. Special handling for Page 2: resultsScroll
    # Replace resultsScroll declaration
    results_scroll_pattern = r'(ScrollView\s*{\s*id:\s*resultsScroll\s*clip:\s*true\s*})'
    results_replacement = (
        "ScrollView {\n"
        "                    id: resultsScroll\n"
        "                    anchors.fill: parent\n"
        "                    visible: opacity > 0.01\n"
        "                    enabled: visible\n"
        "                    opacity: root.pageIndex === 2 ? 1 : 0\n"
        "                    y: root.pageIndex === 2 ? 0 : 12\n"
        "                    Behavior on opacity { NumberAnimation { duration: 280; easing.type: Easing.OutCubic } }\n"
        "                    Behavior on y { NumberAnimation { duration: 280; easing.type: Easing.OutCubic } }\n"
        "                    clip: true"
    )
    content = re.sub(results_scroll_pattern, results_replacement, content)

    # Make EmptyState in resultsScroll static (remove dynamic y, opacity transitions)
    # We find y: 56 + (root.pageIndex === 2 ? 0 : 8)
    content = content.replace("y: 56 + (root.pageIndex === 2 ? 0 : 8)", "y: 56")
    content = content.replace("Behavior on y { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }\n                        height: 300", "height: 300")
    content = content.replace("opacity: visible ? 1 : 0\n                        title:", "title:")
    content = content.replace("targetPage: 1\n                        Behavior on opacity { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }", "targetPage: 1")

    # Make RowLayout in resultsScroll static
    content = content.replace("y: 28 + (root.pageIndex === 2 ? 0 : 8)", "y: 28")
    content = content.replace("Behavior on y { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }\n                        height: resultsScroll.availableHeight - 56", "height: resultsScroll.availableHeight - 56")
    content = content.replace("opacity: visible ? 1 : 0\n                        spacing: 20\n                        Behavior on opacity { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }", "spacing: 20")

    # Write back
    f.write_text(content, encoding="utf-8")
    print("SUCCESS: Main.qml nav transition updated!")

if __name__ == "__main__":
    main()
