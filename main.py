import os
import re
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

def extract_terabox_surl(url: str):
    match = re.search(r'(?:/s/|surl=)([a-zA-Z0-9_-]+)', url)
    if not match:
        return None, None
    raw = match.group(1)
    surl_clean = raw[1:] if raw.startswith("1") else raw
    return raw, surl_clean

# Robust Multi-Gateway Terabox Resolver
async def resolve_terabox(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }

    raw_surl, surl_clean = extract_terabox_surl(url)
    if not surl_clean:
        return None

    api_endpoints = [
        f"https://terabox-api.subhampreet.workers.dev/api?url={urllib.parse.quote(url)}",
        f"https://terabox-dl.freedailycourse.com/api?url={urllib.parse.quote(url)}",
        f"https://terabox-api-seven.vercel.app/api?url={urllib.parse.quote(url)}",
        f"https://terabox.udayscripts.workers.dev/?url={urllib.parse.quote(url)}"
    ]

    for api in api_endpoints:
        try:
            r = requests.get(api, headers=headers, timeout=8)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and len(data) > 0:
                    data = data[0]
                elif isinstance(data, dict):
                    for key in ["response", "list", "data"]:
                        if key in data and isinstance(data[key], list) and len(data[key]) > 0:
                            data = data[key][0]
                            break
                
                v_url = (
                    data.get("download_link") or 
                    data.get("fast_download_link") or 
                    data.get("dlink") or 
                    data.get("url") or 
                    data.get("direct_link")
                )
                if v_url:
                    name = data.get("title") or data.get("file_name") or data.get("name") or "terabox_video.mp4"
                    return {"success": True, "type": "video", "url": v_url, "name": name}
        except Exception:
            continue

    # ফলব্যাক: ডিরেক্ট স্ট্রিম প্লেয়ার এবং এক্সটার্নাল ডাউনলোডার
    embed_url = f"https://www.terabox.com/sharing/embed?surl={surl_clean}"
    direct_downloader = f"https://teraboxdownloader.net/?url={urllib.parse.quote(url)}"
    return {
        "success": True,
        "type": "embed",
        "url": embed_url,
        "name": f"Terabox_{surl_clean}.mp4",
        "download_url": direct_downloader
    }

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
                    "type": "video",
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
        raise HTTPException(status_code=400, detail="Flezen থেকে ভিডিও লিঙ্ক পাওয়া যায়নি!")

    terabox_domains = ["terabox", "1024tera", "terashare", "freeterabox", "4funbox", "mirrobox", "tibibox"]
    if any(domain in link.lower() for domain in terabox_domains):
        res = await resolve_terabox(link)
        if res:
            return res
        raise HTTPException(status_code=400, detail="Terabox লিঙ্কটি অবৈধ বা মেয়াদোত্তীর্ণ!")

    raise HTTPException(status_code=400, detail="শুধুমাত্র Flezen অথবা Terabox লিঙ্ক সাপোর্ট করে।")

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
            .card { background: #1e293b; padding: 26px; border-radius: 16px; width: 100%; max-width: 540px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
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
            iframe { width: 100%; height: 315px; border-radius: 8px; border: none; background: #000; margin-bottom: 12px; }
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
                <input type="text" id="linkInput" placeholder="Flezen বা Terabox লিঙ্ক পেস্ট করুন...">
                <button type="button" class="btn-paste" id="pasteBtn" onclick="handlePasteAndRun()">Paste</button>
            </div>
            <button type="button" class="btn-run" id="btn" onclick="getVideo()">Video Anun</button>
            <div id="msg"></div>
            <div id="videoContainer">
                <video id="player" controls playsinline style="display:none;"></video>
                <iframe id="iframePlayer" allowfullscreen style="display:none;"></iframe>
                <a id="dlBtn" class="btn-dl" href="#" target="_blank">Direct Download</a>
            </div>
        </div>

        <script>
            function stopPreviousVideo() {
                const player = document.getElementById("player");
                const iframe = document.getElementById("iframePlayer");
                const cont = document.getElementById("videoContainer");
                try {
                    player.pause();
                    player.removeAttribute("src");
                    player.load();
                } catch(e){}
                try {
                    iframe.src = "";
                } catch(e){}
                player.style.display = "none";
                iframe.style.display = "none";
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
                        alert("Clipboard খালি!");
                    }
                } catch(err) {
                    alert("Clipboard ব্যবহারের অনুমতি দিন!");
                }
            }

            async function getVideo() {
                const input = document.getElementById("linkInput");
                const btn = document.getElementById("btn");
                const pasteBtn = document.getElementById("pasteBtn");
                const msg = document.getElementById("msg");
                const cont = document.getElementById("videoContainer");
                const player = document.getElementById("player");
                const iframe = document.getElementById("iframePlayer");
                const dl = document.getElementById("dlBtn");

                const url = input.value.trim();
                if(!url) {
                    stopPreviousVideo();
                    msg.innerText = "দয়া করে লিঙ্ক দিন!";
                    return;
                }

                stopPreviousVideo();

                btn.disabled = true;
                pasteBtn.disabled = true;
                msg.style.color = "#38bdf8";
                msg.innerText = "ভিডিও বিশ্লেষণ করা হচ্ছে...";

                try {
                    const res = await fetch("/api/fetch", {
                        method: "POST",
                        headers: {"Content-Type": "application/json"},
                        body: JSON.stringify({ url: url })
                    });
                    const d = await res.json();
                    if(res.ok && d.success) {
                        msg.innerText = "";
                        if(d.type === "embed") {
                            player.style.display = "none";
                            iframe.src = d.url;
                            iframe.style.display = "block";
                            dl.href = d.download_url || d.url;
                            dl.innerText = "🚀 ফাস্ট ডাউনলোডারে ফাইলটি খুলুন";
                        } else {
                            iframe.style.display = "none";
                            player.src = d.url;
                            player.load();
                            player.style.display = "block";
                            dl.href = d.url;
                            dl.innerText = "Direct Download MP4";
                            dl.setAttribute("download", d.name || "video.mp4");
                        }
                        cont.style.display = "block";
                    } else {
                        msg.style.color = "#f87171";
                        msg.innerText = d.detail || "ভিডিও পাওয়া যায়নি!";
                    }
                } catch(e) {
                    msg.style.color = "#f87171";
                    msg.innerText = "কানেকশন এরর হয়েছে!";
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
