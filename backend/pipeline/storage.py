"""Step 6 - Persist the final mp4 and return a URL the frontend can play.

Two modes (config.STORAGE_MODE):
  "local"    -> copy into OUTPUT_DIR; served by the backend at /media/<file>
  "supabase" -> upload to Supabase Storage; return its public URL
"""
import os
import shutil
import logging

from . import config

log = logging.getLogger("pipeline.storage")


def _save_local(local_path: str, object_name: str) -> str:
    dest = os.path.join(config.OUTPUT_DIR, object_name)
    shutil.copyfile(local_path, dest)
    url = f"{config.PUBLIC_BASE_URL}/media/{object_name}"
    log.info("Saved video locally: %s  (%s)", dest, url)
    return url


def _upload_supabase(local_path: str, object_name: str) -> str:
    from supabase import create_client  # imported lazily so local mode needs no keys

    client = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)
    bucket = client.storage.from_(config.SUPABASE_BUCKET)

    with open(local_path, "rb") as f:
        data = f.read()

    bucket.upload(
        path=object_name,
        file=data,
        file_options={"content-type": "video/mp4", "upsert": "true"},
    )

    # Works when the bucket is public. For a private bucket, swap to a signed URL:
    #   return bucket.create_signed_url(object_name, 60 * 60 * 24)["signedURL"]
    public_url = bucket.get_public_url(object_name)
    log.info("Uploaded to Supabase: %s", public_url)
    return public_url


def store_video(local_path: str, object_name: str) -> str:
    """Dispatch to the configured storage backend."""
    if config.STORAGE_MODE == "supabase":
        return _upload_supabase(local_path, object_name)
    return _save_local(local_path, object_name)
