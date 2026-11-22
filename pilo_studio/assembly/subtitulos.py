"""Subtítulos automáticos a partir de las marcas de palabra de edge-tts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pilo_studio.models import Guion, Palabra


@dataclass
class Linea:
    inicio: float
    fin: float
    texto: str


def construir_lineas(guion: Guion, palabras_por_linea: int, pausa: float) -> list[Linea]:
    """Agrupa palabras en bloques cortos y los ubica en la línea de tiempo global."""
    lineas: list[Linea] = []
    t0 = 0.0
    for e in guion.escenas:
        ps = e.palabras
        if not ps and e.narracion:  # sin marcas: reparto uniforme
            tokens = e.narracion.split()
            paso = (e.duracion or 1.0) / max(len(tokens), 1)
            ps = [Palabra(w, i * paso, (i + 1) * paso) for i, w in enumerate(tokens)]
        for i in range(0, len(ps), palabras_por_linea):
            grupo = ps[i : i + palabras_por_linea]
            lineas.append(Linea(t0 + grupo[0].inicio, t0 + grupo[-1].fin, " ".join(p.texto for p in grupo)))
        t0 += (e.duracion or 0) + pausa
    # Evitar solapes y huecos parpadeantes: cada línea dura hasta que empieza la siguiente (máx 0.4 s extra)
    for a, b in zip(lineas, lineas[1:]):
        a.fin = min(max(a.fin, b.inicio - 0.4), b.inicio) if b.inicio > a.inicio else a.fin
    return lineas


def _ts_srt(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _ts_ass(t: float) -> str:
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360_000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def escribir_srt(lineas: list[Linea], ruta: Path) -> Path:
    bloques = [f"{i}\n{_ts_srt(l.inicio)} --> {_ts_srt(l.fin)}\n{l.texto}\n" for i, l in enumerate(lineas, 1)]
    ruta.write_text("\n".join(bloques), encoding="utf-8")
    return ruta


def escribir_ass(lineas: list[Linea], ruta: Path, ancho: int, alto: int, fmt: dict, scfg: dict) -> Path:
    es_vertical = alto > ancho
    cab = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {ancho}
PlayResY: {alto}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Pilo,{scfg.get('fuente', 'Arial')},{fmt['tam_fuente']},{scfg.get('color', '&H00FFFFFF')},&H000000FF,{scfg.get('color_borde', '&H00000000')},&H80000000,-1,0,0,0,100,100,0,0,1,{6 if es_vertical else 4},2,2,60,60,{fmt['margen_v']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    pop = r"{\fscx85\fscy85\t(0,90,\fscx100\fscy100)}" if es_vertical else ""  # efecto 'pop' en Shorts
    eventos = [
        f"Dialogue: 0,{_ts_ass(l.inicio)},{_ts_ass(l.fin)},Pilo,,0,0,0,,{pop}{l.texto.upper() if es_vertical else l.texto}"
        for l in lineas
    ]
    ruta.write_text(cab + "\n".join(eventos) + "\n", encoding="utf-8")
    return ruta
