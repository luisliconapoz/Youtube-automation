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
    b = BibliaEstilo(p, cargar_config(p.ruta))
    prompt = b.prompt_final(Escena(1, "Pilo despega", "robot takes off", personajes=["Pilo"], escenario="nave"))
    assert "orange robot" in prompt and "cockpit" in prompt and "amber" in prompt and "#" not in prompt


def test_prompt_neon_con_reparto_y_prohibiciones(proyecto):
    p = Proyecto.cargar(proyecto)
    b = BibliaEstilo(p, cargar_config(p.ruta))
    e = Escena(1, "Pilo duda", 'Pilo looks at a sign reading "SALE 50%" next to 3 coins', escenario="nave",
               reparto=[{"personaje": "Pilo", "expresion": "Thinking", "pose": "Thinking", "accion": "holding a coin"}])
    prompt = b.prompt_final(e, "16:9 widescreen")
    assert prompt.startswith("simple minimalist 2D neon vector illustration on a pure black background")
    assert "curious explorer robot" in prompt and "thinking expression" in prompt
    assert "pose: hand on chin, thinking" in prompt and "holding a coin" in prompt
    import re
    assert "SALE" not in prompt and "%" not in prompt and "#" not in prompt
    assert set(re.findall(r"\d+", prompt)) <= {"2", "16", "9", "3"}  # solo "2D", "16:9" y "no 3D render"
    assert "16:9" in prompt and "no 3D render" in prompt and "no text" in prompt


def test_limpiar_prompt():
    from pilo_studio.visuals.estilo import limpiar_prompt

    assert limpiar_prompt("a chart showing 50% growth and $1,000 bills") == "a chart showing growth and bills"
    assert limpiar_prompt('a sign reading "SALE" on a wall') == "a sign on a wall"
    assert limpiar_prompt("2D neon coin with 3 stacks") == "2D neon coin with stacks"


@pytest.mark.parametrize("canal,personajes,nicho", [
    ("fact-stick", {"Blue", "Green", "Pink", "Farmer", "Rich"}, "personal finance"),
    ("money-lab", {"Cyan", "Lime", "Brown", "Gray"}, "real estate"),
    ("wild-money", {"Orange", "Purple", "White", "Teal"}, "billionaires"),
])
def test_canales_oficiales(canal, personajes, nicho):
    from pilo_studio.config import RAIZ

    ruta = RAIZ / "proyectos" / canal
    meta = Proyecto.cargar_meta(ruta)
    assert set(meta["personajes"]) == personajes and nicho in meta["nicho"] and not meta["provisional"]
    assert (ruta / "guia" / "guia_oficial.jpg").exists()


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
    cfg["salida"]["nube"]["activada"] = False
    cfg["imagenes"]["proveedores"] = ["placeholder"]
    cfg["formatos"]["short"].update(ancho=270, alto=480, tam_fuente=30, margen_v=120)
    cfg["video"]["fps"] = 12
    final = pipeline.producir(proyecto, formato="short", cfg=cfg)
    assert final.exists() and final.stat().st_size > 1000
    assert final.parent.parent == tmp_path / "onedrive"
    imagenes = sorted((proyecto / "build" / "short" / "imagenes").glob("image_*.png"))
    assert [i.stem for i in imagenes][:2] == ["image_001", "image_002"]
    assert (final.parent / "publicacion.txt").exists()
    miniatura = final.with_name(final.stem + "_miniatura.jpg")
    assert miniatura.exists()
    from PIL import Image
    assert Image.open(miniatura).size == (1080, 1920)


def test_claude_sin_clave_devuelve_none(proyecto, monkeypatch):
    from pilo_studio.director.guionista import guion_claude

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    p = Proyecto.cargar(proyecto)
    assert guion_claude(p, "short", cargar_config(p.ruta), BibliaEstilo(p)) is None


