"""Trazado de un personaje sobre la guía oficial → datos vectoriales (JSON).

    python -m pilo_studio.personajes.trazar blue

Herramienta de desarrollo (requiere opencv-python-headless). Analiza el recorte de la guía
ampliado ×4 y extrae, en coordenadas de la guía (px del recorte, con decimales):
  - trazo neón: contornos exactos del trazo cian, con sus variaciones de grosor
    (incluye el mechón, los nudillos del puño y las líneas de los dedos)
  - interior: la silueta negra del cuerpo (los huecos, como el del brazo en jarra, quedan fuera)
  - ojos: elipse ajustada al contorno exterior blanco (forma, tamaño, inclinación) y
    círculo de la pupila ajustado al borde interior del blanco
  - boca (banda blanca), lengua roja y cejas: polígonos trazados
  - halo: perfil de brillo medido alrededor del trazo
El render (fiel.py) solo usa estos datos y Pillow.
"""
from __future__ import annotations

import json
import sys

import cv2
import numpy as np
from PIL import Image

from pilo_studio.personajes import fiel

E = 4                      # ampliación de análisis
SUAVIZADO = 0.7            # sigma (px ×4): solo ruido JPEG; más alto recorta las puntas finas de dedos
SIMPLIFICACION = 0.35      # tolerancia (px ×4) de approxPolyDP


def _cargar(clave):
    archivo, caja = fiel.REFERENCIAS[clave]
    g = Image.open(fiel.RAIZ / archivo).convert("RGB").crop(caja)
    return np.array(g.resize((g.width * E, g.height * E), Image.LANCZOS)).astype(np.int32), g.size


