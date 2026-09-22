import os
import urllib.parse
import asyncio
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import RequestWebViewRequest
import uvicorn

API_ID = 39935562
API_HASH = "0dce340be473504b335286e7cb8ce93f"

SESSION_STRING = os.getenv("SESSION_STRING", "YOUR_SESSION_STRING_HERE")

FLEZEN_BOT = "flezennbot"
WEBAPP_URL = "https://flezen-downloader.pages.dev/"
DOWNLOAD_ENDPOINT = "https://api2.diskwala.net/api/flezen/download"
STATUS_ENDPOINT = "https://api2.diskwala.net/api/flezen/status"

app = FastAPI()
user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

async def get_fresh_token():
    bot = await user_client.get_input_entity(FLEZEN_BOT)
    res = await user_client(RequestWebViewRequest(
        peer=bot, bot=bot, url=WEBAPP_URL, platform="android"
    ))
    web_url = res.url
    if "#tgWebAppData=" in web_url:
        raw_data = web_url.split("#tgWebAppData=")[1].split("&tgWebAppVersion=")[0]
    else:
        raw_data = web_url.split("tgWebAppData=")[1].split("&")[0]
    return f"Bearer {urllib.parse.unquote(raw_data)}"

class URLPayload(BaseModel):
    url: str

# Multi-API Stable Terabox Resolver
async def resolve_terabox(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    api_list = [
        f"https://yt-video-production.up.railway.app/terabox?url={urllib.parse.quote(url)}",
        f"https://teraboxvideodownloader.nepcoderdevs.workers.dev/?url={urllib.parse.quote(url)}",
        f"https://terabox-api.frontbench.fun/api/yt?url={urllib.parse.quote(url)}"
    ]

    for api_url in api_list:
        try:
            res = requests.get(api_url, headers=headers, timeout=12)
            if res.status_code == 200:
                data = res.json()
                
                if isinstance(data, dict):
                    items = data.get("response") or data.get("list") or data.get("data")
                    if isinstance(items, list) and len(items) > 0:
                        data = items[0]

                    v_url = data.get("download_link") or data.get("fast_download_link") or data.get("url") or data.get("direct_link")
                    name = data.get("title") or data.get("file_name") or data.get("name") or "terabox_video.mp4"
                    if v_url:
                        return {"success": True, "url": v_url, "name": name}

                elif isinstance(data, list) and len(data) > 0:
                    first = data[0]
                    v_url = first.get("download_link") or first.get("fast_download_link") or first.get("url")
                    name = first.get("title") or first.get("name") or "terabox_video.mp4"
                    if v_url:
                        return {"success": True, "url": v_url, "name": name}
        except Exception:
            continue

    return None

# Flezen Resolver
async def resolve_flezen(url: str):
    try:
        token = await get_fresh_token()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Token error: {str(e)}")

    headers = {
        "Accept": "*/*",
        "Authorization": token,
        "Content-Type": "application/json",
        "Origin": "https://flezen-downloader.pages.dev",
        "Referer": "https://flezen-downloader.pages.dev/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "X-Bot-Id": "flezen"
    }

    try:
        requests.post(DOWNLOAD_ENDPOINT, json={"link": url}, headers=headers, timeout=15)
    except Exception:
        pass

    loop = asyncio.get_event_loop()
    start_time = loop.time()
    while loop.time() - start_time < 45:
        try:
            s_res = requests.get(STATUS_ENDPOINT, params={"link": url}, headers=headers, timeout=15)
            s_data = s_res.json()
            if s_data.get("ok") and s_data.get("status") == "done":
                file_info = s_data.get("file", {})
                return {
                    "success": True,
                    "url": file_info.get("url"),
                    "name": file_info.get("name", "video.mp4")
                }
            elif not s_data.get("ok") or s_data.get("status") == "error":
                return None
        except Exception:
            pass
        await asyncio.sleep(2)
    return None

@app.post("/api/fetch")
async def fetch_video(payload: URLPayload):
    link = payload.url.strip()
    
    if "flezen.com/s/" in link:
        res = await resolve_flezen(link)
        if res:
            return res
        raise HTTPException(status_code=400, detail="Flezen theke video link paoa jayni!")

    terabox_domains = ["terabox.com", "1024tera.com", "teraboxapp.com", "terasharelink.com", "freeterabox.com"]
    if any(domain in link for domain in terabox_domains):
        res = await resolve_terabox(link)
        if res:
            return res
        raise HTTPException(status_code=400, detail="Terabox server theke video link process kora jayni!")

    raise HTTPException(status_code=400, detail="Unsupported URL! Sudhu Flezen ba Terabox link support kore.")

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html lang="bn">
    <head>
        <meta charset="UTF-8">
        <title>Flezen & Terabox Downloader</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { font-family: system-ui, sans-serif; background: #0b0f19; color: #f8fafc; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }
            .card { background: #1e293b; padding: 26px; border-radius: 16px; width: 100%; max-width: 520px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
            h2 { color: #38bdf8; text-align: center; margin-top: 0; }
            p.sub { text-align: center; color: #94a3b8; font-size: 13px; margin-top: -8px; margin-bottom: 15px; }
            .input-group { display: flex; gap: 8px; margin: 15px 0 10px 0; }
            input { flex: 1; padding: 13px; border-radius: 8px; border: 1px solid #334155; background: #0f172a; color: #fff; outline: none; font-size: 14px; }
            .btn-paste { padding: 0 16px; background: #64748b; color: #fff; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; }
            .btn-paste:hover { background: #475569; }
            .btn-run { width: 100%; padding: 13px; background: #0284c7; color: white; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; font-size: 15px; }
            .btn-run:hover { background: #0369a1; }
            .btn-run:disabled, .btn-paste:disabled { opacity: 0.5; cursor: not-allowed; }
            #videoContainer { margin-top: 20px; display: none; }
            video { width: 100%; border-radius: 8px; background: #000; margin-bottom: 12px; }
            .btn-dl { display: block; text-align: center; background: #10b981; color: white; padding: 12px; border-radius: 8px; text-decoration: none; font-weight: bold; }
            .btn-dl:hover { background: #059669; }
            #msg { text-align: center; color: #38bdf8; min-height: 20px; font-size: 14px; margin-top: 10px; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Direct Video Player</h2>
            <p class="sub">Flezen & Terabox Ad-Free Downloader</p>
            <div class="input-group">
                <input type="text" id="linkInput" placeholder="Flezen ba Terabox link paste korun...">
                <button type="button" class="btn-paste" id="pasteBtn" onclick="handlePasteAndRun()">Paste</button>
            </div>
            <button type="button" class="btn-run" id="btn" onclick="getVideo()">Video Anun</button>
            <div id="msg"></div>
            <div id="videoContainer">
                <video id="player" controls playsinline></video>
                <a id="dlBtn" class="btn-dl" href="#" target="_blank">Direct Download MP4</a>
            </div>
        </div>

        <script>
            function stopPreviousVideo() {
                const player = document.getElementById("player");
                const cont = document.getElementById("videoContainer");
                try {
                    player.pause();
                    player.removeAttribute("src");
                    player.load();
                } catch(e){}
                cont.style.display = "none";
            }

            document.getElementById("linkInput").addEventListener("input", function() {
                if(this.value.trim() === "") {
                    stopPreviousVideo();
                    document.getElementById("msg").innerText = "";
                }
            });

            async function handlePasteAndRun() {
                try {
                    const text = await navigator.clipboard.readText();
                    if(text) {
                        const input = document.getElementById("linkInput");
                        input.value = text.trim();
                        getVideo();
                    } else {
                        alert("Clipboard khali!");
                    }
                } catch(err) {
                    alert("Clipboard access permission proyojon!");
                }
            }

            async function getVideo() {
                const input = document.getElementById("linkInput");
                const btn = document.getElementById("btn");
                const pasteBtn = document.getElementById("pasteBtn");
                const msg = document.getElementById("msg");
                const cont = document.getElementById("videoContainer");
                const player = document.getElementById("player");
                const dl = document.getElementById("dlBtn");

                const url = input.value.trim();
                if(!url) {
                    stopPreviousVideo();
                    msg.innerText = "Doya kore link paste korun!";
                    return;
                }

                stopPreviousVideo();

                btn.disabled = true;
                pasteBtn.disabled = true;
                msg.style.color = "#38bdf8";
                msg.innerText = "Processing video... Opekkha korun.";

                try {
                    const res = await fetch("/api/fetch", {
                        method: "POST",
                        headers: {"Content-Type": "application/json"},
                        body: JSON.stringify({ url: url })
                    });
                    const d = await res.json();
                    if(res.ok && d.success) {
                        msg.innerText = "";
                        player.src = d.url;
                        player.load();
                        dl.href = d.url;
                        dl.setAttribute("download", d.name || "video.mp4");
                        cont.style.display = "block";
                    } else {
                        msg.style.color = "#f87171";
                        msg.innerText = d.detail || "Video link paoa jayni!";
                    }
                } catch(e) {
                    msg.style.color = "#f87171";
                    msg.innerText = "Connection error ba timeout!";
                } finally {
                    btn.disabled = false;
                    pasteBtn.disabled = false;
                }
            }
        </script>
    </body>
    </html>
    """

@app.on_event("startup")
async def on_startup():
    await user_client.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
