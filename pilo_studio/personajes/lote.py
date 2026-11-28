"""Reconstrucción por lotes de los 13 personajes a partir de sus guías oficiales.

    python -m pilo_studio.personajes.lote            # traza los 12 restantes (Blue ya está aprobado)

Método (el de Blue, generalizado; herramienta de desarrollo, requiere opencv):
  1. Cada personaje se recorta de su guía (zona en coordenadas absolutas de la guía) y se
     analiza ampliado ×4. Se quitan los marcos de las tarjetas (componentes que tocan el borde).
  2. Capas de color: los píxeles iluminados se agrupan por color (k-means en Lab). Un grupo
     más tenue, del mismo tono y pegado a otro más brillante es HALO y se descarta (el halo se
     regenera); el resto son capas reales (neón principal, oro, gris del traje, blanco, rojo…).
  3. Interior negro del cuerpo: regiones encerradas por las capas (con cierre de huecos).
  4. Cara: se retiran los rasgos pintados en la guía (ojos, boca, lengua, cejas) y se coloca el
     ROSTRO MAESTRO (el de Blue) con una semejanza: mismo centro entre ojos que la guía y escala
     por distancia entre ojos. Cualquier píxel de accesorio que invada los rasgos se recorta.
  5. Halo: ajustado por mínimos cuadrados al perfil de brillo medido alrededor del trazo.
  6. Todo se guarda en personajes/trazados/<clave>.json y se dibuja con Pillow (fiel.render_capas).
"""
from __future__ import annotations

import json
import sys

import cv2
import numpy as np
from PIL import Image, ImageFilter

from pilo_studio.personajes import fiel, trazar

E = trazar.E

# zona de cada personaje en su guía (x0, y0, x1, y1, absolutas); y1 = donde la guía corta la figura
PERSONAJES = {
    "blue":   ("fact-stick", (35, 156, 220, 360)),
    "green":  ("fact-stick", (252, 158, 458, 360)),
    "pink":   ("fact-stick", (476, 158, 686, 360)),
    "farmer": ("fact-stick", (706, 156, 918, 360)),
    "rich":   ("fact-stick", (938, 159, 1152, 360)),
    "cyan":   ("money-lab", (30, 208, 203, 357)),
    "lime":   ("money-lab", (214, 208, 381, 357)),
    "brown":  ("money-lab", (389, 204, 572, 357)),
    "gray":   ("money-lab", (597, 204, 763, 357)),
    "orange": ("wild-money", (22, 170, 206, 334)),
    "purple": ("wild-money", (216, 166, 402, 334)),
    "white":  ("wild-money", (411, 170, 591, 334)),
    "teal":   ("wild-money", (599, 170, 767, 334)),
}
# opciones por personaje (datos, no diseño): rasgos de la guía que NO son cara y deben conservarse
OPCIONES = {
    "farmer": {"conservar_bigote": True},
    "rich": {"segundo_ojo": "anillo_dorado"},     # el ojo derecho queda dentro del monóculo
}


def cargar(clave):
    marca, (x0, y0, x1, y1) = PERSONAJES[clave]
    g = Image.open(fiel.RAIZ / "proyectos" / marca / "guia" / "guia_oficial.jpg").convert("RGB")
    c = g.crop((x0, y0, x1, y1))
    return np.array(c.resize((c.width * E, c.height * E), Image.LANCZOS)).astype(np.int32)


def es_blanco(color) -> bool:
    """Blanco o blanco teñido por el halo (claro y poco saturado)."""
    return min(color) > 150 and max(color) - min(color) < 60


def _cerca(m, px):
    k = int(px * E) * 2 + 1
    return cv2.dilate(m.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))) > 0


