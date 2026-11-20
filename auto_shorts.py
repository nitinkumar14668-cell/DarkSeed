import os
import subprocess
import random
import google.generativeai as genai
from PIL import Image, ImageDraw, ImageFont
from moviepy import *
# YouTube upload ke liye aapka existing code yahan aayega (main niche sirf core logic bata raha hoon)

# ==========================================
# 1. Setup and Configurations
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

# Example song list (Aap isko dynamic kar sakte hain)
SONGS_TO_PROCESS = [
    {"title": "Ishq Mubarak", "emotion": "romantic, warm, cinematic"},
    {"title": "Feel The Pain", "emotion": "sad, black and white, emotional, crying"},
]

def create_directories():
    os.makedirs("Video/Published And Created/Created", exist_ok=True)
    os.makedirs("temp_assets", exist_ok=True)

# ==========================================
# 2. Download Song (yt-dlp)
# ==========================================
def download_song(song_name):
    print(f"Downloading: {song_name}...")
    # YouTube se search karke audio download karega
    # Note: Copyright strike se bachne ke liye legal source use karein
    search_query = f"ytsearch1:{song_name} audio"
    subprocess.run([
        "yt-dlp", "-x", "--audio-format", "mp3", 
        "-o", "temp_assets/original_song.mp3", 
        search_query
    ], check=True)

# ==========================================
# 3. Slowed + Reverb + Lofi Edit (FFmpeg)
# ==========================================
def edit_audio():
    print("Applying Slowed + Reverb effects...")
    input_file = "temp_assets/original_song.mp3"
    output_file = "temp_assets/edited_song.mp3"
    
    # FFmpeg filter: 0.8x speed (slowed) + Echo/Reverb
    # asetrate = sample rate badal kar pitch slow karta hai
    # atempo = tempo adjust karta hai
    # aecho = reverb effect deta hai
    ffmpeg_cmd = [
        "ffmpeg", "-y", "-i", input_file,
        "-filter:a", "asetrate=44100*0.8,aresample=44100,atempo=1.0,aecho=0.8:0.9:1000:0.3",
        "-b:a", "192k", output_file
    ]
    subprocess.run(ffmpeg_cmd, check=True)
    return output_file

# ==========================================
# 4. Google AI Studio (Gemini) se Image Generate karna
# ==========================================
def generate_ai_image(song_title, emotion):
    print(f"Generating AI Image for {song_title}...")
    
    # Prompt setup (9:16 aspect ratio for Shorts)
    prompt = f"""
    A cinematic, ultra-realistic portrait for a YouTube thumbnail. 
    Mood: {emotion}. 
    Song title: {song_title}.
    Style: High contrast, moody lighting, beautiful depth of field, blurred background. 
    The image should look emotional and top-class, like a movie poster.
    Aspect ratio: 9:16 (vertical portrait).
    """
    
    try:
        # Imagen 3 model use karna (Gemini API ke through)
        model = genai.ImageGenerationModel("imagen-3.0-generate-001")
        response = model.generate_images(
            prompt=prompt,
            number_of_images=1,
            aspect_ratio="9:16",
        )
        
        image_path = "temp_assets/ai_background.png"
        response.images[0].save(image_path)
        return image_path
    except Exception as e:
        print(f"AI Image Generation failed (Fallback to gradient): {e}")
        # Fallback: Black gradient background agar API fail ho jaye
        img = Image.new('RGB', (1080, 1920), color=(20, 20, 20))
        img.save("temp_assets/ai_background.png")
        return "temp_assets/ai_background.png"

# ==========================================
# 5. Thumbnail par Text Add karna (Pillow)
# ==========================================
def create_thumbnail_with_text(image_path, song_title):
    print("Adding stylish text to thumbnail...")
    img = Image.open(image_path)
    draw = ImageDraw.Draw(img)
    
    # Fonts setup
    try:
        # GitHub action mein fonts install kar liye hain
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 120)
        font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 60)
    except:
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()

    # Text positions (Center me)
    title_text = song_title
    sub_text = "Slowed + Reverb"
    
    # Text ka shadow effect
    draw.text((540, 1500), title_text, font=font_title, fill="white", anchor="mm")
    draw.text((540, 1650), sub_text, font=font_sub, fill="yellow", anchor="mm")
    
    thumbnail_path = "temp_assets/final_thumbnail.jpg"
    img.convert("RGB").save(thumbnail_path, quality=95)
    return thumbnail_path

# ==========================================
# 6. Video Create karna (MoviePy / FFmpeg)
# ==========================================
def create_video(thumbnail_path, audio_path):
    print("Creating final YouTube Short video...")
    output_video = "Video/Published And Created/Created/short_video.mp4"
    
    # FFmpeg command to combine image + audio into video (Shorts 9:16)
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", thumbnail_path,
        "-i", audio_path,
        "-c:v", "libx264", "-tune", "stillimage",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p", "-shortest",
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920", # Force 9:16
        output_video
    ]
    subprocess.run(cmd, check=True)
    return output_video

# ==========================================
# MAIN EXECUTION
# ==========================================
def main():
    create_directories()
    
    # Random song pick karte hain (ya list se ek-ek karke process karein)
    song = random.choice(SONGS_TO_PROCESS)
    print(f"Selected Song: {song['title']}")
    
    # 1. Download
    download_song(song['title'])
    
    # 2. Edit Audio
    edited_audio = edit_audio()
    
    # 3. AI Image
    ai_image = generate_ai_image(song['title'], song['emotion'])
    
    # 4. Thumbnail
    thumbnail = create_thumbnail_with_text(ai_image, song['title'])
    
    # 5. Create Video
    video_path = create_video(thumbnail, edited_audio)
    
    print(f"Success! Video ready at: {video_path}")
    
    # 6. Yahan aapka YouTube Upload function call hoga
    # upload_to_youtube(video_path, song['title'], thumbnail)

if __name__ == "__main__":
    main()
