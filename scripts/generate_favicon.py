#!/usr/bin/env python3
import os
import subprocess
import time
from pathlib import Path
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"
SVG_PATH = WEB_DIR / "favicon.svg"
HTML_RENDER_PATH = WEB_DIR / "_render_favicon.html"
PNG_512 = WEB_DIR / "favicon-512x512.png"

# Create a clean HTML wrapper to render SVG at exactly 512x512 with transparent background
HTML_CONTENT = """<!DOCTYPE html>
<html>
<head>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { width: 512px; height: 512px; background: transparent; overflow: hidden; }
    img { width: 512px; height: 512px; display: block; }
  </style>
</head>
<body>
  <img src="favicon.svg" />
</body>
</html>
"""
HTML_RENDER_PATH.write_text(HTML_CONTENT, encoding="utf-8")

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

if os.path.exists(CHROME_BIN):
    cmd = [
        CHROME_BIN,
        "--headless=new",
        "--default-background-color=00000000",
        "--window-size=512,512",
        f"--screenshot={PNG_512}",
        str(HTML_RENDER_PATH),
    ]
    subprocess.run(cmd, check=True)
else:
    print("Chrome binary not found at default Mac location.")

if HTML_RENDER_PATH.exists():
    HTML_RENDER_PATH.unlink()

if PNG_512.exists():
    img = Image.open(PNG_512).convert("RGBA")
    
    # 180x180 apple touch icon
    apple_img = img.resize((180, 180), Image.Resampling.LANCZOS)
    apple_img.save(WEB_DIR / "apple-touch-icon.png", format="PNG")
    
    # 32x32
    img_32 = img.resize((32, 32), Image.Resampling.LANCZOS)
    img_32.save(WEB_DIR / "favicon-32x32.png", format="PNG")

    # 16x16
    img_16 = img.resize((16, 16), Image.Resampling.LANCZOS)
    img_16.save(WEB_DIR / "favicon-16x16.png", format="PNG")

    # favicon.ico (holds 16x16, 32x32, 48x48)
    img_48 = img.resize((48, 48), Image.Resampling.LANCZOS)
    img.save(
        WEB_DIR / "favicon.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48)],
    )
    print("Successfully generated favicon.ico, apple-touch-icon.png, and PNG icons!")
else:
    print("PNG_512 was not generated.")
