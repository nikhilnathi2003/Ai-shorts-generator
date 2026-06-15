"""Step 2 - Voiceover via Edge-TTS (free, no API key).

We capture WordBoundary events during synthesis so captions can be built with zero
extra cost or RAM (the "edge" caption source). Edge reports offsets in 100ns ticks.
"""
import asyncio
import logging

import edge_tts

from . import config

log = logging.getLogger("pipeline.tts")

TICKS_PER_SECOND = 10_000_000  # edge-tts uses 100-nanosecond units


async def _synthesize(text: str, out_path: str, voice: str) -> list[dict]:
    communicate = edge_tts.Communicate(text, voice)
    words: list[dict] = []
    with open(out_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / TICKS_PER_SECOND
                dur = chunk["duration"] / TICKS_PER_SECOND
                words.append({
                    "word": chunk["text"],
                    "start": round(start, 3),
                    "end": round(start + dur, 3),
                })
    return words


def synthesize(text: str, out_path: str) -> list[dict]:
    """Write an mp3 to out_path. Returns word-boundary list [{word,start,end}].

    Runs in a worker thread (no running loop), so asyncio.run is safe here.
    """
    words = asyncio.run(_synthesize(text, out_path, config.TTS_VOICE))
    log.info("TTS done: %s (%d word boundaries)", out_path, len(words))
    return words
