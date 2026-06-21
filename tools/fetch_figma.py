import os
import re
import sys
import subprocess
import urllib.parse

import requests
from dotenv import load_dotenv

load_dotenv(encoding="utf-8-sig")


def parse_figma_url(url: str):
    """Parse file key and node id from a Figma link."""
    # Find file key
    file_match = re.search(r"(?:file|design)/([a-zA-Z0-9]{22,})", url)
    if not file_match:
        return None, None
    file_key = file_match.group(1)

    # Find node-id/id
    node_match = re.search(r"node-id=([a-zA-Z0-9\-:]+)", url)
    if not node_match:
        # Try id parameter
        node_match = re.search(r"\bid=([a-zA-Z0-9\-:]+)", url)

    node_id = node_match.group(1) if node_match else None
    if node_id:
        node_id = node_id.replace("-", ":")

    return file_key, node_id


def download_figma_image_tokenless(url: str, output_path: str = "tools/figma_output.png") -> bool:
    """Take a screenshot of a public Figma URL without tokens using Playwright CLI."""
    print("Preparing tokenless render for public Figma link...")
    # Convert figma URL to embed URL
    embed_url = f"https://www.figma.com/embed?embed_host=share&url={urllib.parse.quote(url)}"

    print("Launching headless Playwright browser to capture design canvas (waiting 10s for WebGL)...")
    npx_bin = "npx.cmd" if os.name == "nt" else "npx"
    cmd = [
        npx_bin,
        "playwright",
        "screenshot",
        "--wait-for-timeout",
        "10000",
        "--viewport-size",
        "1920,1080",
        embed_url,
        output_path,
    ]

    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"\n[+] SUCCESS: Figma frame downloaded tokenlessly to:")
        print(f"    {os.path.abspath(output_path)}")
        print(f"    You can now ask the AI model (Gemini 3.5 Flash) to match this design directly!")
        return True
    except Exception as e:
        print(f"Error rendering figma tokenlessly: {e}")
        # Print instructions to try setting access token
        print("\nIf the file is private, please try configuring a FIGMA_ACCESS_TOKEN in your .env file:")
        print("1. Go to Figma -> Account Settings -> Personal Access Tokens.")
        print("2. Create a token and add it: FIGMA_ACCESS_TOKEN=your_token")
        return False


def download_figma_image(url: str, output_path: str = "tools/figma_output.png"):
    file_key, node_id = parse_figma_url(url)
    if not file_key:
        print("Error: Invalid Figma URL format. Expected: figma.com/file/FILE_KEY/... or figma.com/design/FILE_KEY/...")
        return False

    token = os.getenv("FIGMA_ACCESS_TOKEN")
    if not token:
        # Fallback to tokenless Playwright capture
        return download_figma_image_tokenless(url, output_path)

    print(f"Connecting to Figma API for file key: {file_key}...")
    headers = {"X-Figma-Token": token}

    # If a specific node is specified, download just that frame/node
    if node_id:
        api_url = f"https://api.figma.com/v1/images/{file_key}?ids={node_id}&format=png&scale=2"
        print(f"Fetching render URL for node: {node_id}...")
    else:
        # If no node, fall back to tokenless viewport capture or document retrieval
        print("No specific node-id found in URL. Fetching the file page view tokenlessly...")
        return download_figma_image_tokenless(url, output_path)

    res = requests.get(api_url, headers=headers, timeout=20)
    if res.status_code != 200:
        # If API fails (e.g. token expired, or unauthorized), fallback to tokenless browser capture
        print(f"Figma API failed ({res.status_code}). Falling back to tokenless Playwright screenshot...")
        return download_figma_image_tokenless(url, output_path)

    data = res.json()
    image_url = data.get("images", {}).get(node_id)
    if not image_url:
        image_url = data.get("images", {}).get(node_id.replace(":", "-"))

    if not image_url:
        print(f"Error: Node {node_id} could not be rendered via API. Falling back to Playwright capture...")
        return download_figma_image_tokenless(url, output_path)

    print(f"Downloading rendered image from: {image_url}...")
    img_res = requests.get(image_url, timeout=30)
    if img_res.status_code == 200:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(img_res.content)
        print(f"\n[+] SUCCESS: Figma frame downloaded successfully to:")
        print(f"    {os.path.abspath(output_path)}")
        print(f"    You can now ask the AI model (Gemini 3.5 Flash) to match this design directly!")
        return True
    else:
        print(f"Download failed: {img_res.status_code}. Falling back to Playwright capture...")
        return download_figma_image_tokenless(url, output_path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/fetch_figma.py <figma_url> [output_path]")
        sys.exit(1)

    url = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else "tools/figma_output.png"
    download_figma_image(url, out_path)
