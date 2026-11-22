"""FASE 3 — Generación de imágenes con consistencia visual.

Cadena de respaldo configurable (todas gratuitas, todas en la nube):
  pollinations -> Pollinations.ai (Flux). Sin clave funciona con límite de velocidad;
                  con POLLINATIONS_API_KEY (registro gratuito) admite varias peticiones en paralelo.
  huggingface  -> Inference API gratuita de Hugging Face (FLUX.1-schnell), requiere HF_TOKEN
Respaldo local, solo si la nube falla incluso tras una ronda extra:
  vecina       -> reutiliza la imagen generada más cercana de la secuencia
  referencias  -> reutiliza las imágenes de referencia del usuario
  placeholder  -> último recurso: forma neón abstracta sobre negro (sin texto)

Todas las imágenes se piden EN LOTE a través de una cola compartida
(ver visuals/cola.py): los proveedores en la nube trabajan en paralelo, cada uno
a su ritmo máximo, y lo que falle se resuelve al final con el respaldo local.
"""

from __future__ import annotations

import io
import os
import time
import urllib.parse
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from pilo_studio.models import Escena, Guion
from pilo_studio.utils import log
from pilo_studio.visuals.cola import Cola, Limitador, Proveedor, Trabajo
from pilo_studio.visuals.estilo import BibliaEstilo


def _ajustar(img: Image.Image, ancho: int, alto: int) -> Image.Image:
    """Recorta/escala para cubrir exactamente el cuadro (sin bandas negras)."""
    return ImageOps.fit(img.convert("RGB"), (ancho, alto), Image.Resampling.LANCZOS)


# ------------------------------------------------------------ proveedores en la nube
class Reintentable(Exception):
    """Error transitorio (429/5xx/red): el trabajo vuelve a la cola."""


def _imagen_de(r: requests.Response, nombre: str, limitador: Limitador) -> Image.Image | None:
    if r.ok and r.headers.get("content-type", "").startswith("image"):
        return Image.open(io.BytesIO(r.content))
    if r.status_code == 429:
        espera = float(r.headers.get("retry-after", "20") or 20)
        limitador.penalizar(espera)
        raise Reintentable(f"{nombre}: límite de ritmo (429), pausa de {espera:.0f}s")
    raise Reintentable(f"{nombre}: HTTP {r.status_code} {r.text[:120]}")


def pollinations(cfg: dict, semilla: int) -> Proveedor:
    pc = cfg["imagenes"]["pollinations"]
    clave = os.environ.get("POLLINATIONS_API_KEY")
    cabeceras = {"Authorization": f"Bearer {clave}"} if clave else {}
    prov = Proveedor(
        "pollinations", generar=lambda t: None,
        # Sin clave: nivel anónimo ≈ 1 petición / 15 s → un solo hilo, bien espaciado.
        concurrencia=pc.get("concurrencia", 4) if clave else 1,
        intervalo=pc.get("intervalo_con_clave", 1.0) if clave else pc.get("espera_anonimo", 16),
        reintentos=pc.get("reintentos", 3),
    )

    def generar(t: Trabajo) -> Image.Image | None:
        url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(t.prompt)
        params = {"width": t.ancho, "height": t.alto, "seed": semilla, "model": pc.get("modelo", "flux"),
                  "nologo": "true", "enhance": "false", "negative": cfg["imagenes"].get("negativo", "")}
        try:
            r = requests.get(url, params=params, headers=cabeceras, timeout=pc.get("timeout", 120))
        except requests.RequestException as e:
            raise Reintentable(f"pollinations: {type(e).__name__}") from None
        return _imagen_de(r, "pollinations", prov.limitador)

    prov.generar = generar
    return prov


