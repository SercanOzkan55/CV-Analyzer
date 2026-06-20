# 🎨 Figma to Gemini Flash Integration Guide

This workspace includes a utility to fetch design layouts directly from Figma and save them to the project workspace. This enables **Gemini 3.5 Flash** (the model you select in Antigravity) to read the design specifications, compare them with the existing React code, and write clean modifications.

---

## 🚀 Two Modes of Operation

### 1. Tokenless Mode (Public Files)
If the Figma file is **public**, you **do not need** any personal access tokens or credentials! The script will automatically launch a headless Playwright browser, render the canvas, and capture a screenshot.

```bash
python tools/fetch_figma.py "https://www.figma.com/design/AbCdEfGh/CV-Analyzer?node-id=12-3"
```
*(No setup required! Just run and capture).*

### 2. API Mode (Private & Public Files)
For private files or faster/exact frame exports:
1. Go to your **Figma Account Settings** -> **Personal Access Tokens**.
2. Create a token and add it to your `.env` file:
   ```env
   FIGMA_ACCESS_TOKEN=your_token_here
   ```

---

## 📸 How to Fetch Designs

Run the script from your terminal:

```bash
python tools/fetch_figma.py "FIGMA_URL"
```

### Examples:

- **Fetch a specific frame** (Recommended: captures targeted area):
  ```bash
  python tools/fetch_figma.py "https://www.figma.com/design/AbCdEfGhIjKlMnOpQrStUv/CV-Analyzer-Layout?node-id=102-145"
  ```
  *(This saves the frame image directly to `tools/figma_output.png`)*

- **Fetch to a custom filename**:
  ```bash
  python tools/fetch_figma.py "https://www.figma.com/design/AbCdEfGh/CV-Analyzer?node-id=12-3" "tools/new_dashboard.png"
  ```

---

## 🤖 Working with Gemini 3.5 Flash (Antigravity)

Once the design image is downloaded to your workspace:

1. **Reference the image in your chat prompt**:
   > *"I have downloaded the target Figma design to `tools/figma_output.png`. Please check `frontend/src/pages/DashboardPage.jsx` and modify the UI layout, spacing, and colors to exactly match the design in that image."*

2. **Let the Assistant read the file**:
   Because Gemini 3.5 Flash in Antigravity has direct access to the workspace files, it can view the downloaded `figma_output.png`, inspect your React files, and write the precise code changes to achieve a perfect implementation!

3. **Verify**:
   Run the build script to ensure compilation succeeds:
   ```bash
   cd frontend
   npm run build
   ```
