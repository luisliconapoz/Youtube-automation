"""Montaje con ffmpeg (sin Node): cada imagen dura lo que su frase, con movimiento
suave (zoom/paneo), subtítulos quemados y audio mezclado. Corre igual en GitHub Actions."""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from .base import ProviderResult, Renderer

FPS = 30


def _motion(m: str, frames: int, w: int, h: int) -> str:
    step = 0.12 / max(frames, 1)
    z = {
        "slow_zoom_out": f"1.12-{step}*on",
        "static": "1.0",
    }.get(m, f"1+{step}*on")
    if m == "pan_left":
        return f"zoompan=z=1.1:x='(iw-iw/zoom)*(1-on/{frames})':y='(ih-ih/zoom)/2':d={frames}:s={w}x{h}:fps={FPS}"
    if m == "pan_right":
        return f"zoompan=z=1.1:x='(iw-iw/zoom)*on/{frames}':y='(ih-ih/zoom)/2':d={frames}:s={w}x{h}:fps={FPS}"
    return f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={FPS}"


class FFmpegRenderer(Renderer):
    name = "ffmpeg"

    def render(self, project_root: Path, timeline: dict, out_path: Path) -> ProviderResult:
        w, h = timeline["width"], timeline["height"]
        tmp = Path(tempfile.mkdtemp(prefix="pilo_render_"))
        parts = []
        for s in timeline["scenes"]:
            frames = max(int(round(s["duration"] * FPS)), 1)
            part = tmp / f"{s['number']:03d}.mp4"
            vf = f"scale={w * 2}:{h * 2},{_motion(s.get('motion', 'slow_zoom_in'), frames, w, h)},format=yuv420p"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(project_root / s["image"]),
                            "-vf", vf, "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast",
                            "-crf", "20", str(part)], check=True)
            parts.append(part)
        lst = tmp / "list.txt"
        lst.write_text("".join(f"file '{p}'\n" for p in parts))
        silent = tmp / "video.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-c", "copy", str(silent)], check=True)
        mix = project_root / "05_audio" / "mix.wav"
        subs = project_root / "06_subtitles" / "subs.srt"
        size = 9 if timeline["format"] == "LONG" else 12
        margin = 12 if timeline["format"] == "LONG" else 40  # escala libass: 288 de alto
        style = (f"FontName=DejaVu Sans,FontSize={size},Bold=1,PrimaryColour=&H00FFFFFF,"
                 f"OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV={margin}")
        vf = f"subtitles='{subs}':force_style='{style}'" if subs.exists() else "null"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(silent)]
        if mix.exists():
            cmd += ["-i", str(mix)]
        cmd += ["-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
        if mix.exists():
            cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
        cmd += [str(out_path)]
        subprocess.run(cmd, check=True)
        return ProviderResult(out_path, usd=0.0)
