import os
import datetime
import re
import traceback
import asyncio
import cloudinary
import cloudinary.uploader
from fastapi import FastAPI, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings
from config import (
    GEMINI_API_KEY,
    CLOUDINARY_CLOUD_NAME,
    CLOUDINARY_API_KEY,
    CLOUDINARY_API_SECRET,
    ELEVENLABS_AUDIO_API_KEY,
    ELEVENLABS_VOICE_MODI,
    ELEVENLABS_VOICE_SALMAN,
    ELEVENLABS_VOICE_SRK,
)


# --------------------------
# Cloudinary Config
# --------------------------
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True,
)


# --------------------------
# FastAPI App
# --------------------------
app = FastAPI(title="AI Lesson Generator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------
# Job status store
# --------------------------
job_status = {}


# --------------------------
# Gemini & ElevenLabs Clients
# --------------------------
client = genai.Client(api_key=GEMINI_API_KEY)
elevenlabs_client = ElevenLabs(api_key=ELEVENLABS_AUDIO_API_KEY)


# --------------------------
# Request Model
# --------------------------
class LessonRequest(BaseModel):
    course: str
    topic: str
    celebrity: str
    preferences: dict | None = None


# --------------------------
# Helpers
# --------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_celebrity_voice(celebrity: str) -> str:
    voices = {
        "modi": ELEVENLABS_VOICE_MODI,
        "salman": ELEVENLABS_VOICE_SALMAN,
        "srk": ELEVENLABS_VOICE_SRK,
    }
    return voices.get(celebrity.lower(), ELEVENLABS_VOICE_MODI)  # default Modi


def get_celebrity_video(celebrity_name: str):
    input_video_dir = os.path.join(BASE_DIR, "backend", "input")
    celebrity_video = os.path.join(input_video_dir, f"{celebrity_name.lower()}.mp4")

    if os.path.exists(celebrity_video):
        print(f"🎬 Using celebrity video: {celebrity_video}")
        return celebrity_video
    else:
        input_video = os.path.join(input_video_dir, "modi.mp4")
        print(f"🎬 Using default video: {input_video}")
        return input_video


# --------------------------
# Serve Files
# --------------------------
base_output_path = os.path.join(BASE_DIR, "outputs")
video_output_path = os.path.join(base_output_path, "video")
text_output_path = os.path.join(base_output_path, "text")

os.makedirs(video_output_path, exist_ok=True)
os.makedirs(text_output_path, exist_ok=True)

app.mount("/video-stream", StaticFiles(directory=video_output_path), name="video-stream")
app.mount("/transcript-stream", StaticFiles(directory=text_output_path), name="transcript-stream")


# --------------------------
# Root & Utility Routes
# --------------------------
@app.get("/")
def home():
    return {"message": "AI Lesson Generator Backend Running"}


@app.get("/transcript/{filename}")
def get_transcript(filename: str):
    file_path = os.path.join(BASE_DIR, "outputs", "text", filename)
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"content": content}
    return {"error": "Transcript not found"}


@app.get("/status/{job_id}")
def get_status(job_id: str):
    status_data = job_status.get(job_id, {"status": "not_found"})
    if isinstance(status_data, str):
        return {"status": status_data}
    return status_data


# --------------------------
# Generate Lesson Endpoint
# --------------------------
@app.post("/generate")
async def generate_lesson(data: LessonRequest, background_tasks: BackgroundTasks):
    topic_clean = re.sub(r'[^\w\s-]', '', data.topic).strip().replace(" ", "_")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = f"{topic_clean}_{timestamp}"

    job_status[base_filename] = {"status": "processing"}

    background_tasks.add_task(process_lesson, data, base_filename)

    return {
        "status": "Processing",
        "filename": f"{base_filename}.mp4",
        "text_file": f"{base_filename}.txt",
        "audio_file": f"{base_filename}.mp3",
        "jobId": base_filename,
    }


