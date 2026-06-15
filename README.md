# AI Shorts Generator

Turn a topic or a pasted story into a captioned, vertical (1080×1920) short video.

```
topic / story
   │
   ▼
① Groq · Llama 3.3 70B   →  narration script + 11-15 scene prompts
② Edge-TTS               →  voiceover .mp3 (+ word-level timing)
③ Pollinations.ai        →  one image per scene
④ Edge timings / Whisper →  word-level caption timing
⑤ FFmpeg                 →  slideshow + voiceover + burned TikTok captions + music
⑥ Supabase Storage       →  public .mp4 link  →  shown/played in the UI
```

- **Backend:** FastAPI + an in-memory queue with one background worker (heavy video work runs one job at a time). Polled progress, not websockets.
- **Frontend:** React + Vite. A 9:16 preview frame shows queue progress live, then plays the finished video.

---

## Repo layout

```
backend/
  main.py                 FastAPI app (routes, CORS, worker startup)
  Dockerfile              installs ffmpeg + fonts (deploy as Docker on Render)
  pipeline/
    config.py             env-driven settings
    jobs.py               in-memory job store + status model
    worker.py             asyncio queue + single background worker
    runner.py             orchestrates the 6 steps for one job
    script_gen.py         ① Groq
    tts.py                ② Edge-TTS (returns word boundaries)
    images.py             ③ Pollinations
    captions.py           ④ word timing → styled .ass
    assemble.py           ⑤ FFmpeg filtergraph
    storage.py            ⑥ Supabase upload
  assets/                 drop bg_music.mp3 here (optional)
frontend/
  src/App.jsx             input + polling
  src/components/         PreviewStage, PipelineRail
render.yaml               Render blueprint (Docker)
```

---

## 1. Supabase setup (storage)

1. Create a project at supabase.com (free tier).
2. Storage → New bucket → name it `videos` → make it **Public** (so the preview link works).
   - Prefer private? Keep it private and switch `storage.py` to `create_signed_url` (a commented line is already there).
3. Project Settings → API → copy the **Project URL** and the **service_role** key.
   The service key is server-side only — it lives in the backend env, never in the frontend.

## 2. Groq setup (script generation)

Get a free API key at console.groq.com → `GROQ_API_KEY`. Model used: `llama-3.3-70b-versatile`.

## 3. Run locally

**Backend** (needs ffmpeg installed locally — `apt install ffmpeg` / `brew install ffmpeg`):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in GROQ + SUPABASE values
uvicorn main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
cp .env.example .env        # VITE_API_BASE=http://localhost:8000
npm run dev                 # http://localhost:5173
```

Optionally drop a royalty-free `bg_music.mp3` into `backend/assets/` (see that folder's README for sources).

---

## 4. Deploy

### Backend → Render (as Docker, not the native Python runtime)

ffmpeg can't be `apt`-installed on Render's native Python runtime, so the backend ships as a Docker image (the Dockerfile installs ffmpeg + fonts).

1. Push this repo to GitHub.
2. Render → New → **Blueprint** → pick the repo (`render.yaml` is detected). Or: New → Web Service → Docker → root `backend/`.
3. Set env vars: `GROQ_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `ALLOWED_ORIGINS` (your Vercel URL).
4. Deploy. Health check: `GET /health`.

### Frontend → Vercel

1. Vercel → New Project → import the repo → **Root Directory = `frontend`** (Vite is auto-detected).
2. Env var: `VITE_API_BASE = https://your-render-service.onrender.com`.
3. Deploy, then add that Vercel URL to the backend's `ALLOWED_ORIGINS` and redeploy the backend.

---

## Captions: Edge vs Whisper

`CAPTION_SOURCE` (default **`edge`**):

- **`edge`** — reuses the word-boundary timings Edge-TTS already emits while synthesizing. Free, ~exact (it's literally the spoken text), and adds **zero** RAM/CPU. Recommended, especially on free tiers.
- **`whisper`** — runs `faster-whisper` on the audio for word timestamps. Heavier; use `tiny`/`base` only. May exceed 512 MB RAM on Render free — see below.

Both feed the same styled `.ass` builder (bold, centered, white text, yellow active-word highlight with a subtle pop, thick black outline).

---

## Free-tier reality checks

- **Render free = 512 MB RAM** and spins down when idle (≈30–60s cold start on the next request). The queue + polling design means HTTP requests return instantly, so cold starts and multi-minute renders don't cause request timeouts — the worker just keeps going. faster-whisper `base` can blow the RAM ceiling; default `CAPTION_SOURCE=edge` sidesteps that. If you need Whisper, use a paid instance or the HF Inference API.
- **Processing time:** a 60–90s short typically takes **2–5 min** end to end on a small instance, dominated by image generation and the ffmpeg encode. The UI shows per-step progress throughout.
- **Pollinations** is a free community service and can be slow or intermittently fail; image fetches retry with backoff, but expect the occasional slow scene.
- **Groq rate limits** on the free tier are handled with exponential backoff + retry; a sustained burst can still 429.
- **In-memory queue/jobs** live in one process — restarting the backend drops in-flight jobs, and it won't scale past one instance. For durability/scale, swap `jobs.py` + `worker.py` for Redis/RQ (the pipeline code doesn't change).
- **Music must be yours to use.** No track ships in this repo; add a royalty-free one. `ENABLE_MUSIC=true` is ignored if `assets/bg_music.mp3` is absent.

---

## API

```
POST /api/generate   { "input": "..." }          → { "job_id": "abc123" }
GET  /api/status/:id                              → { stage, progress, message, video_url?, error? }
GET  /health                                      → { "status": "ok" }
```

Stages, in order: `queued → script → voiceover → images → captions → assembling → uploading → done` (or `error`).
