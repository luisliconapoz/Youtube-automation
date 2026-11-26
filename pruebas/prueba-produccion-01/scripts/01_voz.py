"""Paso 1 · Narración con TTS local (Kokoro v1.0, ONNX, Apache-2.0).

Sintetiza cada escena por separado con UNA sola voz (em_alex) y guarda:
  audio/escena_N.wav   – audio de cada escena
  audio/narracion.wav  – narración completa (escenas + pausas)
  audio/tiempos.json   – inicio/fin exactos de cada escena (para montaje y subtítulos)

Modelo: https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0
Uso: python 01_voz.py <carpeta_modelos>
"""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

BASE = Path(__file__).resolve().parent.parent
MODELOS = Path(sys.argv[1] if len(sys.argv) > 1 else BASE / "modelos")
VOZ, VELOCIDAD = "em_alex", 1.08
PAUSA_INICIO, PAUSA_ENTRE, PAUSA_FINAL = 0.25, 0.30, 0.9

guion = json.loads((BASE / "guion.json").read_text(encoding="utf-8"))
out = BASE / "audio"
out.mkdir(exist_ok=True)

k = Kokoro(str(MODELOS / "kokoro-v1.0.onnx"), str(MODELOS / "voices-v1.0.bin"))
sr = 24000
piezas, tiempos, t = [np.zeros(int(PAUSA_INICIO * sr), np.float32)], [], PAUSA_INICIO
for i, esc in enumerate(guion["escenas"]):
    audio, sr = k.create(esc["narracion"], voice=VOZ, speed=VELOCIDAD, lang="es")
    audio = audio.astype(np.float32)
    # recorta silencios de borde del modelo para que los tiempos sean precisos
    activo = np.where(np.abs(audio) > 0.01)[0]
    audio = audio[max(activo[0] - 240, 0): activo[-1] + 480]
    sf.write(out / f"escena_{esc['id']}.wav", audio, sr)
    dur = len(audio) / sr
    tiempos.append({"id": esc["id"], "voz_inicio": round(t, 3), "voz_fin": round(t + dur, 3)})
    pausa = PAUSA_FINAL if i == len(guion["escenas"]) - 1 else PAUSA_ENTRE
    piezas += [audio, np.zeros(int(pausa * sr), np.float32)]
    t += dur + pausa

total = np.concatenate(piezas)
total = total / max(np.abs(total).max(), 1e-6) * 0.89  # normaliza a ~-1 dBFS
sf.write(out / "narracion.wav", total, sr)
(out / "tiempos.json").write_text(json.dumps({"duracion": round(len(total) / sr, 3), "escenas": tiempos}, indent=2))
print(f"Narración: {len(total) / sr:.2f} s")
for x in tiempos:
    print(x)