# --------------------------
# Background Task Logic
# --------------------------
async def process_lesson(data: LessonRequest, base_filename: str):
    print("\n📥 RAW REQUEST DATA:")
    print(data.dict())
    try:
        print(f"\n🚀 Starting generation for: {data.topic} ({data.celebrity})")

        # 1️⃣ Build Preferences Context
        preferences_text = ""

        if data.preferences:
            interested_topics = data.preferences.get("interested_topics", [])
            if isinstance(interested_topics, list):
                interested_topics = ", ".join(interested_topics)

            preferences_text = f"""
        User Preferences:
        - Learning Goal: {data.preferences.get("learning_goal", "Not specified")}
        - Interested Topics: {interested_topics or "Not specified"}
        - Experience Level: {data.preferences.get("experience_level", "Not specified")}
        - Weekly Commitment: {data.preferences.get("weekly_commitment", "Not specified")}
        - Learning Style: {data.preferences.get("learning_style", "Not specified")}
        """
        else:
            preferences_text = "User Preferences: Not provided"

        print("\n📊 USER PREFERENCES:\n")
        print(data.preferences if data.preferences else "No preferences provided")

        # 2️⃣ Generate Text with Gemini
        prompt = f"""
        Create a 50 word educational explanation about '{data.topic}' in the subject '{data.course}'.

        Rules:
        - 100% English only
        - No Hindi
        - No Hinglish
        - Simple classroom teaching tone
        - Between 45 and 60 words

        Narration style inspired by the celebrity {data.celebrity}.

        {preferences_text}

        Instructions:
        - Adapt explanation based on user's experience level
        - Adjust depth based on learning goal
        - Match explanation style with preferred learning style
        """

        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            script = response.text.strip().replace("\n", " ")
            print(f"📝 Generated text: {script}")
        except Exception as e:
            print(f"❌ Gemini Error: {e}")
            job_status[base_filename] = {"status": "failed"}
            return

        # 3️⃣ Create Output Folders
        base_output_dir = os.path.join(BASE_DIR, "outputs")
        text_dir = os.path.join(base_output_dir, "text")
        audio_dir = os.path.join(base_output_dir, "audio")
        video_dir = os.path.join(base_output_dir, "video")

        os.makedirs(text_dir, exist_ok=True)
        os.makedirs(audio_dir, exist_ok=True)
        os.makedirs(video_dir, exist_ok=True)

        text_path = os.path.join(text_dir, f"{base_filename}.txt")
        audio_path = os.path.join(audio_dir, f"{base_filename}.mp3")
        final_video = os.path.join(video_dir, f"{base_filename}.mp4")

        # 4️⃣ Save Text to File
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(script)
        print(f"💾 Saved text to: {text_path}")

        # 5️⃣ Generate Audio with ElevenLabs
        print("🎵 Generating audio with ElevenLabs...")
        voice_id = get_celebrity_voice(data.celebrity)

        try:
            audio_generator = elevenlabs_client.text_to_speech.convert(
                voice_id=voice_id,
                output_format="mp3_44100_128",
                text=script,
                model_id="eleven_multilingual_v2",
                voice_settings=VoiceSettings(
                    stability=0.5,
                    similarity_boost=0.75,
                    style=0.0,
                    use_speaker_boost=True,
                ),
            )
            with open(audio_path, "wb") as f:
                for chunk in audio_generator:
                    if chunk:
                        f.write(chunk)
            print(f"✅ Audio saved: {audio_path}")
        except Exception as tts_err:
            print(f"❌ ElevenLabs TTS error: {tts_err}")
            job_status[base_filename] = {"status": "failed"}
            return

        # 6️⃣ Select Video
        input_video = get_celebrity_video(data.celebrity)
        if not os.path.exists(input_video):
            print(f"❌ Error: Video file not found at {input_video}")
            job_status[base_filename] = {"status": "failed"}
            return

        # 7️⃣ Merge Video + Audio (FFmpeg)
        ffmpeg_command = (
            f'ffmpeg -y -stream_loop -1 -i "{input_video}" '
            f'-i "{audio_path}" '
            f'-map 0:v:0 -map 1:a:0 '
            f'-c:v copy -c:a aac -shortest "{final_video}"'
        )
        print(f"🎥 Running ffmpeg command: {ffmpeg_command}")
        os.system(ffmpeg_command)

        if not os.path.exists(final_video):
            print(f"❌ FFmpeg failed — video file not found at {final_video}")
            job_status[base_filename] = {"status": "failed"}
            return

        # 8️⃣ Upload to Cloudinary
        cloudinary_url = None
        try:
            print(f"☁️ Uploading video to Cloudinary...")
            upload_result = cloudinary.uploader.upload(
                final_video,
                resource_type="video",
                folder="ai_mentor/videos",
                public_id=base_filename,
                overwrite=True,
                chunk_size=6000000,
            )
            cloudinary_url = upload_result.get("secure_url")
            print(f"✅ Cloudinary upload success: {cloudinary_url}")
        except Exception as cloud_err:
            print(f"⚠️ Cloudinary upload failed (will fall back to local proxy): {cloud_err}")

        job_status[base_filename] = {
            "status": "ready",
            "cloudinary_url": cloudinary_url,
        }
        print(f"✅ Lesson ready!")
        print(f"   Video : {final_video}")
        if cloudinary_url:
            print(f"   Cloud : {cloudinary_url}")

    except Exception as e:
        job_status[base_filename] = {"status": "failed"}
        print(f"❌ Error generating lesson: {e}")
        traceback.print_exc()