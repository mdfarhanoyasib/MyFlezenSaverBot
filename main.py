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

# Environment Variable অথবা সরাসরি সেশন স্ট্রিং বসান
SESSION_STRING = os.getenv("SESSION_STRING", "আপনার_কপি_করা_STRING_SESSION_এখানে_দিন")

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

@app.post("/api/fetch")
async def fetch_video(payload: URLPayload):
    link = payload.url.strip()
    if not link.startswith("https://flezen.com/s/"):
        raise HTTPException(status_code=400, detail="ভুল Flezen লিঙ্ক!")

    try:
        token = await get_fresh_token()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"টোকেন এরর: {str(e)}")

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
        requests.post(DOWNLOAD_ENDPOINT, json={"link": link}, headers=headers, timeout=15)
    except Exception:
        pass

    start_time = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start_time < 45:
        try:
            s_res = requests.get(STATUS_ENDPOINT, params={"link": link}, headers=headers, timeout=15)
            s_data = s_res.json()
            if s_data.get("ok") and s_data.get("status") == "done":
                file_info = s_data.get("file", {})
                return {
                    "success": True,
                    "url": file_info.get("url"),
                    "name": file_info.get("name", "video.mp4")
                }
            elif not s_data.get("ok") or s_data.get("status") == "error":
                raise HTTPException(status_code=400, detail="সার্ভার থেকে ভিডিও পাওয়া যায়নি!")
        except Exception:
            pass
        await asyncio.sleep(2)

    raise HTTPException(status_code=408, detail="টাইমআউট! আবার চেষ্টা করুন।")

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html lang="bn">
    <head>
        <meta charset="UTF-8">
        <title>Flezen Downloader</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { font-family: sans-serif; background: #0b0f19; color: #f8fafc; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 20px; }
            .card { background: #1e293b; padding: 30px; border-radius: 16px; width: 100%; max-width: 520px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
            h2 { color: #38bdf8; text-align: center; }
            input { width: 100%; padding: 14px; border-radius: 8px; border: 1px solid #334155; background: #0f172a; color: #fff; box-sizing: border-box; margin: 15px 0; outline: none; }
            button { width: 100%; padding: 14px; background: #0284c7; color: white; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; }
            #videoContainer { margin-top: 20px; display: none; }
            video { width: 100%; border-radius: 8px; background: #000; margin-bottom: 12px; }
            .btn { display: block; text-align: center; background: #10b981; color: white; padding: 12px; border-radius: 8px; text-decoration: none; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Flezen Direct Player</h2>
            <input type="text" id="linkInput" placeholder="Flezen লিঙ্ক পেস্ট করুন...">
            <button id="btn" onclick="getVideo()">ভিডিও আনুন</button>
            <p id="msg" style="text-align:center; color:#38bdf8;"></p>
            <div id="videoContainer">
                <video id="player" controls playsinline></video>
                <a id="dlBtn" class="btn" href="#" target="_blank">ফ্রি ডাউনলোড MP4</a>
            </div>
        </div>
        <script>
            async function getVideo() {
                const url = document.getElementById("linkInput").value.trim();
                const btn = document.getElementById("btn");
                const msg = document.getElementById("msg");
                const cont = document.getElementById("videoContainer");
                if(!url) return alert("লিঙ্ক দিন!");
                btn.disabled = true;
                cont.style.display = "none";
                msg.innerText = "ভিডিও সংগ্রহ করা হচ্ছে...";
                try {
                    const res = await fetch("/api/fetch", {
                        method: "POST",
                        headers: {"Content-Type": "application/json"},
                        body: JSON.stringify({ url: url })
                    });
                    const d = await res.json();
                    if(res.ok && d.success) {
                        msg.innerText = "";
                        document.getElementById("player").src = d.url;
                        const dl = document.getElementById("dlBtn");
                        dl.href = d.url;
                        dl.setAttribute("download", d.name);
                        cont.style.display = "block";
                    } else {
                        msg.innerText = d.detail || "সমস্যা হয়েছে!";
                    }
                } catch(e) {
                    msg.innerText = "কানেকশন এরর!";
                } finally {
                    btn.disabled = false;
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