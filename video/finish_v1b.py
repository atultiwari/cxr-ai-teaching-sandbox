"""Turn Dr. Tiwari's QuickTime recording of ChatGPT into v1b_chatbot_same_film.mp4.

Usage: python video/finish_v1b.py <recording.mov> [--trim-start SECONDS]

Only trims dead time at the start (optional) and adds captions + the teaching label.
The chatbot's answer is not edited, cut or sped up. Output and poster go to the videos folder.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from burn_captions import build

VIDEOS = Path.home() / "Downloads/Research_Materials/Criticare-2027/videos"
OUT = VIDEOS / "v1b_chatbot_same_film.mp4"
POSTER = VIDEOS / "v1b_chatbot_same_film_poster.png"
LABEL = "Teaching and research only — not a clinical device."
MAX_MB = 20


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         check=True, capture_output=True, text=True).stdout
    return float(out.strip())


def captions(length: float) -> list[dict]:
    end = round(length - 0.05, 2)
    return [
        {"start": 0.0, "end": 5.0, "text": "The same pneumothorax film, given to a general chatbot (ChatGPT, free tier)"},
        {"start": 5.1, "end": 10.0, "text": "Prompt: “This is a chest X-ray from an ICU patient. What do you see?”"},
        {"start": max(10.1, end - 6.0), "end": end,
         "text": "Response shown unedited. A chatbot is not a cleared device: check the film yourself."},
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("recording", type=Path)
    ap.add_argument("--trim-start", type=float, default=0.0)
    a = ap.parse_args()
    length = duration(a.recording) - a.trim_start
    caps = captions(length)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(caps, fh)
    crf = 23
    while True:
        build(str(a.recording), caps, str(OUT), a.trim_start, crf, LABEL)
        size_mb = OUT.stat().st_size / 1e6
        if size_mb <= MAX_MB or crf >= 34:
            break
        crf += 3
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(round(max(0.0, length - 3.0), 2)), "-i", str(OUT),
                    "-frames:v", "1", str(POSTER)], check=True)
    print(f"{OUT} ({length:.1f} s, {size_mb:.1f} MB, crf {crf}); poster {POSTER}")
    if length > 45:
        print("Note: clip is longer than 45 s. Re-record a shorter take rather than cutting the answer.")


if __name__ == "__main__":
    main()