def test_claude_convierte_salida_estructurada(proyecto, monkeypatch):
    from types import SimpleNamespace

    from pilo_studio.director import guionista

    capturado = {}

    class Stream:
        def __init__(self, **kw):
            capturado.update(kw)
            Modelo = kw["output_format"]
            self.salida = Modelo.model_validate({
                "titulo": "T", "descripcion": "D", "etiquetas": ["a"], "miniatura_texto": "WOW",
                "miniatura_prompt": "robot close-up",
                "escenas": [{"narracion": "Hola", "prompt_visual": "robot waves", "escenario": "nave",
                             "reparto": [{"personaje": "Pilo", "expresion": "Happy", "pose": "Thumbs up",
                                          "accion": "waving"}]}]})

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get_final_message(self):
            return SimpleNamespace(stop_reason="end_turn", parsed_output=self.salida,
                                   usage=SimpleNamespace(input_tokens=1, output_tokens=1))

    class Falso:
        def __init__(self):
            self.beta = SimpleNamespace(messages=SimpleNamespace(stream=Stream))

    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr(guionista.anthropic, "Anthropic", Falso)
    p = Proyecto.cargar(proyecto)
    cfg = cargar_config(p.ruta)
    g = guionista.guion_claude(p, "short", cfg, BibliaEstilo(p, cfg))
    e = g.escenas[0]
    assert g.titulo == "T" and e.id == 1 and e.personajes == ["Pilo"]
    assert e.reparto == [{"personaje": "Pilo", "expresion": "Happy", "pose": "Thumbs up", "accion": "waving"}]
    contenido = capturado["messages"][0]["content"][-1]["text"]
    assert "orange robot" in contenido and "Thinking" in contenido and "PROHIBIDO" in contenido
    assert "neón 2D" in capturado["system"]


def test_esquema_solo_admite_personajes_y_expresiones_oficiales(proyecto):
    import pydantic

    from pilo_studio.director.guionista import modelo_guion

    p = Proyecto.cargar(proyecto)
    Modelo = modelo_guion(BibliaEstilo(p, cargar_config(p.ruta)))
    base = {"titulo": "T", "descripcion": "", "etiquetas": [], "miniatura_texto": "", "miniatura_prompt": ""}
    escena = {"narracion": "x", "prompt_visual": "y", "escenario": None}
    Modelo.model_validate({**base, "escenas": [{**escena, "reparto": [
        {"personaje": "Pilo", "expresion": "Smug", "pose": "Arms crossed", "accion": ""}]}]})
    for malo in ({"personaje": "Batman", "expresion": "Happy", "pose": "Pointing", "accion": ""},
                 {"personaje": "Pilo", "expresion": "Furioso", "pose": "Pointing", "accion": ""},
                 {"personaje": "Pilo", "expresion": "Happy", "pose": "Bailando", "accion": ""}):
        with pytest.raises(pydantic.ValidationError):
            Modelo.model_validate({**base, "escenas": [{**escena, "reparto": [malo]}]})


def test_subida_nube_se_omite_sin_config(tmp_path, monkeypatch):
    from pilo_studio.storage import nube

    monkeypatch.delenv("RCLONE_CONF_B64", raising=False)
    monkeypatch.setattr(nube, "RCLONE_CONF", tmp_path / "no-existe.conf")
    assert nube.subir(tmp_path, "onedrive:PiloStudio") is False


def test_programa_maestro_crea_proyecto_con_universo(tmp_path, monkeypatch):
    import pilo

    monkeypatch.setattr(pilo, "RAIZ", tmp_path)
    (tmp_path / "proyectos").mkdir()
    destino = pilo.crear_proyecto("Los agujeros negros explicados", None, EJEMPLO)
    assert (destino / "idea.md").read_text(encoding="utf-8").startswith("# Los agujeros negros explicados")
    assert "Pilo" in Proyecto.cargar(destino).estilo.personajes


def test_miniatura_largo_1280x720(tmp_path):
    from PIL import Image

    from pilo_studio.visuals.miniatura import componer_miniatura

    Image.new("RGB", (500, 300), "blue").save(tmp_path / "f.png")
    out = componer_miniatura(tmp_path / "f.png", "El secreto del universo revelado hoy", "largo", tmp_path / "m.jpg")
    img = Image.open(out)
    assert img.size == (1280, 720) and out.stat().st_size < 2_000_000
    assert img.getpixel((640, 650)) != img.getpixel((640, 50))  # hay texto/degradado abajo


