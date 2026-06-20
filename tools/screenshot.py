import sys
import subprocess
import os

def take_screenshot(url: str, output_path: str = "tools/app_screenshot.png"):
    print(f"Taking screenshot of: {url}")
    cmd = [
        "npx", "playwright", "screenshot",
        "--viewport-size", "1280,800",
        url,
        output_path
    ]
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        # Run playwright screenshot CLI
        subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print(f"[+] Screenshot saved to: {os.path.abspath(output_path)}")
        return True
    except Exception as e:
        print(f"Error capturing screenshot: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/screenshot.py <url> [output_path]")
        sys.exit(1)
    url = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else "tools/app_screenshot.png"
    take_screenshot(url, out_path)
