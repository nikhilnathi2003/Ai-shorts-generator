"""Step 4 - Caption timing -> styled .ass subtitles.

Two sources of word timings:
  - "edge"   : reuse the WordBoundary data captured during TTS (free, no extra RAM).
  - "whisper": run faster-whisper on the audio for word-level timestamps.

We emit ASS (not SRT) because libass lets us do the bold, centered, yellow-on-black
TikTok look with a per-word highlight + pop, which plain SRT can't express.
"""
import logging

from . import config

log = logging.getLogger("pipeline.captions")

# ASS colors are &HAABBGGRR
COL_WHITE = "&H00FFFFFF"
COL_YELLOW = "&H0000FFFF"


def get_word_timings(audio_path: str, edge_words: list[dict]) -> list[dict]:
    if config.CAPTION_SOURCE == "whisper":
        return _whisper_words(audio_path)
    return edge_words or []


def _whisper_words(audio_path: str) -> list[dict]:
    from faster_whisper import WhisperModel  # lazy import; heavy

    log.info("Loading faster-whisper model: %s", config.WHISPER_MODEL)
    model = WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(audio_path, word_timestamps=True)
    words = []
    for seg in segments:
        for w in (seg.words or []):
            token = w.word.strip()
            if token:
                words.append({"word": token, "start": round(w.start, 3), "end": round(w.end, 3)})
    log.info("Whisper produced %d words", len(words))
    return words


def _ts(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs == 100:
        cs = 0
        s += 1
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _clean(word: str) -> str:
    return word.replace("{", "(").replace("}", ")").replace("\n", " ").strip()


def _header() -> str:
    # Font size/outline tuned for 1080x1920. DejaVu Sans ships in the Docker image.
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {config.WIDTH}
PlayResY: {config.HEIGHT}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,DejaVu Sans,96,{COL_WHITE},{COL_WHITE},&H00000000,&H64000000,1,0,0,0,100,100,1,0,1,6,3,2,80,80,720,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, Effect, Text
"""


def build_ass(words: list[dict], out_path: str) -> str:
    """One event per spoken word, contiguous in time, so exactly one caption line
    is ever on screen. Each event shows the word's small phrase chunk with the
    active word colored yellow and given a subtle pop. No overlapping layers, so
    nothing doubles or misaligns.
    """
    lines = [_header()]
    chunk_size = max(1, config.CAPTION_CHUNK_WORDS)
    n = len(words)

    for idx, w in enumerate(words):
        c = idx // chunk_size
        chunk = words[c * chunk_size: c * chunk_size + chunk_size]
        tokens = [_clean(x["word"]) for x in chunk]
        local = idx - c * chunk_size

        start = w["start"]
        # Hold each word until the next one starts -> no gaps, no flicker.
        if idx + 1 < n:
            end = words[idx + 1]["start"]
        else:
            end = w["end"] + 0.6
        if end <= start:
            end = start + 0.2

        parts = []
        for k, tok in enumerate(tokens):
            if k == local:
                parts.append(
                    f"{{\\c{COL_YELLOW}\\fscx100\\fscy100"
                    f"\\t(0,80,\\fscx110\\fscy110)}}{tok}{{\\r}}"
                )
            else:
                parts.append(tok)
        text = " ".join(parts)
        lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Cap,,0,0,,{text}")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log.info("Wrote ASS captions: %s (%d words)", out_path, n)
    return out_path