def test_prompt_largo_se_recorta_sin_perder_reglas(proyecto):
    p = Proyecto.cargar(proyecto)
    b = BibliaEstilo(p, cargar_config(p.ruta))
    e = Escena(1, "", "robot " * 600, reparto=[{"personaje": "Pilo", "expresion": "Happy", "pose": "Pointing"}])
    prompt = b.prompt_final(e)
    assert len(prompt) <= 1400 and prompt.endswith("no cluttered dashboards") and "orange robot" in prompt


def test_respaldo_reutiliza_imagen_vecina(proyecto, monkeypatch):
    from PIL import Image

    from pilo_studio.visuals import generador
    from pilo_studio.visuals.cola import Proveedor

    def solo_impares(t):
        if t.clave in ("image_001", "miniatura_fondo"):
            return Image.new("RGB", (t.ancho, t.alto), (0, 229, 255))
        raise RuntimeError("caído")

    monkeypatch.setattr(generador, "FABRICAS_RED", {"pollinations": lambda c, s: Proveedor(
        "pollinations", solo_impares, reintentos=1, max_fallos_seguidos=100)})
    p = Proyecto.cargar(proyecto)
    cfg = cargar_config(p.ruta)
    cfg["imagenes"]["pausa_ronda_extra"] = 0
    cfg["imagenes"]["proveedores"] = ["pollinations", "vecina", "placeholder"]
    cfg["formatos"]["short"].update(ancho=90, alto=160)
    g = Guion("t", "short", escenas=[Escena(1, "a", "x"), Escena(2, "b", "y")])
    generador.generar_imagenes(g, p.build("short"), cfg, BibliaEstilo(p, cfg))
    assert Image.open(g.escenas[1].imagen).getpixel((5, 5)) == (0, 229, 255)  # copia de image_001


def test_canal_envia_guia_oficial_a_claude(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from pilo_studio.config import RAIZ
    from pilo_studio.director import guionista

    destino = tmp_path / "canal"
    shutil.copytree(RAIZ / "proyectos" / "wild-money", destino)
    (destino / "idea.md").write_text("# Cómo gana dinero Netflix\n\nidea", encoding="utf-8")
    capturado = {}

    class Stream:
        def __init__(self, **kw):
            capturado.update(kw)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get_final_message(self):
            return SimpleNamespace(stop_reason="refusal", parsed_output=None, usage=None)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr(guionista.anthropic, "Anthropic",
                        lambda: SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=Stream))))
    p = Proyecto.cargar(destino)
    cfg = cargar_config(p.ruta)
    assert guionista.guion_claude(p, "short", cfg, BibliaEstilo(p, cfg)) is None  # refusal -> siguiente proveedor
    bloques = capturado["messages"][0]["content"]
    assert bloques[0]["type"] == "image" and bloques[0]["source"]["media_type"] == "image/jpeg"
    texto = bloques[-1]["text"]
    assert "billionaires" in texto and "Purple" in texto and "golden crown" in texto
    assert "40 a 58 segundos" in texto and "Entre 8 y 12 escenas" in texto
    assert "Arms crossed" in texto and "Smug" in texto


def test_short_demasiado_largo_se_acelera(proyecto, monkeypatch):
    from pilo_studio.audio import locutor

    llamadas = []

    def falso(guion, build, cfg):
        llamadas.append(cfg["audio"]["velocidad"])
        for e in guion.escenas:
            e.duracion = 7.0 if cfg["audio"]["velocidad"] == "+0%" else 5.5
        return guion

    monkeypatch.setattr(locutor, "generar_audio", falso)
    cfg = cargar_config(proyecto)
    g = Guion("t", "short", escenas=[Escena(i, "x", "y") for i in range(1, 11)])
    falso(g, None, cfg)                       # 10 escenas × 7 s = 70 s + pausas
    locutor.controlar_duracion(g, proyecto, cfg)
    assert llamadas[-1].startswith("+") and llamadas[-1] != "+0%"
    assert locutor.duracion_total(g, 0.15) <= 58
