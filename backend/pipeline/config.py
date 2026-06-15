"""Central config pulled from environment variables."""
import os
from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


# --- Required ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# --- Storage ---
# "local"  -> save the mp4 to OUTPUT_DIR and serve it from the backend (no cloud, no keys)
# "supabase" -> upload to Supabase Storage and return a public URL (needed for deploys)
STORAGE_MODE = os.getenv("STORAGE_MODE", "local").strip().lower()
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "videos")

# For local mode: where finished videos are saved, and the base URL the frontend plays from.
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "outputs"))
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- CORS ---
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",") if o.strip()
]

# --- Tunables ---
CAPTION_SOURCE = os.getenv("CAPTION_SOURCE", "edge").strip().lower()  # "edge" | "whisper"
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "tiny")
TTS_VOICE = os.getenv("TTS_VOICE", "en-US-AndrewMultilingualNeural")
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "flux")
# Optional Pollinations token (legacy; their free/anon access is currently closed).
POLLINATIONS_TOKEN = os.getenv("POLLINATIONS_TOKEN", "").strip()

# Together AI - free FLUX.1-schnell image endpoint (the active image provider).
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", "").strip()
TOGETHER_IMAGE_MODEL = os.getenv("TOGETHER_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell-Free")
ENABLE_MUSIC = _bool("ENABLE_MUSIC", True)
MUSIC_VOLUME = float(os.getenv("MUSIC_VOLUME", "0.10"))
ENABLE_MOTION = _bool("ENABLE_MOTION", False)
CAPTION_CHUNK_WORDS = int(os.getenv("CAPTION_CHUNK_WORDS", "3"))

GROQ_MODEL = "llama-3.3-70b-versatile"

# Video output spec
WIDTH, HEIGHT, FPS = 1080, 1920, 30

# Where the music file lives (optional)
MUSIC_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "bg_music.mp3")


def missing_required() -> list[str]:
    """Return names of required vars that are unset, for a clear startup error."""
    missing = []
    if not GROQ_API_KEY:
        missing.append("GROQ_API_KEY")
    if STORAGE_MODE == "supabase":
        if not SUPABASE_URL:
            missing.append("SUPABASE_URL")
        if not SUPABASE_SERVICE_KEY:
            missing.append("SUPABASE_SERVICE_KEY")
    return missing
