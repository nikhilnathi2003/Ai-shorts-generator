"""Simple in-memory queue with one background worker.

Video work is CPU/RAM heavy, so we process one job at a time. The HTTP handler
returns immediately with a job id; the worker drains the queue in the background.
Swap asyncio.Queue for Redis/RQ to scale beyond a single instance.
"""
import asyncio
import logging

from .runner import run_pipeline
from .jobs import store

log = logging.getLogger("pipeline.worker")

_queue: asyncio.Queue | None = None
_worker_task: asyncio.Task | None = None


def get_queue() -> asyncio.Queue:
    global _queue
    if _queue is None:
        _queue = asyncio.Queue()
    return _queue


async def enqueue(job_id: str, input_text: str):
    await get_queue().put((job_id, input_text))


async def _worker_loop():
    q = get_queue()
    loop = asyncio.get_running_loop()
    log.info("Worker started")
    while True:
        job_id, input_text = await q.get()
        try:
            store.prune()
            # run_pipeline is blocking -> push to the default thread pool.
            await loop.run_in_executor(None, run_pipeline, job_id, input_text)
        except Exception:  # noqa: BLE001
            log.exception("Worker crashed on job %s", job_id)
        finally:
            q.task_done()


def start_worker():
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_worker_loop())
    return _worker_task
