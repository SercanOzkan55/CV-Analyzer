import os
import sys
import subprocess

def generate_comparison_report(figma_url: str, app_url: str, output_html: str = "tools/design_comparison_report.html"):
    print("\n[=] Starting Figma vs App Design Comparison...")
    
    figma_img = "tools/figma_target.png"
    app_img = "tools/app_actual.png"
    
    # 1. Fetch Figma Target
    print("\n[1/3] Fetching Figma target design...")
    figma_cmd = ["python", "tools/fetch_figma.py", figma_url, figma_img]
    subprocess.run(figma_cmd, shell=True)
    
    # 2. Capture Local App State
    print("\n[2/3] Capturing actual running application state...")
    app_cmd = ["python", "tools/screenshot.py", app_url, app_img]
    subprocess.run(app_cmd, shell=True)
    
    if not os.path.exists(figma_img) or not os.path.exists(app_img):
        print("Error: Could not obtain both figma design and application screenshots.")
        return False
        
    # 3. Create Side-by-Side and Overlay HTML comparison report
    print("\n[3/3] Generating visual comparison HTML report...")
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Design Comparison Report</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: #0f172a;
      color: #f8fafc;
      margin: 0;
      padding: 24px;
    }}
    .header {{
      margin-bottom: 24px;
      border-bottom: 1px solid #334155;
      padding-bottom: 16px;
    }}
    h1 {{
      margin: 0 0 8px 0;
      font-size: 24px;
    }}
    .urls {{
      font-size: 14px;
      color: #94a3b8;
    }}
    .controls {{
      margin-bottom: 20px;
      display: flex;
      gap: 12px;
    }}
    button {{
      background: #38bdf8;
      color: #0f172a;
      border: none;
      padding: 10px 16px;
      border-radius: 6px;
      cursor: pointer;
      font-weight: 600;
      transition: background 0.2s;
    }}
    button:hover {{
      background: #0ea5e9;
    }}
    .comparison-container {{
      display: flex;
      gap: 20px;
      margin-bottom: 30px;
    }}
    .panel {{
      flex: 1;
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 12px;
      padding: 16px;
      display: flex;
      flex-direction: column;
      align-items: center;
    }}
    .panel h3 {{
      margin-top: 0;
      margin-bottom: 12px;
      color: #38bdf8;
    }}
    .preview-img {{
      max-width: 100%;
      height: auto;
      border-radius: 6px;
      border: 1px solid #475569;
    }}
    
    /* Overlay mode styles */
    .overlay-view {{
      display: none;
      position: relative;
      width: 1280px;
      height: 800px;
      margin: 0 auto;
      border: 2px solid #38bdf8;
      border-radius: 8px;
      overflow: hidden;
      background: #000;
    }}
    .overlay-img {{
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      object-fit: contain;
    }}
    .overlay-target {{
      opacity: 0.5;
      z-index: 2;
    }}
    .overlay-actual {{
      z-index: 1;
    }}
    .slider-container {{
      display: none;
      width: 600px;
      margin: 10px auto;
      text-align: center;
    }}
    .opacity-slider {{
      width: 100%;
    }}
  </style>
</head>
<body>

  <div class="header">
    <h1>🎨 Design Comparison Report</h1>
    <div class="urls">
      <strong>Figma Target:</strong> {figma_url}<br>
      <strong>Running App:</strong> {app_url}
    </div>
  </div>

  <div class="controls">
    <button onclick="showSideBySide()">Side-by-Side View</button>
    <button onclick="showOverlay()">Overlay Comparison View</button>
  </div>

  <div id="sideBySide" class="comparison-container">
    <div class="panel">
      <h3>🎯 Target Figma Design</h3>
      <img src="figma_target.png" class="preview-img" alt="Figma Target">
    </div>
    <div class="panel">
      <h3>🖥️ Actual Web Application</h3>
      <img src="app_actual.png" class="preview-img" alt="App Actual">
    </div>
  </div>

  <div id="overlayView" class="overlay-view">
    <img src="app_actual.png" class="overlay-img overlay-actual" alt="Actual app">
    <img src="figma_target.png" id="targetImg" class="overlay-img overlay-target" alt="Figma target">
  </div>

  <div id="sliderContainer" class="slider-container">
    <label for="opacity">Figma Overlay Opacity: <span id="opacityVal">50%</span></label><br>
    <input type="range" id="opacity" class="opacity-slider" min="0" max="100" value="50" oninput="adjustOpacity(this.value)">
  </div>

  <script>
    function showSideBySide() {{
      document.getElementById('sideBySide').style.display = 'flex';
      document.getElementById('overlayView').style.display = 'none';
      document.getElementById('sliderContainer').style.display = 'none';
    }}

    function showOverlay() {{
      document.getElementById('sideBySide').style.display = 'none';
      document.getElementById('overlayView').style.display = 'block';
      document.getElementById('sliderContainer').style.display = 'block';
    }}

    function adjustOpacity(val) {{
      document.getElementById('targetImg').style.opacity = val / 100;
      document.getElementById('opacityVal').innerText = val + '%';
    }}
  </script>

</body>
</html>
"""
    
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"\n[+] SUCCESS: Visual design comparison report generated successfully!")
    print(f"    Report Path: {os.path.abspath(output_html)}")
    print(f"    You can open this HTML file in your browser to inspect pixel-perfect design alignment.")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python tools/figma_implement_design.py <figma_url> <app_url> [output_html]")
        sys.exit(1)
        
    fig_url = sys.argv[1]
    app_url = sys.argv[2]
    out_html = sys.argv[3] if len(sys.argv) > 3 else "tools/design_comparison_report.html"
    generate_comparison_report(fig_url, app_url, out_html)
