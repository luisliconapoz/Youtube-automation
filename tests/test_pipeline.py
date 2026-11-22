"""Pruebas offline: el TTS se simula con un tono generado por FFmpeg."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from pilo_studio import pipeline
from pilo_studio.assembly.subtitulos import construir_lineas
from pilo_studio.config import cargar_config
from pilo_studio.director.guionista import guion_plantilla
from pilo_studio.models import Escena, Guion, Palabra
from pilo_studio.proyecto import Proyecto
from pilo_studio.utils import ffmpeg_bin
from pilo_studio.visuals.estilo import BibliaEstilo, extraer_paleta

EJEMPLO = Path(__file__).resolve().parent.parent / "proyectos" / "ejemplo-pilo-espacio"


@pytest.fixture
def proyecto(tmp_path) -> Path:
    destino = tmp_path / "proy"
    shutil.copytree(EJEMPLO, destino)
    return destino


def test_plantilla_divide_en_escenas(proyecto):
    p = Proyecto.cargar(proyecto)
    cfg = cargar_config(p.ruta)
    g = guion_plantilla(p, "largo", cfg, BibliaEstilo(p))
    assert g.titulo == "Pilo y los secretos del espacio"
    assert len(g.escenas) >= 4
    assert any("Pilo" in e.personajes for e in g.escenas)


def test_prompt_inyecta_personaje_y_paleta(proyecto):
    p = Proyecto.cargar(proyecto)
    b = BibliaEstilo(p)
    prompt = b.prompt_final(Escena(1, "Pilo despega", "robot takes off", personajes=["Pilo"], escenario="nave"))
    assert "orange robot" in prompt and "cockpit" in prompt and "#ffb703" in prompt


def test_paleta_desde_referencias(tmp_path):
    from PIL import Image

    Image.new("RGB", (50, 50), (255, 0, 0)).save(tmp_path / "a.png")
    assert extraer_paleta([tmp_path / "a.png"], n=2)[0] == "#ff0000"


def test_subtitulos_tiempos_globales():
    g = Guion("t", "largo", escenas=[
        Escena(1, "a b", "", duracion=1.0, palabras=[Palabra("a", 0, .4), Palabra("b", .5, .9)]),
        Escena(2, "c", "", duracion=1.0, palabras=[Palabra("c", .1, .5)]),
    ])
    lineas = construir_lineas(g, palabras_por_linea=2, pausa=0.5)
    assert [l.texto for l in lineas] == ["a b", "c"]
    assert lineas[1].inicio == pytest.approx(1.6)


def _tts_falso(guion, build, cfg):
    d = build / "audio"
    d.mkdir(parents=True, exist_ok=True)
    for e in guion.escenas:
        mp3 = d / f"escena_{e.id:03d}.mp3"
        subprocess.run([ffmpeg_bin(), "-y", "-f", "lavfi", "-i", "sine=f=440:d=1", str(mp3)],
                       check=True, capture_output=True)
        e.audio, e.duracion = str(mp3), 1.0
        e.palabras = [Palabra(w, i * 0.15, (i + 1) * 0.15) for i, w in enumerate(e.narracion.split()[:6])]
    return guion


def test_pipeline_completo_offline(proyecto, tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "generar_audio", _tts_falso)
    monkeypatch.setenv("PILO_OUTPUT_DIR", str(tmp_path / "onedrive"))
    cfg = cargar_config(proyecto)
    cfg["guion"]["proveedores"] = ["plantilla"]
    cfg["imagenes"]["proveedores"] = ["placeholder"]
    cfg["formatos"]["short"].update(ancho=270, alto=480, tam_fuente=30, margen_v=120)
    cfg["video"]["fps"] = 12
    final = pipeline.producir(proyecto, formato="short", cfg=cfg)
    assert final.exists() and final.stat().st_size > 1000
    assert final.parent.parent == tmp_path / "onedrive"
    assert (final.parent / "publicacion.txt").exists()
