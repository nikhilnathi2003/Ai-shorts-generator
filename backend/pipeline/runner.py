"""Runs the full 6-step pipeline for one job. Pure sync; called from a worker thread."""
import os
import shutil
import logging
import tempfile

from . import config, script_gen, tts, images, captions, assemble, storage
from .jobs import store, Stage

log = logging.getLogger("pipeline.runner")


def run_pipeline(job_id: str, input_text: str):
    workdir = tempfile.mkdtemp(prefix=f"short_{job_id}_")
    try:
        # 1. Script + scenes
        store.set_stage(job_id, Stage.SCRIPT)
        result = script_gen.generate_script(input_text)
        script, scene_prompts = result["script"], result["scenes"]
        store.update(job_id, script=script)

        # 2. Voiceover (+ word boundaries for captions)
        store.set_stage(job_id, Stage.VOICEOVER)
        voice_path = os.path.join(workdir, "voice.mp3")
        edge_words = tts.synthesize(script, voice_path)

        # 3. Images
        store.set_stage(job_id, Stage.IMAGES)

        def _img_progress(done, total):
            store.update(job_id, message=f"Generating visuals ({done}/{total})")

        image_paths = images.fetch_images(scene_prompts, workdir, on_each=_img_progress)

        # 4. Captions
        store.set_stage(job_id, Stage.CAPTIONS)
        words = captions.get_word_timings(voice_path, edge_words)
        ass_path = os.path.join(workdir, "captions.ass")
        captions.build_ass(words, ass_path)

        # 5. Assemble
        store.set_stage(job_id, Stage.ASSEMBLING)
        out_path = os.path.join(workdir, "output.mp4")
        assemble.assemble(image_paths, voice_path, ass_path, out_path, workdir)

        # 6. Store (local file or Supabase, per config)
        store.set_stage(job_id, Stage.UPLOADING)
        object_name = f"{job_id}.mp4"
        url = storage.store_video(out_path, object_name)

        store.update(job_id, video_url=url)
        store.set_stage(job_id, Stage.DONE)
        log.info("Job %s complete: %s", job_id, url)

    except Exception as exc:  # noqa: BLE001 - surface any failure to the user cleanly
        log.exception("Job %s failed", job_id)
        store.update(job_id, error=str(exc))
        store.set_stage(job_id, Stage.ERROR, message="Something went wrong")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
