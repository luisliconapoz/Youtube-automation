"""Mezcla: voz por escena en su tiempo + música sin copyright (con ducking) + SFX,
normalizado a -14 LUFS. Reglas en config/audio.json."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ..core.paths import ROOT

ASSETS = ROOT / "assets"


def pick_music(mood: str) -> Path | None:
    """Busca en assets/music/ un archivo cuyo nombre contenga alguna palabra del mood."""
    files = sorted(p for p in (ASSETS / "music").glob("*") if p.suffix.lower() in (".mp3", ".wav", ".m4a"))
    words = [w for w in mood.lower().split() if len(w) > 3]
    for f in files:
        if any(w in f.stem.lower() for w in words):
            return f
    return files[0] if files else None


def mix(project_root: Path, timeline: dict, out: Path) -> Path:
    cfg = json.loads((ROOT / "config" / "audio.json").read_text(encoding="utf-8"))
    fmt = timeline["format"]
    inputs, filters, labels = [], [], []
    for i, s in enumerate(timeline["scenes"]):
        v = project_root / s["voice"]
        if not v.exists():
            continue
        inputs += ["-i", str(v)]
        ms = int(s["start"] * 1000)
        filters.append(f"[{len(labels)}:a]aresample=48000,adelay={ms}|{ms}[v{i}]")
        labels.append(f"[v{i}]")
    n_voice = len(labels)
    total = timeline["total_seconds"]
    filters.append(f"{''.join(labels)}amix=inputs={n_voice}:normalize=0,apad,atrim=0:{total}[voice]")
    last = "[voice]"
    idx = n_voice
    # SFX
    sfx_db = cfg["sfx"]["level_db_below_voice"]
    sfx_labels = []
    for i, s in enumerate(timeline["scenes"]):
        name = s.get("sfx", "none")
        f = next(iter((ASSETS / "sfx").glob(f"{name}.*")), None) if name and name != "none" else None
        if f:
            inputs += ["-i", str(f)]
            ms = int(s["start"] * 1000)
            filters.append(f"[{idx}:a]aresample=48000,volume=-{sfx_db}dB,adelay={ms}|{ms}[s{i}]")
            sfx_labels.append(f"[s{i}]")
            idx += 1
    if sfx_labels:
        filters.append(f"{last}{''.join(sfx_labels)}amix=inputs={1 + len(sfx_labels)}:normalize=0:duration=first[vs]")
        last = "[vs]"
    music = pick_music(timeline.get("audio", {}).get("music_mood", ""))
    if music:
        m = cfg["music"]
        lvl = m["bed_level_db_below_voice"][fmt]
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        filters.append(f"[{idx}:a]aresample=48000,volume=-{lvl}dB,atrim=0:{total},"
                       f"afade=t=in:d={m['fade_in_s']},afade=t=out:st={max(total - m['fade_out_s'], 0)}:d={m['fade_out_s']}[mus]")
        filters.append(f"{last}asplit[vk][vm]")
        d = m["ducking"]
        filters.append(f"[mus][vk]sidechaincompress=threshold=0.03:ratio=8:attack={d['attack_ms']}:release={d['release_ms']}[duck]")
        filters.append(f"[vm][duck]amix=inputs=2:normalize=0:duration=first[pre]")
        last = "[pre]"
    lufs = cfg["master"]["integrated_lufs"]
    tp = cfg["master"]["true_peak_dbtp"]
    filters.append(f"{last}loudnorm=I={lufs}:TP={tp}:LRA=11[out]")
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(filters),
           "-map", "[out]", "-ar", "48000", "-ac", "2", str(out)]
    subprocess.run(cmd, check=True)
    return out