def huggingface(cfg: dict, semilla: int) -> Proveedor | None:
    token = os.environ.get("HF_TOKEN")
    if not token:
        return None
    hc = cfg["imagenes"]["huggingface"]
    url = f"https://router.huggingface.co/hf-inference/models/{hc.get('modelo', 'black-forest-labs/FLUX.1-schnell')}"
    prov = Proveedor("huggingface", generar=lambda t: None,
                     concurrencia=hc.get("concurrencia", 2), intervalo=hc.get("intervalo", 1.0),
                     reintentos=hc.get("reintentos", 2))

    def generar(t: Trabajo) -> Image.Image | None:
        # FLUX trabaja mejor en múltiplos de 64 y ~1 MP; luego se reescala al cuadro final
        w, h = (1024, 576) if t.ancho > t.alto else (576, 1024)
        try:
            r = requests.post(url, headers={"Authorization": f"Bearer {token}"}, timeout=hc.get("timeout", 120),
                              json={"inputs": t.prompt, "parameters": {
                                  "width": w, "height": h, "seed": semilla,
                                  "negative_prompt": cfg["imagenes"].get("negativo", "")}})
        except requests.RequestException as e:
            raise Reintentable(f"huggingface: {type(e).__name__}") from None
        return _imagen_de(r, "huggingface", prov.limitador)

    prov.generar = generar
    return prov


FABRICAS_RED = {"pollinations": pollinations, "huggingface": huggingface}


# ------------------------------------------------------------ referencias
def desde_referencias(biblia: BibliaEstilo, escena: Escena) -> Image.Image | None:
    refs = biblia.proyecto.referencias
    if not refs:
        return None
    # Preferir una referencia cuyo nombre de archivo coincida con un personaje/escenario
    claves = [c.lower() for c in escena.personajes + ([escena.escenario] if escena.escenario else [])]
    for r in refs:
        if any(c in r.stem.lower() for c in claves):
            return Image.open(r)
    return Image.open(refs[(escena.id - 1) % len(refs)])


