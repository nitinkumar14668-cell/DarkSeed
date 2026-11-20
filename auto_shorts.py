import os
import subprocess
import random
import google.generativeai as genai
from PIL import Image, ImageDraw, ImageFont

# ==========================================
# 1. Setup and Configurations
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
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
    search_query = f"ytsearch1:{song_name} audio"
    # '-f bestaudio' add kiya hai taaki sabse best audio mile
    subprocess.run([
        "yt-dlp", "-x", "--audio-format", "mp3", "-f", "bestaudio",
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
    
    prompt = f"""
    A cinematic, ultra-realistic portrait for a YouTube thumbnail. 
    Mood: {emotion}. 
    Song title: {song_title}.
    Style: High contrast, moody lighting, beautiful depth of field, blurred background. 
    The image should look emotional and top-class, like a movie poster.
    Vertical portrait, 9:16 aspect ratio.
    """
    
    try:
        # Imagen 3 model use karna
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
    
    # Image ka size fix karte hain (1080x1920) taaki text sahi jagah baithe
    img = img.resize((1080, 1920))
    
    draw = ImageDraw.Draw(img)
    
    # Fonts setup
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 120)
        font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 60)
    except:
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()

    title_text = song_title
    sub_text = "Slowed + Reverb"
    
    # Text ka shadow effect ke liye thoda offset
    draw.text((542, 1502), title_text, font=font_title, fill="black", anchor="mm")
    draw.text((540, 1500), title_text, font=font_title, fill="white", anchor="mm")
    
    draw.text((542, 1652), sub_text, font=font_sub, fill="black", anchor="mm")
    draw.text((540, 1650), sub_text, font=font_sub, fill="yellow", anchor="mm")
    
    thumbnail_path = "temp_assets/final_thumbnail.jpg"
    img.convert("RGB").save(thumbnail_path, quality=95)
    return thumbnail_path

# ==========================================
# 6. Video Create karna (FFmpeg) - MoviePy Removed
# ==========================================
def create_video(thumbnail_path, audio_path):
    print("Creating final YouTube Short video...")
    output_video = "Video/Published And Created/Created/short_video.mp4"
    
    # FFmpeg command: Image + Audio = Video (9:16)
    # -r 1 lagaya hai taaki still image process karne mein RAM na khaye
    # -t 59 lagaya hai taaki Shorts 60 seconds se lamba na ho
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-framerate", "1", "-i", thumbnail_path,
        "-i", audio_path,
        "-c:v", "libx264", "-tune", "stillimage",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p", "-shortest",
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
        "-t", "59", # YouTube Shorts max 60s
        output_video
    ]
    subprocess.run(cmd, check=True)
    return output_video

# ==========================================
# MAIN EXECUTION
# ==========================================
def main():
    create_directories()
    
    song = random.choice(SONGS_TO_PROCESS)
    print(f"Selected Song: {song['title']}")
    
    download_song(song['title'])
    edited_audio = edit_audio()
    ai_image = generate_ai_image(song['title'], song['emotion'])
    thumbnail = create_thumbnail_with_text(ai_image, song['title'])
    video_path = create_video(thumbnail, edited_audio)
    
    print(f"Success! Video ready at: {video_path}")
    
    # 6. Yahan aapka YouTube Upload function call hoga
    # upload_to_youtube(video_path, song['title'], thumbnail)

if __name__ == "__main__":
    main()
