import asyncio
import json
import os
import subprocess
import time
import base64
import urllib.request
from app.auth import create_session_token

TOKEN = create_session_token("admin")
SCREENSHOT_DIR = "/Volumes/mydata/Users/Adsmedia/Development/Apps/tts-local/docs/screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = 9222

chrome_proc = subprocess.Popen([
    CHROME_BIN,
    "--headless=new",
    f"--remote-debugging-port={PORT}",
    "--window-size=1280,900",
    "--hide-scrollbars",
    "about:blank"
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

time.sleep(1.5)

try:
    with urllib.request.urlopen(f"http://localhost:{PORT}/json") as resp:
        targets = json.loads(resp.read().decode())
    ws_url = targets[0]["webSocketDebuggerUrl"]
    print(f"Connected to Chrome at: {ws_url}")
except Exception as e:
    print(f"Failed to connect to Chrome: {e}")
    chrome_proc.terminate()
    exit(1)

import websockets

async def run_cdp():
    async with websockets.connect(ws_url, max_size=50 * 1024 * 1024) as ws:
        msg_id = 0

        async def send(method, params=None):
            nonlocal msg_id
            msg_id += 1
            payload = {"id": msg_id, "method": method, "params": params or {}}
            await ws.send(json.dumps(payload))
            while True:
                resp = json.loads(await ws.recv())
                if resp.get("id") == msg_id:
                    return resp.get("result", {})

        await send("Network.enable")
        await send("Page.enable")

        # Set auth session cookie
        await send("Network.setCookie", {
            "name": "tts_local_session",
            "value": TOKEN,
            "domain": "localhost",
            "path": "/"
        })

        # Navigate to homepage
        print("Navigating to http://localhost:8000/ ...")
        await send("Page.navigate", {"url": "http://localhost:8000/"})
        await asyncio.sleep(2.0)

        # Tab 1: TTS Studio
        print("Capturing 01_tts_studio.png ...")
        await send("Runtime.evaluate", {"expression": "window.Alpine.store ? null : null; document.querySelector('button[class*=\"border-indigo-500\"]').click();"})
        await asyncio.sleep(1.5)
        res = await send("Page.captureScreenshot", {"format": "png"})
        with open(f"{SCREENSHOT_DIR}/01_tts_studio.png", "wb") as f:
            f.write(base64.b64decode(res["data"]))

        # Tab 2: Whisper STT
        print("Capturing 02_whisper_stt.png ...")
        await send("Runtime.evaluate", {"expression": "Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Whisper STT')).click();"})
        await asyncio.sleep(1.5)
        res = await send("Page.captureScreenshot", {"format": "png"})
        with open(f"{SCREENSHOT_DIR}/02_whisper_stt.png", "wb") as f:
            f.write(base64.b64decode(res["data"]))

        # Tab 3: Voice Clones
        print("Capturing 03_voice_clones.png ...")
        await send("Runtime.evaluate", {"expression": "Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Voice Clones')).click();"})
        await asyncio.sleep(1.0)
        res = await send("Page.captureScreenshot", {"format": "png"})
        with open(f"{SCREENSHOT_DIR}/03_voice_clones.png", "wb") as f:
            f.write(base64.b64decode(res["data"]))

        # Tab 4: API Docs
        print("Capturing 04_api_docs.png ...")
        await send("Runtime.evaluate", {"expression": "Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('API Docs')).click();"})
        await asyncio.sleep(1.0)
        res = await send("Page.captureScreenshot", {"format": "png"})
        with open(f"{SCREENSHOT_DIR}/04_api_docs.png", "wb") as f:
            f.write(base64.b64decode(res["data"]))

        # Tab 5: System & Hardware
        print("Capturing 05_system_info.png ...")
        await send("Runtime.evaluate", {"expression": "Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('System & Credits')).click();"})
        await asyncio.sleep(1.0)
        res = await send("Page.captureScreenshot", {"format": "png"})
        with open(f"{SCREENSHOT_DIR}/05_system_info.png", "wb") as f:
            f.write(base64.b64decode(res["data"]))

        # Tab 6: Settings
        print("Capturing 06_settings.png ...")
        await send("Runtime.evaluate", {"expression": "Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Settings')).click();"})
        await asyncio.sleep(1.0)
        res = await send("Page.captureScreenshot", {"format": "png"})
        with open(f"{SCREENSHOT_DIR}/06_settings.png", "wb") as f:
            f.write(base64.b64decode(res["data"]))

        print("All screenshots successfully captured!")

try:
    asyncio.run(run_cdp())
finally:
    chrome_proc.terminate()
