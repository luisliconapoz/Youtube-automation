"""Paso 3 · Verificación técnica del MP4 final.

1. ffprobe: códecs, resolución, fps, duración de vídeo y audio.
2. Decodificación completa (ffmpeg -f null): detecta fotogramas o paquetes corruptos.
3. Sincronía: detecta los silencios en el audio DEL MP4 y compara cada arranque de voz
   con el inicio previsto en audio/tiempos.json (el que usan escenas y subtítulos).
4. Extrae un fotograma por escena (con subtítulos) a salida/verificacion/ para revisión visual.
"""
import json
import re
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
mp4 = BASE / "salida" / "video_final.mp4"
tiempos = json.loads((BASE / "audio" / "tiempos.json").read_text())

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

info = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(mp4)]).stdout)
for s in info["streams"]:
    if s["codec_type"] == "video":
        print(f"VIDEO  {s['codec_name']} {s['width']}x{s['height']} {s['r_frame_rate']} fps  {s['pix_fmt']}  dur={s['duration']} s  frames={s['nb_frames']}")
        assert s["width"] * 16 == s["height"] * 9, "no es 9:16"
    else:
        print(f"AUDIO  {s['codec_name']} {s['sample_rate']} Hz {s['channels']} ch  dur={s['duration']} s")
dur = float(info["format"]["duration"])
print(f"FORMATO duración={dur:.2f} s  tamaño={int(info['format']['size']) / 1e6:.2f} MB")
assert 15 <= dur <= 20, "duración fuera de 15-20 s"

dec = run(["ffmpeg", "-v", "error", "-i", str(mp4), "-f", "null", "-"])
print("DECODIFICACIÓN COMPLETA:", "OK sin errores" if not dec.stderr.strip() else dec.stderr[:500])

sd = run(["ffmpeg", "-i", str(mp4), "-af", "silencedetect=noise=-35dB:d=0.2", "-vn", "-f", "null", "-"]).stderr
fines = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", sd)]
print("\nSINCRONÍA (arranque de voz previsto vs. detectado en el MP4):")
peor = 0.0
for e in tiempos["escenas"]:
    det = min(fines, key=lambda f: abs(f - e["voz_inicio"]))
    err = det - e["voz_inicio"]
    peor = max(peor, abs(err))
    print(f"  escena {e['id']}: previsto {e['voz_inicio']:6.3f} s  detectado {det:6.3f} s  desfase {err * 1000:+5.0f} ms")
print(f"  desfase máximo: {peor * 1000:.0f} ms ({'OK' if peor < 0.1 else 'REVISAR'}; un fotograma = 33 ms)")

out = BASE / "salida" / "verificacion"
out.mkdir(exist_ok=True)
for e in tiempos["escenas"]:
    t = (e["voz_inicio"] + e["voz_fin"]) / 2
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(mp4), "-frames:v", "1", "-vf", "scale=540:-1", str(out / f"fotograma_escena_{e['id']}.jpg")])
print(f"\nFotogramas de control en {out}")