def capas_de_color(g: np.ndarray, k: int = 9):
    """Devuelve (lista de capas {color, mascara}, mascara de iluminado, fondo)."""
    V = g.max(2)
    H, W = V.shape
    fondo = np.median(g[V < 40], axis=0)
    lit = V > 70
    lit[: 2 * E] = False          # el borde de la tarjeta queda así separado y tocando el borde superior
    # fuera los marcos de tarjeta: componentes iluminados que tocan izquierda, derecha o arriba
    n, lab, st, _ = cv2.connectedComponentsWithStats(lit.astype(np.uint8), 8)
    for i in range(1, n):
        x, y, w, h, a = st[i]
        toca = x <= 1 or y <= 3 * E or x + w >= W - 1
        fino = min(w, h) < 9 * E or a < 0.12 * w * h          # líneas de marco, esquinas de tarjeta
        filas = np.where((lab[: 14 * E] == i).any(1))[0]
        borde_sup = y < 3 * E and w > 25 * E and (lab[: 10 * E] == i).sum() > 0.7 * a   # borde superior de tarjeta
        if (toca and fino) or borde_sup:
            lit[lab == i] = False
    Lab = cv2.cvtColor(np.clip(g, 0, 255).astype(np.uint8), cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)
    idx = np.flatnonzero(lit.ravel())
    muestra = idx[:: max(1, len(idx) // 60000)]
    cv2.setRNGSeed(0)                      # resultado reproducible
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 60, 0.5)
    _, _, centros = cv2.kmeans(Lab[muestra], k, None, crit, 4, cv2.KMEANS_PP_CENTERS)
    d = ((Lab[idx][:, None, :] - centros[None]) ** 2).sum(2)
    asig = np.full(H * W, -1)
    asig[idx] = d.argmin(1)
    asig = asig.reshape(H, W)
    grupos = []
    for i, c in enumerate(centros):
        m = asig == i
        if m.sum() < 3 * E * E:
            continue
        grupos.append(dict(lab=c, mascara=m, L=float(c[0]),
                           croma=float(np.hypot(c[1] - 128, c[2] - 128))))
    # halo: grupo más oscuro, mismo tono (o ambos neutros), casi todo pegado a uno más brillante
    def mismo_tono(a, b):
        if a["croma"] < 18 and b["croma"] < 18:
            return True
        da = np.degrees(np.arctan2(a["lab"][2] - 128, a["lab"][1] - 128))
        db = np.degrees(np.arctan2(b["lab"][2] - 128, b["lab"][1] - 128))
        return abs((da - db + 180) % 360 - 180) < 28 and min(a["croma"], b["croma"]) > 10
    for a in grupos:
        a["halo"] = False
        for b in grupos:
            if b is a or b["L"] < a["L"] * 1.25 + 8 or not mismo_tono(a, b):
                continue
            if (a["mascara"] & _cerca(b["mascara"], 4.5)).sum() > 0.8 * a["mascara"].sum():
                a["halo"], a["halo_de"] = True, b
                break
    # líneas finas (cuadrícula de la calculadora, gráfico de la tableta, pliegues): son más
    # tenues que el trazo pero forman crestas; el halo no (solo crece hacia el trazo)
    Vf = V.astype(np.float32)
    dd = int(1.2 * E)
    vec = lambda dx, dy: np.roll(np.roll(Vf, dy, 0), dx, 1)
    cresta = (Vf > np.maximum(vec(dd, 0), vec(-dd, 0)) + 20) | (Vf > np.maximum(vec(0, dd), vec(0, -dd)) + 20)
    cresta = cv2.dilate(cresta.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    for a in grupos:
        a["extra"] = np.zeros(V.shape, bool)
    for a in grupos:
        if a["halo"]:
            b = a["halo_de"]
            b["extra"] |= a["mascara"] & cresta & (V > 0.45 * np.percentile(V[b["mascara"]], 90))
    reales = [gr for gr in grupos if not gr["halo"]]
    # fusionar grupos casi iguales (núcleo y borde del mismo neón)
    fusion = []
    for gr in sorted(reales, key=lambda x: -x["mascara"].sum()):
        for f in fusion:
            if np.linalg.norm(f["lab"] - gr["lab"]) < 22 and mismo_tono(f, gr):
                f["mascara"] |= gr["mascara"]
                f["extra"] |= gr["extra"]
                break
        else:
            fusion.append(dict(gr))
    capas = []
    for f in fusion:
        px = g[f["mascara"]]
        brillo = px.max(1)
        nucleo = px[brillo >= np.percentile(brillo, 50)]
        capas.append(dict(color=[int(v) for v in np.median(nucleo, 0)], mascara=f["mascara"] | f["extra"],
                          base=f["mascara"]))
    return capas, lit, fondo


def interior_negro(paredes: np.ndarray, g: np.ndarray, corte: int):
    """Regiones negras encerradas por las capas (cuerpo); los huecos con halo no cuentan.
    Las guías dejan aberturas en el contorno (cuello, coronilla): se cierran con el menor
    radio que encierra el cuerpo, solo para encontrarlo (el trazo no cambia)."""
    H, W = paredes.shape
    base_cerr = paredes.copy()
    filas = np.where(paredes[corte - 2])[0]
    if len(filas):
        base_cerr[corte - 2: corte + 1, filas.min(): filas.max() + 1] = True
    base_cerr[corte + 1:, :] = False
    bbox = np.argwhere(paredes)
    area_fig = (np.ptp(bbox[:, 0]) + 1) * (np.ptp(bbox[:, 1]) + 1)
    # unión de lo que encierran varios radios de cierre (cada región validada por su tinte):
    # no depende de en qué radio aparece primero el cuerpo
    interior = np.zeros((H, W), bool)
    cerrado_total = np.zeros((H, W), bool)
    for diam in (5, 8, 11, 15):
        nucleo = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (diam * E + 1, diam * E + 1))
        cerrado = cv2.dilate(base_cerr.astype(np.uint8), nucleo) > 0
        cerrado_total |= cerrado
        n, lab, st, _ = cv2.connectedComponentsWithStats((~cerrado).astype(np.uint8), 4)
        for i in range(1, n):
            x, y, w, h, a = st[i]
            if x == 0 or y == 0 or x + w >= W or a < 20 * E * E:
                continue
            m = lab == i
            oscuros = g[m][g[m].max(1) < 90]
            if len(oscuros) and np.median(oscuros.max(1)) < 34:   # negro del cuerpo (aunque lo tiña el resplandor)
                # huecos pequeños con halo dentro (entre brazo, cabeza y objeto) son fondo, no cuerpo
                if a < 700 * E * E and np.percentile(oscuros.max(1), 90) > 20:
                    continue
                interior |= m
    cerrado = cerrado_total
    base = np.zeros((H, W), bool)
    base[:corte + 1] = True
    # devolver al interior la franja que tapó el cierre, creciendo paso a paso sin cruzar
    # ningún trazo (reconstrucción geodésica): así no se sale por los brazos finos
    # solo hacia píxeles negros en la guía: por una rendija del contorno no se cuela al fondo con halo
    junto_trazo = cv2.distanceTransform((~paredes).astype(np.uint8), cv2.DIST_L2, 5) < 1.5 * E
    permitido = ((cerrado & ~paredes & ((g.max(2) < 26) | junto_trazo)) | interior) & base
    k3 = np.ones((3, 3), np.uint8)
    for _ in range(diam * E // 2 + 2):
        nuevo = (cv2.dilate(interior.astype(np.uint8), k3) > 0) & permitido
        if (nuevo == interior).all():
            break
        interior = nuevo
    return interior & ~paredes


def rasgos_de_la_guia(capas, interior, g, opciones):
    """Localiza los ojos de la guía y la máscara de rasgos faciales pintados (a retirar)."""
    blanco = np.zeros(interior.shape, bool)
    for c in capas:
        r, gg, b = c["color"]
        if es_blanco(c["color"]):
            blanco |= c["base"]
    # componentes blancos rodeados casi por completo de interior negro (rasgos y accesorios
    # dentro de la cabeza); el contorno de un personaje blanco toca el fondo y queda fuera
    n0, lab0, st0, _ = cv2.connectedComponentsWithStats(blanco.astype(np.uint8), 8)
    blanco_libre = np.zeros(blanco.shape, bool)
    for i in range(1, n0):
        x, y, w, h, a = st0[i]
        if a < 4 * E * E:
            continue
        sl = (slice(max(0, y - 3 * E), y + h + 3 * E), slice(max(0, x - 3 * E), x + w + 3 * E))
        m = lab0[sl] == i
        anillo = _cerca(m, 1.5) & ~m
        oscuro = (g[sl].max(2) < 60) | interior[sl]
        if oscuro[anillo].mean() > 0.5 and interior[sl][_cerca(m, 8)].any():
            blanco_libre[sl] |= m
    abierto = cv2.morphologyEx(blanco_libre.astype(np.uint8), cv2.MORPH_OPEN,
                               cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * E + 1, 2 * E + 1)))
    n, lab, st, cen = cv2.connectedComponentsWithStats(abierto, 8)
    H = interior.shape[0]
    cand = [i for i in range(1, n) if st[i, 4] > 12 * E * E and cen[i][1] < 0.6 * H
            and st[i, 4] / (st[i, 2] * st[i, 3]) > 0.35]
    # ojos = la pareja de blancos de tamaño parecido y a la misma altura con más área
    pares = [(a, b) for a in cand for b in cand if a < b
             and abs(cen[a][1] - cen[b][1]) < 0.5 * max(st[a, 3], st[b, 3])
             and min(st[a, 4], st[b, 4]) > 0.4 * max(st[a, 4], st[b, 4])]
    if pares:
        ojos = sorted(max(pares, key=lambda p: st[p[0], 4] + st[p[1], 4]), key=lambda i: cen[i][0])
    else:
        ojos = sorted(cand, key=lambda i: -st[i, 4])[:1]
    if len(ojos) == 1 and opciones.get("segundo_ojo") == "anillo_dorado":
        oro = np.zeros(interior.shape, bool)
        for c in capas:
            r, gg, b = c["color"]
            if r > 200 and gg > 170 and b < 120:
                oro |= c["mascara"]
        na, laba, sta, cena = cv2.connectedComponentsWithStats(oro.astype(np.uint8), 8)
        j = max(range(1, na), key=lambda i: sta[i, 4] if cena[i][1] < 0.6 * H else 0)
        anillo = (laba == j).astype(np.uint8)
        lleno = anillo.copy()
        cs, _ = cv2.findContours(anillo, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        cv2.drawContours(lleno, cs, -1, 1, -1)
        nh, labh, sth, cenh = cv2.connectedComponentsWithStats(((lleno > 0) & (anillo == 0)).astype(np.uint8), 8)
        centro = cenh[max(range(1, nh), key=lambda i: sth[i, 4])] if nh > 1 else cena[j]
        c1, c2 = sorted([np.array(cen[ojos[0]]), np.array(centro)], key=lambda c: c[0])
    elif len(ojos) < 2:
        raise RuntimeError("no se encontraron los dos ojos en la guía")
    else:
        c1, c2 = np.array(cen[ojos[0]]), np.array(cen[ojos[1]])
    dist = float(np.linalg.norm(c2 - c1))
    alto_ojo = max(st[o, 3] for o in ojos)
    ancho_ojo = max(st[o, 2] for o in ojos)
    x0 = min(c1[0], c2[0]) - ancho_ojo / 2 - 0.45 * dist
    x1 = max(c1[0], c2[0]) + ancho_ojo / 2 + 0.45 * dist
    y0 = min(c1[1], c2[1]) - alto_ojo / 2 - 0.8 * alto_ojo
    y1 = max(c1[1], c2[1]) + alto_ojo / 2 + 2.4 * alto_ojo
    fondo_ojos = max(c1[1], c2[1]) + alto_ojo / 2
    caja = np.zeros(interior.shape, bool)
    caja[int(max(0, y0)): int(y1), int(max(0, x0)): int(x1)] = True
    cara = np.zeros(interior.shape, bool)
    for i in range(1, n):
        m = lab == i
        if not (m & caja).any():
            continue
        relleno = st[i, 4] / (st[i, 2] * st[i, 3])
        if relleno < 0.3:          # anillos (gafas, monóculo): accesorio, se conserva
            continue
        bajo_ojos = cen[i][1] > fondo_ojos
        if opciones.get("conservar_bigote") and bajo_ojos and st[i, 4] > 0.6 * min(st[o, 4] for o in ojos):
            continue
        cara |= m
    # rasgos de color pintados en la guía (lengua, labios, bocas): formas de capas secundarias
    # dentro de la cara, rodeadas de interior negro y que no son aros
    principal = max(capas, key=lambda c: c["base"].sum())
    for c in capas:
        if c is principal or es_blanco(c["color"]):
            continue
        nn, ll, ss, _ = cv2.connectedComponentsWithStats((c["base"] & caja).astype(np.uint8), 8)
        for i in range(1, nn):
            x, y, w, h, a = ss[i]
            sl = (slice(max(0, y - 3 * E), y + h + 3 * E), slice(max(0, x - 3 * E), x + w + 3 * E))
            m = ll[sl] == i
            anillo = _cerca(m, 1.5) & ~m
            if interior[sl][anillo].mean() > 0.5 and a / (w * h) >= 0.3:
                cara[sl] |= m
    cara |= caja & interior & (g.max(2) > 45) & (g.max(2) < 170)
    return dict(ojo_izq=c1 / E, ojo_der=c2 / E, distancia=dist / E, cara=_cerca(cara, 0.8) & caja)


def ajustar_halo(g, paredes, interior, capas):
    """Halo = Σ capas · (a1·desenfoque(s1) + a2·desenfoque(s2)), ajustado al brillo máximo (V)."""
    from scipy.optimize import nnls
    V = g.max(2).astype(np.float64)
    fuera = ~(paredes | interior)
    d = cv2.distanceTransform((~paredes).astype(np.uint8), cv2.DIST_L2, 5) / E
    base = float(np.median(V[fuera & (d > 18)])) if (fuera & (d > 18)).any() else 0.0
    bandas = [fuera & (d >= k - 0.5) & (d < k + 0.5) for k in range(1, 10)]
    objetivo = np.array([V[b].mean() - base if b.any() else 0 for b in bandas])
    cache = {}
    def base_s(s):
        if s not in cache:
            luz = np.zeros(V.shape)
            for c in capas:
                m = Image.fromarray((c["mascara"] * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(s * E))
                luz += np.asarray(m, np.float64) / 255 * max(c["color"])
            cache[s] = np.array([luz[b].mean() if b.any() else 0 for b in bandas])
        return cache[s]
    mejor = None
    for s1 in (0.6, 0.9, 1.2, 1.6, 2.0):
        for s2 in (3.0, 4.0, 5.0, 6.5, 8.0, 10.0):
            A = np.stack([base_s(s1), base_s(s2)], 1)
            (a1, a2), _ = nnls(A, objetivo)
            err = float(np.abs(A @ [a1, a2] - objetivo).mean())
            if mejor is None or err < mejor[0]:
                mejor = (err, dict(s1=s1, a1=round(float(a1), 3), s2=s2, a2=round(float(a2), 3)))
    return dict(mejor[1], error_medio=round(mejor[0], 1), perfil_V=[round(float(v), 1) for v in objetivo])


def trazar_personaje(clave: str) -> dict:
    g = cargar(clave)
    H, W = g.shape[:2]
    capas, lit, fondo = capas_de_color(g)
    paredes = np.zeros((H, W), bool)
    for c in capas:
        paredes |= c["mascara"]
    corte = H - 1
    interior = interior_negro(paredes, g, corte)
    # líneas interiores tenues (dedos, pliegues): crestas de color dentro del cuerpo
    cara = rasgos_de_la_guia(capas, interior, g, OPCIONES.get(clave, {}))
    maestro = fiel._maestro_de_blue(fiel.cargar_trazado("blue"))[0]
    # cejas del maestro: solo los trazos junto a los ojos (Blue guarda además un resto en el contorno)
    maestro["cejas"] = [p for p in maestro["cejas"]
                        if any(abs(np.mean([q[0] for q in p["ext"]]) - o["elipse"][0]) < 0.6 for o in maestro["ojos"])]
    neones = [c for c in capas if max(c["color"]) > 200 and not es_blanco(c["color"])] or capas
    principal = max(neones, key=lambda c: c["mascara"].sum())
    maestro["color_ceja"] = [int(v * 0.42) for v in principal["color"]]   # tono oscuro del neón, como en Blue
    medio = (cara["ojo_izq"] + cara["ojo_der"]) / 2
    escala = cara["distancia"]
    # máscara del rostro maestro colocado (para recortar accesorios que lo invadan)
    tmp = {"lienzo": [W / E, H / E], "rostro": {"medio": medio.tolist(), "escala": escala}, "maestro": maestro}
    rasgos = fiel.mascara_rostro(tmp, k=E, margen=fiel.MARGEN_CARA)
    bigote_info = None
    if OPCIONES.get(clave, {}).get("conservar_bigote"):
        bigote_info = _encajar_bigote(capas, cara, interior, maestro, medio, escala, rasgos)
    recortado = 0
    for c in capas:
        quitar = (cara["cara"] | rasgos) & c["mascara"]
        es_cara = cara["cara"] & c["mascara"]
        recortado += int((quitar & ~es_cara).sum())
        c["mascara"] = c["mascara"] & ~quitar
    if bigote_info:
        capa, m = bigote_info
        capa["mascara"] = capa["mascara"] | m
    interior |= cara["cara"] & ~paredes
    capas = [c for c in capas if c["mascara"].sum() > 2 * E * E]
    datos = {
        "clave": clave, "formato": "capas", "lienzo": [W / E, H / E],
        "origen": {"guia": PERSONAJES[clave][0], "zona": PERSONAJES[clave][1]},
        "fondo": [int(v) for v in fondo],
        "capas": [{"color": c["color"], "polis": trazar._poligonos(c["mascara"], area_min=0.5 * E * E,
                                                                     perimetro_min=6 * E)} for c in capas],
        "interior": trazar._poligonos(interior),
        "rostro": {"medio": [round(float(v), 2) for v in medio], "escala": round(escala, 3),
                   "ojos_guia": [cara["ojo_izq"].round(2).tolist(), cara["ojo_der"].round(2).tolist()]},
        "maestro": maestro,
        "accesorio_recortado_px": round(recortado / E / E, 1),
    }
    datos["halo_render"] = ajustar_halo(g, paredes & ~cara["cara"], interior, capas)
    # color del resplandor de cada capa, medido en un anillo de 2–6 px a su alrededor
    todas = np.zeros((H, W), bool)
    for c in capas:
        todas |= c["mascara"]
    for c, dc in zip(capas, datos["capas"]):
        dist = cv2.distanceTransform((~c["mascara"]).astype(np.uint8), cv2.DIST_L2, 5) / E
        otras = _cerca(todas & ~c["mascara"], 6)
        anillo = ~(todas | interior) & (dist > 2) & (dist < 6) & ~otras
        if anillo.sum() > 50:
            exceso = np.clip(np.median(g[anillo] - fondo, axis=0), 1, None)
            if exceso.max() >= 15:          # con un anillo casi negro el tono medido es ruido
                dc["color_halo"] = [int(round(v)) for v in exceso / exceso.max() * max(dc["color"])]
    return datos


def _encajar_bigote(capas, cara, interior, maestro, medio, escala, rasgos):
    """Bigote de la guía (forma trazada) escalado de modo uniforme para caber entre los ojos y la
    boca del rostro maestro sin tocarlos. Devuelve (capa blanca, nueva máscara) y lo retira de la capa."""
    blanca = next((c for c in capas if es_blanco(c["color"])), None)
    if blanca is None:
        return None
    zona = blanca["mascara"] & _cerca(interior, 1.0) & ~cara["cara"]
    zona[: int((medio[1] + 0.25 * escala) * E)] = False          # por debajo de los ojos
    n, lab, st, _ = cv2.connectedComponentsWithStats(zona.astype(np.uint8), 8)
    if n < 2:
        return None
    i = max(range(1, n), key=lambda j: st[j, 4])
    x, y, w, h, _ = st[i]
    forma = (lab[y:y + h, x:x + w] == i).astype(np.uint8)
    blanca["mascara"] = blanca["mascara"] & ~(lab == i)
    # hueco libre: bajo los ojos del maestro y sobre su boca (en la columna del bigote)
    cols = rasgos[:, x:x + w].any(1)
    filas = np.where(cols)[0]
    ojos_fondo = max(o["elipse"][1] + o["elipse"][3] for o in maestro["ojos"])
    y_ojos = int((medio[1] + ojos_fondo * escala) * E)
    libres = [r for r in range(y_ojos, rasgos.shape[0]) if not cols[r]]
    if not libres:
        return None
    y_a = libres[0]
    y_b = next((r for r in range(y_a, rasgos.shape[0]) if cols[r]), y_a)
    alto = y_b - y_a - 2
    if alto < 3 * E:
        return None
    f = min(1.0, alto / h)
    nw, nh = max(1, int(w * f)), max(1, int(h * f))
    peq = cv2.resize(forma, (nw, nh), interpolation=cv2.INTER_AREA) > 0
    nueva = np.zeros(rasgos.shape, bool)
    cx = x + w // 2
    x0, y0 = cx - nw // 2, y_a + (alto - nh) // 2 + 1
    nueva[y0:y0 + nh, x0:x0 + nw] = peq
    return blanca, nueva & ~rasgos


def guardar(datos):
    ruta = fiel.RAIZ / "personajes" / "trazados" / f"{datos['clave']}.json"
    ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    return ruta


if __name__ == "__main__":
    claves = sys.argv[1:] or [k for k in PERSONAJES if k != "blue"]
    errores = {}
    for k in claves:
        try:
            d = trazar_personaje(k)
        except Exception as e:      # se registra y el lote sigue
            errores[k] = repr(e)
            print(k, "ERROR", e)
            continue
        print(guardar(d).name, "capas", [c["color"] for c in d["capas"]], "halo", d["halo_render"]["error_medio"],
              "recortado", d["accesorio_recortado_px"])
    if errores:
        sys.exit(f"errores: {errores}")
