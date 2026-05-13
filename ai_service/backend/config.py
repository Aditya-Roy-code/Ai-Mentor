import os
from dotenv import load_dotenv

load_dotenv()

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY not found. Check your .env file.")

# Cloudinary
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

if not all([
    CLOUDINARY_CLOUD_NAME,
    CLOUDINARY_API_KEY,
    CLOUDINARY_API_SECRET
]):
    raise ValueError(
        "❌ Cloudinary credentials missing. "
        "Check your .env file."
    )

# ElevenLabs
ELEVENLABS_AUDIO_API_KEY = os.getenv("ELEVENLABS_AUDIO_API_KEY")
if not ELEVENLABS_AUDIO_API_KEY:
    raise ValueError(
        "❌ ELEVENLABS_AUDIO_API_KEY missing."
    )

# Voice IDs
ELEVENLABS_VOICE_MODI = os.getenv(
    "ELEVENLABS_VOICE_MODI"
)

ELEVENLABS_VOICE_SALMAN = os.getenv(
    "ELEVENLABS_VOICE_SALMAN"
)

ELEVENLABS_VOICE_SRK = os.getenv(
    "ELEVENLABS_VOICE_SRK"
)