import os
import json
import glob
import shutil
import asyncio
from datetime import datetime, timedelta, timezone

import edge_tts
from google import genai
from google.genai import types
from moviepy import AudioFileClip, ColorClip, TextClip, CompositeVideoClip
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# --- SETTINGS ---
VOICE = "hi-IN-MadhurNeural"          # English के लिए: "en-US-ChristopherNeural"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
USED_FILE = "used_topics.txt"
LOG_FILE = "published_log.txt"
FALLBACK_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
IST = timezone(timedelta(hours=5, minutes=30))
RETENTION_DAYS = 30                   # 30 दिन बाद Created और Published से file हटेगी

# GitHub पर: VIDEO_BASE = "Video/Published And Created" (repo के अंदर)
# Termux पर: कुछ set न करें, तो ~/Video/Published And Created इस्तेमाल होगा
BASE_DIR = os.environ.get("VIDEO_BASE", os.path.expanduser("~/Video/Published And Created"))
CREATED_DIR = os.path.join(BASE_DIR, "Created")
PUBLISHED_DIR = os.path.join(BASE_DIR, "Published")

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


# --- HELPERS ---
def find_font():
    matches = (glob.glob("/usr/share/fonts/**/*Devanagari*Bold*.ttf", recursive=True)
               or glob.glob("/usr/share/fonts/**/*Devanagari*.ttf", recursive=True))
    return matches[0] if matches else FALLBACK_FONT


def load_used():
    if not os.path.exists(USED_FILE):
        return []
    with open(USED_FILE, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def save_used(topic):
    with open(USED_FILE, "a", encoding="utf-8") as f:
        f.write(topic + "\n")


def log_publish(video_id, topic, when):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{when} | {topic} | {video_id}\n")


def cleanup_old_files():
    """Created और Published folder से 30 दिन पुरानी video/audio files हटाता है।
    File का timer उसके नाम वाले timestamp (YYYYMMDD_HHMMSS) से चलता है।"""
    cutoff = datetime.now(IST) - timedelta(days=RETENTION_DAYS)
    removed = 0

    for folder in (CREATED_DIR, PUBLISHED_DIR):
        for path in glob.glob(os.path.join(folder, "*")):
            stem = os.path.splitext(os.path.basename(path))[0]
            try:
                created_at = datetime.strptime(stem, "%Y%m%d_%H%M%S").replace(tzinfo=IST)
            except ValueError:
                continue   # हमारी file नहीं है, इसे न छुएं

            if created_at < cutoff:
                os.remove(path)
                removed += 1
                print(f"Deleted (30+ days): {path}")

    print(f"Cleanup done. {removed} purani file(s) हटाई।")


# --- 1. SCRIPT + TOPIC (Gemini) ---
def get_script():
    avoid = "\n".join(load_used()[-200:]) or "कोई नहीं"
    prompt = f"""
तुम एक YouTube Shorts स्क्रिप्ट लेखक हो। एक दिलचस्प, सही तथ्यों वाला, लगभग 30 सेकंड का विषय चुनो।
ये विषय पहले इस्तेमाल हो चुके हैं, इन्हें दोबारा मत चुनो:
{avoid}

सिर्फ JSON लौटाओ:
{{"topic": "विषय का छोटा शीर्षक (हिंदी में)",
  "script": "नरेशन हिंदी (देवनागरी) में, 60 शब्दों से कम, बिना stage directions के"}}
"""
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    data = json.loads(response.text)
    return data["topic"].strip(), data["script"].strip()


# --- 2. VOICE (edge-tts, free) ---
async def generate_voice(text, path):
    await edge_tts.Communicate(text, voice=VOICE).save(path)


# --- 3. VIDEO (moviepy 2.x) ---
def create_video(title, audio_path, out_path):
    audio = AudioFileClip(audio_path)
    dur = audio.duration

    bg = ColorClip(size=(1080, 1920), color=(15, 15, 20)).with_duration(dur)  # 9:16
    txt = (TextClip(font=find_font(), text=title, font_size=80, color="yellow",
                    method="caption", size=(960, None), text_align="center")
           .with_position(("center", 500))
           .with_duration(dur))

    video = CompositeVideoClip([bg, txt], size=(1080, 1920)).with_audio(audio)
    video.write_videofile(out_path, fps=24, codec="libx264", audio_codec="aac")
    video.close()
    audio.close()


# --- 4. UPLOAD ---
def upload_to_youtube(video_path, title, description):
    creds = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": f"{title} #Shorts"[:100],
            "description": f"{description}\n\n#Shorts #facts",
            "tags": ["shorts", "facts"],
            "categoryId": "27",
        },
        "status": {
            "privacyStatus": os.environ.get("YT_PRIVACY", "private"),
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    response = youtube.videos().insert(part="snippet,status", body=body, media_body=media).execute()
    video_id = response["id"]
    print(f"Uploaded! https://youtube.com/shorts/{video_id}")
    return video_id


# --- MAIN ---
if __name__ == "__main__":
    os.makedirs(CREATED_DIR, exist_ok=True)
    os.makedirs(PUBLISHED_DIR, exist_ok=True)

    print("0. Purani files cleanup...")
    cleanup_old_files()

    now = datetime.now(IST)
    stamp = now.strftime("%Y%m%d_%H%M%S")
    audio_path = os.path.join(CREATED_DIR, f"{stamp}.mp3")
    video_path = os.path.join(CREATED_DIR, f"{stamp}.mp4")

    print("1. Script generate...")
    topic, script = get_script()
    print("Topic:", topic)
    print("Script:", script)

    print("2. Voice generate...")
    asyncio.run(generate_voice(script, audio_path))

    print("3. Video build -> Created folder...")
    create_video(topic, audio_path, video_path)

    print("4. Upload...")
    video_id = upload_to_youtube(video_path, topic, script)

    print("5. Published folder mein move...")
    for src in (video_path, audio_path):
        shutil.move(src, os.path.join(PUBLISHED_DIR, os.path.basename(src)))

    save_used(topic)
    log_publish(video_id, topic, now.strftime("%Y-%m-%d %H:%M IST"))
    print("Done.")
