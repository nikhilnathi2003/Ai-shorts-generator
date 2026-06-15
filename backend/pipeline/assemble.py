"""Step 5 - FFmpeg assembly: images + voiceover + captions + bg music -> vertical mp4.

When ENABLE_MOTION is on, each still gets a smooth Ken Burns move (alternating
zoom-in / zoom-out) and scenes are joined with crossfades, so the result reads as
a motion video instead of a slideshow. When off, it's a plain hard-cut slideshow.

Run with cwd=workdir so the subtitles filter can reference 'captions.ass' by bare
filename (avoids the Windows-path/colon escaping libass is notorious for).
"""
import os
import json
import logging
import subprocess

from . import config

log = logging.getLogger("pipeline.assemble")

XFADE = 0.45      # crossfade length between scenes (seconds)
ZOOM_TOTAL = 0.16  # how much each image zooms over its time on screen (16%)


def _probe_duration(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", path],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(out.stdout)["format"]["duration"])


def _build_audio(fc, voice_idx, music_idx, music_ok):
    if music_ok:
        fc.append(f"[{music_idx}:a]volume={config.MUSIC_VOLUME}[bg]")
        fc.append(f"[{voice_idx}:a][bg]amix=inputs=2:duration=first:dropout_transition=2[aout]")
        return "[aout]"
    return f"{voice_idx}:a"


def assemble(image_paths, voice_path, ass_path, out_path, workdir):
    audio_dur = _probe_duration(voice_path)
    n = len(image_paths)
    fps = config.FPS
    W, H = config.WIDTH, config.HEIGHT

    cmd = ["ffmpeg", "-y"]

    motion = config.ENABLE_MOTION and n >= 1
    xf = XFADE if (motion and n > 1) else 0.0

    # Per-image on-screen duration. With crossfades, overlaps eat (n-1)*xf, so pad for it.
    target = audio_dur + 0.3
    d = (target + (n - 1) * xf) / n
    d = max(d, xf + 0.7)
    seg_frames = max(2, int(round(d * fps)))

    # ---- inputs: looped stills ----
    for img in image_paths:
        cmd += ["-loop", "1", "-framerate", str(fps), "-t", f"{d:.3f}",
                "-i", os.path.basename(img)]

    voice_idx = n
    cmd += ["-i", os.path.basename(voice_path)]

    music_ok = config.ENABLE_MUSIC and os.path.exists(config.MUSIC_PATH)
    music_idx = voice_idx + 1
    if music_ok:
        cmd += ["-stream_loop", "-1", "-i", os.path.abspath(config.MUSIC_PATH)]

    fc = []

    if motion:
        pre_w, pre_h = int(W * 1.5), int(H * 1.5)
        rate = ZOOM_TOTAL / seg_frames
        for i in range(n):
            if i % 2 == 0:  # zoom in
                zexpr = f"min(1.0+{rate:.7f}*on,1.2)"
            else:           # zoom out
                zexpr = f"max(1.2-{rate:.7f}*on,1.0)"
            fc.append(
                f"[{i}:v]scale={pre_w}:{pre_h}:force_original_aspect_ratio=increase,"
                f"crop={pre_w}:{pre_h},"
                f"zoompan=z='{zexpr}':d={seg_frames}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"s={W}x{H}:fps={fps},setsar=1,format=yuv420p[v{i}]"
            )
        if n == 1:
            fc.append("[v0]copy[vmotion]")
        else:
            prev = "v0"
            for j in range(1, n):
                offset = j * (d - xf)
                label = "vmotion" if j == n - 1 else f"vx{j}"
                fc.append(
                    f"[{prev}][v{j}]xfade=transition=fade:"
                    f"duration={xf:.3f}:offset={offset:.3f}[{label}]"
                )
                prev = label
        fc.append("[vmotion]subtitles=captions.ass[vout]")
    else:
        for i in range(n):
            fc.append(
                f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
                f"crop={W}:{H},setsar=1,fps={fps},format=yuv420p[v{i}]"
            )
        concat_inputs = "".join(f"[v{i}]" for i in range(n))
        fc.append(f"{concat_inputs}concat=n={n}:v=1:a=0[vcat]")
        fc.append("[vcat]subtitles=captions.ass[vout]")

    audio_map = _build_audio(fc, voice_idx, music_idx, music_ok)

    cmd += ["-filter_complex", ";".join(fc)]
    cmd += ["-map", "[vout]", "-map", audio_map]
    cmd += [
        "-r", str(fps),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k",
        "-t", f"{audio_dur:.3f}",
        "-movflags", "+faststart",
        os.path.basename(out_path),
    ]

    log.info("Running ffmpeg (%d imgs, %.1fs audio, motion=%s, music=%s)",
             n, audio_dur, motion, music_ok)
    proc = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = proc.stderr[-2500:]
        log.error("ffmpeg failed:\n%s", tail)
        raise RuntimeError(f"ffmpeg failed: {tail}")
    return out_path
