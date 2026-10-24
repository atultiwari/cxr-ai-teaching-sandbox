"""Burn caption bars into a silent video and export H.264 1920x1080 30 fps, no audio.

Usage: python video/burn_captions.py <in-video> <captions.json> <out.mp4> [--trim START] [--crf 23] [--label TEXT]

captions.json: [{"start": 0.0, "end": 3.5, "text": "..."}]  (seconds, after trimming)
Captions are large white text on a dark translucent bar at the bottom, away from the
top-right webcam corner. Needs ffmpeg with libx264 and the overlay filter (no drawtext needed).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_SIZE = 46
BAR_RGBA = (8, 18, 34, 218)
WRAP = 62


def caption_png(text: str, path: Path) -> None:
    font = ImageFont.truetype(FONT, FONT_SIZE)
    lines = textwrap.wrap(text, WRAP)
    line_h = int(FONT_SIZE * 1.28)
    bar_h = 36 + line_h * len(lines)
    img = Image.new("RGBA", (W, bar_h), BAR_RGBA)
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        tw = draw.textlength(line, font=font)
        draw.text(((W - tw) / 2, 18 + i * line_h), line, font=font, fill=(255, 255, 255, 255))
    img.save(path)


def label_png(text: str, path: Path) -> None:
    """Small persistent label for the top-left corner (the top-right is under the webcam)."""
    font = ImageFont.truetype(FONT, 30)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    tw = int(probe.textlength(text, font=font))
    img = Image.new("RGBA", (tw + 36, 54), (138, 75, 0, 225))
    ImageDraw.Draw(img).text((18, 9), text, font=font, fill=(255, 255, 255, 255))
    img.save(path)


def build(src: str, captions: list[dict], out: str, trim: float, crf: int, label: str = "") -> None:
    with tempfile.TemporaryDirectory() as tmp:
        inputs, chain, last = [], [], "[base]"
        for i, cap in enumerate(captions):
            png = Path(tmp) / f"cap{i}.png"
            caption_png(cap["text"], png)
            inputs += ["-i", str(png)]
            nxt = f"[v{i}]"
            chain.append(f"{last}[{i + 1}:v]overlay=x=0:y=H-h:enable='between(t,{cap['start']},{cap['end']})'{nxt}")
            last = nxt
        fit = (f"scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos,"
               f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x0D1117")
        graph = [f"[0:v]fps=30,{fit},setsar=1[pre]"]
        if label:
            lab = Path(tmp) / "label.png"
            label_png(label, lab)
            inputs = ["-i", str(lab)] + inputs
            graph.append("[pre][1:v]overlay=x=24:y=24[base]")
            offset = 2
        else:
            graph.append("[pre]null[base]")
            offset = 1
        chain = [c.replace(f"[{i + 1}:v]", f"[{i + offset}:v]") for i, c in enumerate(chain)]
        graph += chain
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", str(trim), "-i", src, *inputs,
               "-filter_complex", ";".join(graph), "-map", last, "-an",
               "-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-pix_fmt", "yuv420p",
               "-r", "30", "-movflags", "+faststart", out]
        subprocess.run(cmd, check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("captions"); ap.add_argument("out")
    ap.add_argument("--trim", type=float, default=0.0); ap.add_argument("--crf", type=int, default=23)
    ap.add_argument("--label", default="", help="persistent top-left label, e.g. the teaching disclaimer")
    a = ap.parse_args()
    build(a.src, json.loads(Path(a.captions).read_text()), a.out, a.trim, a.crf, a.label)


if __name__ == "__main__":
    main()