def _suavizar(c: np.ndarray, cerrado=True) -> np.ndarray:
    c = c.reshape(-1, 2).astype(np.float64)
    if len(c) < 8:
        return c
    k = int(SUAVIZADO * 3) * 2 + 1
    w = np.exp(-0.5 * (np.arange(k) - k // 2) ** 2 / SUAVIZADO ** 2)
    w /= w.sum()
    pad = np.concatenate([c[-(k // 2):], c, c[:k // 2]]) if cerrado else np.pad(c, ((k // 2, k // 2), (0, 0)), "edge")
    return np.stack([np.convolve(pad[:, i], w, "valid") for i in (0, 1)], 1)


def _poligonos(mask: np.ndarray, area_min=6 * E * E):
    """Contornos con agujeros → [{'ext': [...], 'agujeros': [[...], ...]}] en px de guía."""
    cs, jer = cv2.findContours(mask.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    res = []
    if jer is None:
        return res
    jer = jer[0]
    for i, c in enumerate(cs):
        if jer[i][3] != -1 or cv2.contourArea(c) < area_min:
            continue
        def conv(cc):
            # el suavizado quita el ruido JPEG de los contornos largos; en trazos cortos
            # (segmentos de dedos, pliegues) los encogería, así que no se aplica
            s = _suavizar(cc) if cv2.contourArea(cc) > 30 * E * E else cc.reshape(-1, 2).astype(np.float64)
            s = cv2.approxPolyDP(s.astype(np.float32).reshape(-1, 1, 2), SIMPLIFICACION, True).reshape(-1, 2)
            return [[round(float(x) / E, 2), round(float(y) / E, 2)] for x, y in s]
        agujeros, j = [], jer[i][2]
        while j != -1:
            if cv2.contourArea(cs[j]) >= 2 * E * E:
                agujeros.append(conv(cs[j]))
            j = jer[j][0]
        res.append({"ext": conv(c), "agujeros": agujeros})
    return res


def _circulo(pts):
    """Ajuste algebraico de circunferencia (Kåsa)."""
    x, y = pts[:, 0], pts[:, 1]
    A = np.c_[2 * x, 2 * y, np.ones(len(x))]
    cx, cy, c = np.linalg.lstsq(A, x ** 2 + y ** 2, rcond=None)[0]
    return float(cx), float(cy), float(np.sqrt(c + cx ** 2 + cy ** 2))


def mascaras(g: np.ndarray) -> dict:
    """Extrae, de una imagen ×E (guía o reconstrucción), las máscaras de cada parte."""
    R, G, B = g[..., 0], g[..., 1], g[..., 2]
    zona = np.zeros(R.shape, bool)
    zona[6 * E: 214 * E, 20 * E: 205 * E] = True            # sin el marco de la tarjeta

    trazo = (G > 165) & (B > 205) & (R < 170) & zona
    n, lab, st, _ = cv2.connectedComponentsWithStats(trazo.astype(np.uint8), 8)
    trazo = np.isin(lab, [i for i in range(1, n) if st[i, 4] > 8 * E * E])   # conserva pliegues y nudillos cortos

    # interior: regiones encerradas por el trazo (el cuerpo se cierra en el borde inferior del recorte)
    cerrado = trazo.copy()
    cerrado_base = np.ones(R.shape, bool)
    CORTE = 210 * E                                         # la guía corta el retrato por aquí
    filas = np.where(trazo[CORTE])[0]
    if len(filas):
        cerrado[CORTE: CORTE + 3, filas.min(): filas.max() + 1] = True
        cerrado[CORTE + 3:, :] = False
        cerrado_base[CORTE + 3:, :] = False
    # en la guía, cabeza y hombros no llegan a tocarse en el cuello: se cierran esos huecos
    # solo para encontrar el interior (el trazo dibujado no cambia)
    nucleo = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5 * E + 1, 5 * E + 1))
    cerrado = cv2.dilate(cerrado.astype(np.uint8), nucleo) > 0
    n2, lab2, st2, _ = cv2.connectedComponentsWithStats((~cerrado).astype(np.uint8), 4)
    interior = np.zeros(R.shape, bool)
    for i in range(1, n2):
        x, y, ww, hh, area = st2[i]
        if x == 0 or y == 0 or x + ww >= R.shape[1] or y + hh > CORTE + 3 or area < 20 * E * E:
            continue
        m = lab2 == i
        oscuros = g[m][g[m].max(1) < 120]
        if len(oscuros) and (oscuros[:, 1] + oscuros[:, 2]).mean() < 40:   # negro del cuerpo, no fondo con halo
            interior |= m
    # devolver al interior lo que tapó el cierre (hasta tocar el trazo)
    interior = (cv2.dilate(interior.astype(np.uint8), nucleo) > 0) & ~trazo & cerrado_base

    # líneas interiores (separación de dedos, pliegue de la palma, nudillos): dentro del cuerpo
    # todo es negro salvo la cara, así que cualquier cian allí es una línea, aunque sea tenue
    cian = (G > 105) & (B > 145) & (R < 170) & (B > R + 60)
    # cresta: más brillante que los dos vecinos a 1,5 px en horizontal o en vertical
    # (el halo del borde solo crece hacia el trazo, así que no es cresta)
    d = int(1.5 * E)
    Gf = G.astype(np.float32)
    def vec(dx, dy):
        return np.roll(np.roll(Gf, dy, 0), dx, 1)
    cresta = ((Gf > np.maximum(vec(d, 0), vec(-d, 0)) + 25) | (Gf > np.maximum(vec(0, d), vec(0, -d)) + 25))
    lineas = interior & cian & cv2.dilate(cresta.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    trazo |= lineas
    interior &= ~trazo
    blanco = (g.min(2) > 128) & interior                     # punto medio blanco/negro (borde suavizado)
    rojo = (R > 115) & (G < 110) & (B < 130) & (R - G > 70) & interior
    nb, labb, stb, cen = cv2.connectedComponentsWithStats(blanco.astype(np.uint8), 8)
    blobs = sorted([i for i in range(1, nb) if stb[i, 4] > 15 * E * E], key=lambda i: cen[i][1])
    # los dos blobs más altos son los ojos (ordenados por x); el siguiente, la banda de la boca
    ojos_ids = sorted(blobs[:2], key=lambda i: cen[i][0])
    boca_ids = blobs[2:]
    cejas_m = (B > 60) & (G > 40) & (R < 60) & (B < 175) & (G < 150) & interior
    if ojos_ids:
        top = min(stb[i, 1] for i in ojos_ids)
        cejas_m[top - 2:, :] = False
        cejas_m[: top - 14 * E, :] = False
    return dict(g=g, zona=zona, trazo=trazo, interior=interior, blanco=blanco, rojo=rojo,
                labb=labb, ojos_ids=ojos_ids, boca_ids=boca_ids, cejas=cejas_m)


def trazar(clave: str) -> dict:
    g, (w, h) = _cargar(clave)
    M = mascaras(g)
    R = g[..., 0]
    zona, trazo, interior, blanco, rojo = M["zona"], M["trazo"], M["interior"], M["blanco"], M["rojo"]
    labb, ojos_ids, boca_ids, cejas_m = M["labb"], M["ojos_ids"], M["boca_ids"], M["cejas"]

    ojos = []
    for i in ojos_ids:
        m = (labb == i).astype(np.uint8)
        c = max(cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0], key=cv2.contourArea).reshape(-1, 2)
        hull = cv2.convexHull(c.astype(np.int32)).reshape(-1, 2)
        dist = np.array([abs(cv2.pointPolygonTest(hull.reshape(-1, 1, 2).astype(np.float32),
                                                  (float(x), float(y)), True)) for x, y in c])
        exterior, interior_b = c[dist < 1.0 * E], c[dist > 2.0 * E]
        (ex, ey), (a1, a2), ang = cv2.fitEllipse(exterior.astype(np.float32))
        px, py, pr = _circulo(interior_b.astype(np.float64))
        ojos.append({"elipse": [ex / E, ey / E, a1 / 2 / E, a2 / 2 / E, ang],
                     "pupila": [px / E, py / E, pr / E]})

    datos = {
        "clave": clave,
        "lienzo": [w, h],
        "trazo": _poligonos(trazo, area_min=0.5 * E * E),
        "interior": _poligonos(interior),
        "ojos": ojos,
        "ojos_blanco": _poligonos(np.isin(labb, ojos_ids), area_min=4 * E * E),   # forma exacta del blanco ("C")
        "boca": _poligonos(np.isin(labb, boca_ids)),
        "lengua": _poligonos(rojo, area_min=4 * E * E),
        "cejas": _poligonos(cejas_m, area_min=2 * E * E),
        "color": [int(v) for v in np.median(g[trazo], axis=0)],
        "color_lengua": [int(v) for v in np.median(g[rojo], axis=0)],
        "color_ceja": [int(v) for v in np.median(g[cejas_m], axis=0)] if cejas_m.any() else [0, 95, 120],
        "color_blanco": [int(v) for v in np.median(g[blanco], axis=0)],
        "fondo": [int(v) for v in np.median(g[~(trazo | interior) & zona & (g.max(2) < 40)], axis=0)],
    }
    datos["halo"] = medir_halo(g, trazo, interior)
    # color del resplandor (más azul que el trazo): proporción G/B y R/B medida a 2–6 px del trazo
    dist = cv2.distanceTransform((~trazo).astype(np.uint8), cv2.DIST_L2, 5) / E
    anillo = ~(trazo | interior) & (dist > 2) & (dist < 6) & zona
    fondo = np.array(datos["fondo"], np.float64)
    exceso = np.median(g[anillo] - fondo, axis=0).clip(1)
    datos["color_halo"] = [int(round(v)) for v in exceso / exceso[2] * datos["color"][2]]
    datos["halo_render"] = ajustar_halo(datos, g, trazo, interior)
    return datos


def ajustar_halo(datos, g, trazo, interior):
    """Halo = a1·desenfoque(s1) + a2·desenfoque(s2) del trazo. Para cada par de radios, las
    intensidades se resuelven por mínimos cuadrados no negativos contra el perfil de la guía."""
    from PIL import ImageFilter
    from scipy.optimize import nnls
    objetivo = np.array(datos["halo"]["perfil_azul"][:9])
    azul = datos.get("color_halo", datos["color"])[2]
    fuera = ~(trazo | interior)
    d = cv2.distanceTransform((~trazo).astype(np.uint8), cv2.DIST_L2, 5) / E
    bandas = [fuera & (d >= k - 0.5) & (d < k + 0.5) for k in range(1, 10)]
    m = Image.fromarray((trazo * 255).astype(np.uint8))
    cache = {}
    def base(sig):
        if sig not in cache:
            b = np.asarray(m.filter(ImageFilter.GaussianBlur(sig * E)), np.float32) / 255 * azul
            cache[sig] = np.array([b[sel].mean() for sel in bandas])
        return cache[sig]
    mejor = None
    for s1 in (0.6, 0.9, 1.2, 1.6, 2.0, 2.5):
        for s2 in (3.0, 4.0, 5.0, 6.5, 8.0, 10.0, 12.0):
            A = np.stack([base(s1), base(s2)], 1)
            (a1, a2), _ = nnls(A, objetivo)
            err = float(np.abs(A @ [a1, a2] - objetivo).mean())
            if mejor is None or err < mejor[0]:
                mejor = (err, dict(s1=s1, a1=round(float(a1), 3), s2=s2, a2=round(float(a2), 3)))
    return dict(mejor[1], error_medio=round(mejor[0], 1))


def medir_halo(g, trazo, interior, max_d=14):
    """Brillo medio (canal azul sobre el fondo) a d px de guía del trazo, por fuera del cuerpo."""
    fuera = ~(trazo | interior)
    d = cv2.distanceTransform((~trazo).astype(np.uint8), cv2.DIST_L2, 5) / E
    base = float(np.median(g[..., 2][fuera & (d > 20)])) if (fuera & (d > 20)).any() else 0.0
    perfil = []
    for k in range(1, max_d + 1):
        sel = fuera & (d >= k - 0.5) & (d < k + 0.5)
        perfil.append(round(float(g[..., 2][sel].mean()) - base, 1) if sel.any() else 0.0)
    return {"perfil_azul": perfil, "fondo": base}


if __name__ == "__main__":
    clave = sys.argv[1] if len(sys.argv) > 1 else "blue"
    datos = trazar(clave)
    ruta = fiel.RAIZ / "personajes" / "trazados" / f"{clave}.json"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    print(ruta, {k: len(v) for k, v in datos.items() if isinstance(v, list)})
