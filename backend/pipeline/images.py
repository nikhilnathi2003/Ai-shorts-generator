"""Step 3 - Generate one image per scene via Cloudflare Workers AI (free FLUX.1-schnell).

Gemini's free image tier is now 0 (needs billing) and Pollinations/Together are closed,
so Cloudflare is the working free image source (10,000 neurons/day, no card).

If you ever enable Gemini billing and want that quality, say so and we'll switch back
with a Cloudflare fallback.

FLUX outputs ~1024x1024; the assemble step crops/scales it to the final 1080x1920.
"""
import os
import base64
import logging

import requests

from .retry import with_retries

log = logging.getLogger("pipeline.images")

MODEL = "@cf/black-forest-labs/flux-1-schnell"


def _fetch_one(prompt: str, seed: int, dest: str) -> str:
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    api_token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    if not account_id or not api_token:
        raise RuntimeError(
            "CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN must both be set in backend/.env "
            "(free at https://dash.cloudflare.com)."
        )

    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{MODEL}"
    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
    # schnell is distilled for few steps; 6 gives a bit more coherence than 4 for cheap.
    payload = {"prompt": prompt[:2000], "steps": 6, "seed": seed}

    def _get():
        r = requests.post(url, headers=headers, json=payload, timeout=120)
        if r.status_code >= 400:
            try:
                detail = r.json()
            except Exception:
                detail = r.text[:300]
            raise RuntimeError(f"Cloudflare {r.status_code}: {detail}")
        data = r.json()
        if not data.get("success", True) and data.get("errors"):
            raise RuntimeError(f"Cloudflare error: {data.get('errors')}")
        b64 = data["result"]["image"]
        raw = base64.b64decode(b64)
        if len(raw) < 1024:
            raise RuntimeError(f"Cloudflare returned a tiny image ({len(raw)} bytes)")
        return raw

    content = with_retries(_get, attempts=4, base_delay=4.0, label=f"cloudflare[{seed}]")
    with open(dest, "wb") as f:
        f.write(content)
    return dest


def fetch_images(prompts: list[str], workdir: str, on_each=None) -> list[str]:
    """Generate one image per prompt. Returns ordered list of file paths."""
    paths = []
    total = len(prompts)
    for i, prompt in enumerate(prompts):
        dest = os.path.join(workdir, f"scene_{i:02d}.jpg")
        _fetch_one(prompt, seed=1000 + i, dest=dest)
        paths.append(dest)
        log.info("Image %d/%d saved", i + 1, total)
        if on_each:
            on_each(i + 1, total)
    return paths