# ------------------------------------------------------------ placeholder (último recurso)
def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return tuple(int(c[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def placeholder(biblia: BibliaEstilo, escena: Escena, ancho: int, alto: int) -> Image.Image:
    """Forma neón abstracta sobre negro, coherente con el estilo y sin texto."""
    paleta = [_hex(c) for c in (biblia.paleta or ["#00e5ff", "#39ff14", "#ff2bd6"])]
    color = paleta[escena.id % len(paleta)]
    capa = Image.new("RGB", (ancho, alto), "black")
    d = ImageDraw.Draw(capa)
    r = min(ancho, alto) // 4
    cx, cy = ancho // 2 + (escena.id % 3 - 1) * r, alto // 2
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=max(4, r // 20))
    d.line((cx - 2 * r, cy + r + r // 2, cx + 2 * r, cy + r + r // 2), fill=color, width=max(3, r // 30))
    brillo = capa.filter(ImageFilter.GaussianBlur(r // 6))
    return Image.blend(brillo, capa, 0.6).point(lambda v: min(255, int(v * 1.6)))


# ------------------------------------------------------------ orquestación
def nombre_imagen(n: int) -> str:
    """Nombres secuenciales: image_001, image_002…"""
    return f"image_{n:03d}"


def trabajos_del_guion(guion: Guion, destino: Path, ancho: int, alto: int, biblia: BibliaEstilo) -> dict[str, tuple]:
    """{clave: (Trabajo, escena|None)} para todo lo que aún no está en caché."""
    from pilo_studio.visuals.miniatura import prompt_miniatura, tam_miniatura

    encuadre = "vertical 9:16" if alto > ancho else "16:9 widescreen"
    trabajos: dict[str, tuple] = {}
    for e in guion.escenas:
        ruta = destino / f"{nombre_imagen(e.id)}.png"
        e.imagen = str(ruta)
        if not ruta.exists():
            trabajos[ruta.stem] = (Trabajo(ruta.stem, biblia.prompt_final(e, encuadre), ancho, alto, ruta), e)
    mw, mh = tam_miniatura(guion.formato)
    ruta = destino / "miniatura_fondo.png"
    if not ruta.exists():
        trabajos[ruta.stem] = (Trabajo(ruta.stem, prompt_miniatura(guion, biblia), mw, mh, ruta), None)
    return trabajos


def _vecina(guion: Guion, escena: Escena | None) -> Image.Image | None:
    """La imagen ya generada más cercana en la secuencia (prioriza la anterior)."""
    if escena is None:
        candidatas = guion.escenas
    else:
        i = guion.escenas.index(escena)
        orden = sorted(range(len(guion.escenas)), key=lambda j: (abs(j - i), j > i))
        candidatas = [guion.escenas[j] for j in orden if j != i]
    for e in candidatas:
        if e.imagen and Path(e.imagen).exists():
            return Image.open(e.imagen)
    return None


def generar_imagenes(guion: Guion, build: Path, cfg: dict, biblia: BibliaEstilo) -> Guion:
    """Genera TODAS las imágenes del video (secuencia + fondo de miniatura) en un solo lote."""
    fmt = cfg["formatos"][guion.formato]
    ancho, alto = fmt["ancho"], fmt["alto"]
    destino = build / "imagenes"
    destino.mkdir(parents=True, exist_ok=True)
    trabajos = trabajos_del_guion(guion, destino, ancho, alto, biblia)
    if not trabajos:
        log.info("  Todas las imágenes están en caché.")
        return guion

    cfg = {**cfg, "imagenes": {**cfg["imagenes"], "negativo": biblia.negativo()}}
    orden = cfg["imagenes"]["proveedores"]

    def proveedores_nube():
        nube = [p for n in orden if n in FABRICAS_RED and (p := FABRICAS_RED[n](cfg, biblia.semilla))]
        return nube if cfg["imagenes"].get("repartir_entre_proveedores", True) else nube[:1]

    def guardar(t: Trabajo, img: Image.Image) -> None:
        _ajustar(img, t.ancho, t.alto).save(t.ruta)
        t.ruta.with_suffix(".prompt.txt").write_text(t.prompt, encoding="utf-8")

    t0 = time.time()
    nube = proveedores_nube()
    log.info("  Lote de %d imágenes · proveedores: %s", len(trabajos),
             ", ".join(f"{p.nombre}×{p.concurrencia}" for p in nube) or "ninguno en la nube")
    sin_hacer = Cola([t for t, _ in trabajos.values()], nube, guardar).ejecutar()

    # Ronda extra: los fallos suelen ser saturación momentánea; se reintenta tras una pausa
    pausa = float(cfg["imagenes"].get("pausa_ronda_extra", 30))
    if sin_hacer and nube and pausa >= 0:
        log.info("  %d imágenes pendientes; ronda extra en %.0f s…", len(sin_hacer), pausa)
        time.sleep(pausa)
        for t in sin_hacer:
            t.intentados.clear()
            t.fallos.clear()
        sin_hacer = Cola(sin_hacer, proveedores_nube(), guardar).ejecutar()

    # Respaldo local para lo que la nube no pudo generar
    for t in sin_hacer:
        escena = trabajos[t.clave][1]
        img, origen = None, None
        for n in orden:
            if n == "vecina":
                img = _vecina(guion, escena)
            elif n == "referencias" and escena is not None:
                img = desde_referencias(biblia, escena)
            elif n == "placeholder":
                img = placeholder(biblia, escena or Escena(0, "", ""), t.ancho, t.alto)
            if img is not None:
                origen = n
                break
        if img is None:
            img, origen = placeholder(biblia, escena or Escena(0, "", ""), t.ancho, t.alto), "placeholder"
        guardar(t, img)
        log.warning("  ⚠️  %s vía respaldo '%s' (la nube no respondió)", t.clave, origen)
    log.info("  Lote completo en %.0f s (%d desde la nube, %d de respaldo)",
             time.time() - t0, len(trabajos) - len(sin_hacer), len(sin_hacer))
    return guion
