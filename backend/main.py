"""AI Shorts Generator - FastAPI backend.

Endpoints:
  GET  /health            -> liveness
  POST /api/generate      -> { input } -> { job_id }
  GET  /api/status/{id}   -> job status + progress (+ video_url when done)
"""
import uuid
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from pipeline import config
from pipeline.jobs import store
from pipeline.worker import enqueue, start_worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    missing = config.missing_required()
    if missing:
        log.warning("Missing required env vars: %s. /api/generate will reject requests.", missing)
    start_worker()
    yield


app = FastAPI(title="AI Shorts Generator", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In local storage mode, serve finished videos straight from disk at /media/<file>.
if config.STORAGE_MODE == "local":
    app.mount("/media", StaticFiles(directory=config.OUTPUT_DIR), name="media")


class GenerateRequest(BaseModel):
    input: str = Field(min_length=3, max_length=6000)


class GenerateResponse(BaseModel):
    job_id: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    missing = config.missing_required()
    if missing:
        raise HTTPException(status_code=503, detail=f"Server not configured: missing {', '.join(missing)}")

    text = req.input.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Input is empty.")

    job_id = uuid.uuid4().hex[:12]
    store.create(job_id, text)
    await enqueue(job_id, text)
    log.info("Queued job %s", job_id)
    return GenerateResponse(job_id=job_id)


@app.get("/api/status/{job_id}")
async def status(job_id: str):
    job = store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found (it may have expired).")
    return job.public()
