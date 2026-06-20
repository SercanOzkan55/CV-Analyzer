# 🤖 AI Agent UI & Visual Automation Toolkit

This folder contains a set of executable scripts designed to act as **AI tools** that your coding assistant (**Gemini 3.5 Flash** in Antigravity) can run to inspect, interact, and align your frontend with Figma designs.

---

## 🛠️ Available Tools

### 1. `tools/screenshot.py` (Capture App State)
Takes a screenshot of the running web application.
- **Usage for AI / Developer**:
  ```bash
  python tools/screenshot.py "http://localhost:5173" "tools/app_actual.png"
  ```

### 2. `tools/playwright_interactive.js` (Interactive Browser Workflow)
Automates user flows (clicks, inputs, key presses, wait states) on your running application and captures the final state.
- **Usage for AI / Developer**:
  ```bash
  node tools/playwright_interactive.js "http://localhost:5173" '[{"action": "click", "selector": "button#login"}, {"action": "type", "selector": "input#email", "value": "test@example.com"}]' "tools/login_state.png"
  ```
- **Supported actions**: `click`, `type`, `hover`, `press`, `wait`.

### 3. `tools/fetch_figma.py` (Figma Design Fetcher)
Downloads a Figma frame or component.
- **API Mode**: Uses `FIGMA_ACCESS_TOKEN` from `.env`.
- **Tokenless Fallback**: Automatically falls back to tokenless viewport screenshotting for public files if no token is configured.
- **Usage for AI / Developer**:
  ```bash
  python tools/fetch_figma.py "FIGMA_URL" "tools/figma_target.png"
  ```

### 4. `tools/figma_implement_design.py` (Visual Diff & Overlay Report)
Pulls the target Figma frame and captures the actual local app screen, then merges them into a side-by-side and transparent overlay HTML visual diff report.
- **Usage for AI / Developer**:
  ```bash
  python tools/figma_implement_design.py "FIGMA_URL" "http://localhost:5173"
  ```
- **Output**: Generates `tools/design_comparison_report.html`. You can open this file in your browser to inspect pixel-perfect design alignment with an opacity slider!

---

## 💡 How to prompt the AI model in chat

When asking the AI model to adjust your UI:

> *"Please run `python tools/figma_implement_design.py <figma_url> http://localhost:5173` to compare my dashboard with the Figma design. Then read the output screenshots `tools/figma_target.png` and `tools/app_actual.png` to fix the layout misalignment in `frontend/src/pages/DashboardPage.jsx`."*

This allows the AI to systematically fetch the designs, capture your app's actual layout, visually analyze them, and write precise CSS/JSX changes!
