"""In-memory job store + status model.

Single-process only (fine for an MVP on one Render instance). For multi-instance
or durability, swap this dict for Redis/DB without touching the pipeline code.
"""
import time
import threading
from dataclasses import dataclass, field, asdict
from enum import Enum


class Stage(str, Enum):
    QUEUED = "queued"
    SCRIPT = "script"
    VOICEOVER = "voiceover"
    IMAGES = "images"
    CAPTIONS = "captions"
    ASSEMBLING = "assembling"
    UPLOADING = "uploading"
    DONE = "done"
    ERROR = "error"


# Human-readable label + the progress % we report when a stage *starts*.
STAGE_META = {
    Stage.QUEUED: ("Waiting in queue", 2),
    Stage.SCRIPT: ("Writing the script", 10),
    Stage.VOICEOVER: ("Recording the voiceover", 28),
    Stage.IMAGES: ("Generating visuals", 45),
    Stage.CAPTIONS: ("Timing the captions", 64),
    Stage.ASSEMBLING: ("Editing the video", 78),
    Stage.UPLOADING: ("Uploading your short", 94),
    Stage.DONE: ("Done", 100),
    Stage.ERROR: ("Failed", 100),
}


@dataclass
class Job:
    id: str
    input_text: str
    stage: Stage = Stage.QUEUED
    progress: int = 2
    message: str = "Waiting in queue"
    error: str | None = None
    video_url: str | None = None
    script: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def public(self) -> dict:
        d = asdict(self)
        d["stage"] = self.stage.value
        # Don't leak the full input text back; keep payload small.
        d.pop("input_text", None)
        return d


class JobStore:
    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, job_id: str, input_text: str) -> Job:
        job = Job(id=job_id, input_text=input_text)
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def set_stage(self, job_id: str, stage: Stage, message: str | None = None):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            label, pct = STAGE_META[stage]
            job.stage = stage
            job.progress = pct
            job.message = message or label
            job.updated_at = time.time()

    def update(self, job_id: str, **kwargs):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            for k, v in kwargs.items():
                setattr(job, k, v)
            job.updated_at = time.time()

    def prune(self, older_than_secs: int = 3600):
        """Drop finished jobs older than an hour to bound memory."""
        cutoff = time.time() - older_than_secs
        with self._lock:
            dead = [
                jid for jid, j in self._jobs.items()
                if j.stage in (Stage.DONE, Stage.ERROR) and j.updated_at < cutoff
            ]
            for jid in dead:
                self._jobs.pop(jid, None)


store = JobStore()
