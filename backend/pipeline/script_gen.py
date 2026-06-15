"""Step 1 - Generate a narration script + scene image prompts via Groq (Llama 3.3 70B)."""
import json
import logging

from groq import Groq, RateLimitError, APIError

from . import config
from .retry import with_retries

log = logging.getLogger("pipeline.script")

SYSTEM_PROMPT = """You are a scriptwriter for viral vertical short-form videos (TikTok/Reels/YouTube Shorts).
Given a topic or a story, you produce a tight, spoken-word narration and a matching set of image prompts.

Rules:
- The narration must sound natural read aloud, be 150-230 words (about 60-90 seconds), and hook the viewer in the first sentence.
- No emojis, no hashtags, no stage directions, no "in this video". Just the words to be spoken.
- Split the visuals into 11 to 15 scenes that track the narration in order, so the video stays visually dynamic (a new image every few seconds).
- Each scene's image_prompt must depict ONE clear, concrete subject performing ONE clear action in a specific, real setting, described literally and photographically. Name visible things (e.g. "a glowing deep-sea anglerfish with a bioluminescent lure in pitch-black water, dark blue tones, close-up" — NOT "the mystery of the deep"). Avoid abstract concepts, metaphors, emotions, and anything that can't be photographed. No text or words in the image. Cinematic photo style, vertical 9:16 framing.
- Return ONLY valid JSON, no markdown fences, no commentary."""

USER_TEMPLATE = """Create a short video from the following input.

INPUT:
\"\"\"{text}\"\"\"

Return JSON with exactly this shape:
{{
  "title": "string, max 8 words",
  "script": "the full narration as one string",
  "scenes": [
    {{"image_prompt": "string"}}
  ]
}}
"""


def _client() -> Groq:
    return Groq(api_key=config.GROQ_API_KEY)


def _extract_json(raw: str) -> dict:
    """Be forgiving: strip accidental code fences and grab the outermost JSON object."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1] if "```" in raw[3:] else raw[3:]
        if raw.lstrip().startswith("json"):
            raw = raw.lstrip()[4:]
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Model did not return JSON")
    return json.loads(raw[start:end + 1])


def generate_script(text: str) -> dict:
    """Returns {"title", "script", "scenes": [{"image_prompt"}...]}."""

    def _call():
        client = _client()
        resp = client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_TEMPLATE.format(text=text[:6000])},
            ],
            temperature=0.8,
            max_tokens=2400,
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content

    raw = with_retries(
        _call,
        attempts=4,
        base_delay=3.0,
        retry_on=(RateLimitError, APIError),
        label="groq.script",
    )

    data = _extract_json(raw)

    script = (data.get("script") or "").strip()
    scenes = data.get("scenes") or []
    prompts = [s.get("image_prompt", "").strip() for s in scenes if s.get("image_prompt")]

    if not script:
        raise ValueError("Empty script returned by model")
    if len(prompts) < 3:
        # Fallback: derive a few scenes from the script so the pipeline can still run.
        prompts = _fallback_scenes(script)

    # Clamp to a sane maximum (more scenes = more images = more Cloudflare neurons).
    prompts = prompts[:15]
    log.info("Generated script (%d words) with %d scenes", len(script.split()), len(prompts))
    return {
        "title": (data.get("title") or "Your Short").strip(),
        "script": script,
        "scenes": prompts,
    }


def _fallback_scenes(script: str) -> list[str]:
    sentences = [s.strip() for s in script.replace("\n", " ").split(".") if s.strip()]
    n = min(6, max(3, len(sentences)))
    step = max(1, len(sentences) // n)
    chosen = sentences[::step][:n]
    return [f"Cinematic vertical 9:16 illustration, dramatic lighting, no text: {s}" for s in chosen]
