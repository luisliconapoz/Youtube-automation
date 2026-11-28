"""Piezas articulables y poses de los 13 personajes, a partir de sus trazados fieles.

Piezas (por personaje, en coordenadas de su guía):
  - cuerpo: cabeza + accesorios de cabeza + torso + prendas + piernas (trazado de la guía) con
    los brazos de la guía retirados (apertura morfológica: los brazos son más finos que el torso)
  - brazos de la guía (con mano y objeto sostenido): pieza aparte, usada en la pose de la guía
  - pivotes: cuello y hombros
En las poses, los brazos se redibujan como tubos de neón con el ancho de brazo, el grosor de
trazo, el color y el halo MEDIDOS en ese personaje, y las manos salen de una biblioteca trazada
de las guías (mano abierta y puño de Blue, índice levantado de Green), recoloreada y escalada.
El rostro maestro se aplica con cualquier expresión.
"""
from __future__ import annotations

import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from pilo_studio.personajes import fiel

POSES = ["explicando", "senalando", "pensando", "presentando",
         "preguntando", "brazos_cruzados", "pulgar_arriba", "celebrando"]
ETIQUETAS = {"explicando": "EXPLICANDO", "senalando": "SEÑALANDO", "pensando": "PENSANDO",
             "presentando": "PRESENTANDO", "preguntando": "PREGUNTANDO", "brazos_cruzados": "BRAZOS CRUZADOS",
             "pulgar_arriba": "PULGAR ARRIBA", "celebrando": "CELEBRANDO"}

# Biblioteca de manos trazadas: (personaje, caja en su guía, codo, muñeca) en coordenadas de guía
MANOS = {
    "abierta": ("blue", (163, 104, 216, 160), (147, 160), (170, 144)),
    "puno": ("blue", (52, 166, 90, 204), (45, 153), (60, 176)),
    "indice": ("green", (143, 74, 186, 128), (139, 142), (151, 122)),
}

# brazos cruzados en la guía (filas en coordenadas de guía): esa franja del torso no se ve
# en la guía; en otras poses se rellena prolongando la fila de justo encima
SIN_BRAZOS_FUERA = {"purple"}
BRAZO_JUNTO_A_CABEZA = {"teal"}          # mano detrás de la cabeza en la guía
CRUZADOS = {"rich": (138, 188), "purple": (122, 160)}

# poses: mano (izquierda/derecha de la imagen) = (dx, dy en distancias entre ojos desde el
# hombro, tipo de mano, giro extra en grados)
DEF_POSES = {
    "explicando":      {"L": (-0.35, 1.75, "puno", 0), "R": (1.75, 0.55, "abierta", 0)},
    "senalando":       {"L": (-0.35, 1.75, "puno", 0), "R": (2.05, -0.1, "indice", -90)},
    "pensando":        {"L": (0.55, 1.15, "puno", 0), "R": (-0.25, -0.35, "puno", 0)},
    "presentando":     {"L": (-0.35, 1.75, "puno", 0), "R": (1.95, 0.25, "abierta", 0)},
    "preguntando":     {"L": (-1.6, 0.75, "abierta", 0), "R": (1.6, 0.75, "abierta", 0)},
    "brazos_cruzados": {"L": (1.15, 0.95, "puno", 0), "R": (-1.15, 0.85, "puno", 0)},
    "pulgar_arriba":   {"L": (-0.35, 1.75, "puno", 0), "R": (1.25, -0.25, "pulgar", 0)},
    "celebrando":      {"L": (-1.05, -1.85, "puno", 0), "R": (1.05, -1.85, "puno", 0)},
}


def _mascaras(d, k):
    w, h = d["lienzo"]
    W, H = int(round(w * k)), int(round(h * k))
    capas = [np.asarray(fiel._poli_mascara(c["polis"], W, H, k)) > 127 for c in d["capas"]]
    interior = np.asarray(fiel._poli_mascara(d["interior"], W, H, k)) > 127
    return capas, interior, W, H


def piezas(clave: str, k: float = 4.0) -> dict:
    """Segmenta el trazado en cuerpo y brazos, y calcula los pivotes (px a escala k)."""
    d = fiel.cargar(clave)
    capas, interior, W, H = _mascaras(d, k)
    sil = interior.copy()
    for m in capas:
        sil |= m
    # rellenar huecos (rendijas oscuras entre prendas) para que la apertura no rompa el torso
    (mx, my), s = d["rostro"]["medio"], d["rostro"]["escala"]
    mx, my, s = mx * k, my * k, s * k
    n, lab, st, _ = cv2.connectedComponentsWithStats((~sil).astype(np.uint8), 4)
    for i in range(1, n):          # solo huecos pequeños (no el espacio entre brazo y cuerpo)
        x, y, w, h, a = st[i]
        if a < (0.35 * s) ** 2 and x > 0 and y > 0 and x + w < W and y + h < H:
            sil |= lab == i
    # eje del cuerpo: centro de la silueta en las filas del cuello/torso
    filas = range(int(my + 1.0 * s), min(H, int(my + 2.1 * s)))
    anchos = []
    for y in filas:
        xs = np.where(sil[y])[0]
        if len(xs):
            cx = xs.mean()
            # tramo que contiene el centro
            run = xs[np.abs(xs - np.median(xs)) < 2.5 * s]
            anchos.append((run.max() - run.min(), y, (run.max() + run.min()) / 2))
    ancho_cuello, y_cuello, cx = min(anchos) if anchos else (s, int(my + 1.5 * s), mx)
    # banda del torso: el ancho de la figura a la altura de la cadera/muslos (abajo del todo,
    # donde ya no hay brazos), centrado en el eje del cuello
    y_b = int(H - 0.15 * s)
    fila = np.where(sil[y_b])[0]
    fila = fila[np.abs(fila - cx) < 1.3 * s]
    medio_ancho = (fila.max() - fila.min()) / 2 if len(fila) else 0.8 * s
    medio_ancho = float(np.clip(medio_ancho, 0.7 * s, 0.95 * s))   # rango medido en las figuras completas
    tx0, tx1 = cx - medio_ancho - 0.06 * s, cx + medio_ancho + 0.06 * s
    xs = np.arange(W)[None, :]
    banda = (xs >= tx0) & (xs <= tx1)
    y_hombro = y_cuello + 0.30 * s
    filas_brazo = np.zeros((H, W), bool)
    desde = y_cuello - 1.6 * s if d["clave"] in BRAZO_JUNTO_A_CABEZA else y_hombro   # brazo levantado
    filas_brazo[int(max(0, desde)): int(H - 0.25 * s)] = True
    semilla = sil & ~banda & filas_brazo
    if d["clave"] in SIN_BRAZOS_FUERA:     # lo que sale de la banda es prenda (capa), no brazo
        semilla[:] = False
    # crecer hacia arriba (manos levantadas) sin entrar en la banda del torso ni en la cabeza
    cabeza = np.zeros((H, W), bool)
    cabeza[: int(y_cuello)] = True
    cabeza &= np.abs(xs - (mx - 0.2 * s)) < (1.15 if d["clave"] in BRAZO_JUNTO_A_CABEZA else 1.75) * s
    permitido = sil & ~banda & ~cabeza
    brazos = semilla
    k3 = np.ones((3, 3), np.uint8)
    for _ in range(int(3 * s)):
        nuevo = (cv2.dilate(brazos.astype(np.uint8), k3) > 0) & permitido
        if (nuevo == brazos).all():
            break
        brazos = nuevo
    medio_torso = (tx0 + tx1) / 2
    ancho_torso = tx1 - tx0
    y_hombro = y_cuello + 0.30 * s
    # medidas de estilo
    dt = cv2.distanceTransform(brazos.astype(np.uint8), cv2.DIST_L2, 5)
    cresta = (dt >= cv2.dilate(dt, np.ones((3, 3), np.uint8))) & (dt > 2)
    ancho_brazo = float(np.median(2 * dt[cresta])) if cresta.sum() > 20 else 0.55 * s
    neones = [c for c in d["capas"] if max(c["color"]) > 200] or d["capas"]
    principal = max(range(len(d["capas"])), key=lambda i: capas[i].sum() if d["capas"][i] in neones else -1)
    m = capas[principal]
    dtm = cv2.distanceTransform(m.astype(np.uint8), cv2.DIST_L2, 5)
    cr = (dtm >= cv2.dilate(dtm, np.ones((3, 3), np.uint8))) & (dtm > 1)
    trazo = float(np.median(2 * dtm[cr])) if cr.sum() > 20 else 0.12 * s
    return dict(d=d, k=k, W=W, H=H, capas=capas, interior=interior, brazos=brazos,
                cuello=(cx, y_cuello), hombros={"L": (medio_torso - 0.36 * ancho_torso, y_hombro),
                                                "R": (medio_torso + 0.36 * ancho_torso, y_hombro)},
                escala=s, ancho_brazo=min(max(ancho_brazo, 0.38 * s), 0.75 * s), trazo=trazo,
                color=d["capas"][principal]["color"],
                color_halo=d["capas"][principal].get("color_halo", d["capas"][principal]["color"]),
                ancho_cuello=ancho_cuello)


def _ik(hombro, mano, a, b, lado):
    sx, sy = hombro
    dx, dy = mano[0] - sx, mano[1] - sy
    dist = max(abs(a - b) + 1e-3, min(math.hypot(dx, dy), a + b - 1e-3))
    ang = math.atan2(dy, dx)
    th = math.acos((a * a + dist * dist - b * b) / (2 * a * dist))
    cands = [(sx + a * math.cos(ang + g * th), sy + a * math.sin(ang + g * th)) for g in (1, -1)]
    codo = max(cands, key=lambda c: 0.6 * c[0] * lado + c[1])
    return codo, (sx + dist * math.cos(ang), sy + dist * math.sin(ang))


_SPRITES: dict = {}


def _sprite(tipo: str, k: float):
    """Mano trazada de la guía: RGBA + muñeca + dirección del antebrazo + escala de su personaje."""
    clave_k = (tipo, k)
    if clave_k not in _SPRITES:
        fuente, (x0, y0, x1, y1), codo, muneca = MANOS[tipo]
        d = fiel.cargar(fuente)
        capas, interior, W, H = _mascaras(d, k)
        img = np.asarray(fiel.render_capas(d, k=k, brillo=False)).astype(np.float32)
        sil = interior.copy()
        for m in capas:
            sil |= m
        caja = np.zeros((H, W), bool)
        caja[int(y0 * k): int(y1 * k), int(x0 * k): int(x1 * k)] = True
        # solo la mano: la parte de la silueta en la caja conectada a la muñeca
        n, lab, st, _ = cv2.connectedComponentsWithStats((sil & caja).astype(np.uint8), 8)
        wx, wy = int(muneca[0] * k), int(muneca[1] * k)
        cerca = lab[max(0, wy - 6): wy + 6, max(0, wx - 6): wx + 6]
        ids = [i for i in np.unique(cerca) if i > 0] or [max(range(1, n), key=lambda i: st[i, 4])]
        mano = np.isin(lab, ids)
        lum = img.max(2) / 255.0
        _SPRITES[clave_k] = dict(mano=mano, lum=lum, codo=(codo[0] * k, codo[1] * k), muneca=(wx, wy),
                                 escala=d["rostro"]["escala"] * k)
    return _SPRITES[clave_k]


def _pegar_mano(lienzo: Image.Image, tipo: str, muneca, direccion, P, giro_extra=0.0):
    """Coloca la mano trazada en la muñeca, orientada según el antebrazo, en el color del personaje."""
    base = "puno" if tipo == "pulgar" else tipo
    sp = _sprite(base, P["k"])
    f = P["escala"] / sp["escala"]
    ys, xs = np.where(sp["mano"])
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    lum = sp["lum"][y0:y1, x0:x1]
    alfa = sp["mano"][y0:y1, x0:x1]
    color = np.array(P["color"], np.float32)
    rgb = np.clip(lum[..., None] * color[None, None] / max(1.0, float(lum[alfa].max())), 0, 255)
    rgba = np.dstack([rgb, alfa * 255]).astype(np.uint8)
    im = Image.fromarray(rgba)
    im = im.resize((max(1, int(im.width * f)), max(1, int(im.height * f))), Image.LANCZOS)
    # ángulo: del antebrazo original al nuevo
    a0 = math.degrees(math.atan2(sp["muneca"][1] - sp["codo"][1], sp["muneca"][0] - sp["codo"][0]))
    a1 = math.degrees(math.atan2(direccion[1], direccion[0]))
    rot = -(a1 - a0) + giro_extra
    pivote = ((sp["muneca"][0] - x0) * f, (sp["muneca"][1] - y0) * f)
    W2 = int(math.hypot(im.width, im.height) * 2) + 4
    lienzo_mano = Image.new("RGBA", (W2, W2), (0, 0, 0, 0))
    lienzo_mano.paste(im, (int(W2 / 2 - pivote[0]), int(W2 / 2 - pivote[1])), im)
    lienzo_mano = lienzo_mano.rotate(rot, resample=Image.BICUBIC, center=(W2 / 2, W2 / 2))
    pos = (int(muneca[0] - W2 / 2), int(muneca[1] - W2 / 2))
    lienzo.paste(lienzo_mano, pos, lienzo_mano)
    if tipo == "pulgar":                        # pulgar levantado sobre el puño, mismo trazo
        d = ImageDraw.Draw(lienzo)
        ax, ay = muneca[0] + 0.05 * P["escala"], muneca[1] - 0.25 * P["escala"]
        bx, by = ax, ay - 0.42 * P["escala"]
        w = int(0.2 * P["escala"])
        d.line([(ax, ay), (bx, by)], fill=tuple(P["color"]), width=w)
        d.ellipse([bx - w / 2, by - w / 2, bx + w / 2, by + w / 2], fill=tuple(P["color"]))
        wi = max(1, int(w - 2 * P["trazo"]))
        d.line([(ax, ay + 2), (bx, by)], fill=(0, 0, 0), width=wi)
        d.ellipse([bx - wi / 2, by - wi / 2, bx + wi / 2, by + wi / 2], fill=(0, 0, 0))


def _tubos(mask_img: Image.Image, segs, ancho):
    d = ImageDraw.Draw(mask_img)
    for a, b in segs:
        d.line([a, b], fill=255, width=max(1, int(ancho)))
        for x, y in (a, b):
            d.ellipse([x - ancho / 2, y - ancho / 2, x + ancho / 2, y + ancho / 2], fill=255)


def render_pose(clave: str, pose: str, expresion: str = "happy", k: float = 3.0, brillo: bool = True) -> Image.Image:
    """Personaje en una de las 8 poses oficiales (o 'guia' para su pose original)."""
    if pose == "guia":
        return fiel.render_capas(clave, k=k, expresion=expresion, brillo=brillo)
    P = piezas(clave, k)
    d, W, H, s = P["d"], P["W"], P["H"], P["escala"]
    margen = int(2.2 * s)
    W2, H2 = W + 2 * margen, H + margen
    off = np.array([margen, margen])
    capas = [np.pad(m & ~P["brazos"], ((margen, 0), (margen, margen))) for m in P["capas"]]
    interior = np.pad(P["interior"] & ~P["brazos"], ((margen, 0), (margen, margen)))
    clave_c = d["clave"]
    if clave_c in CRUZADOS:                      # franja tapada por los brazos cruzados en la guía
        ya, yb = (int(v * k) + margen for v in CRUZADOS[clave_c])
        for m in capas + [interior]:
            m[ya:yb] = m[ya - 1][None, :]
    hombros = {l: (x + off[0], y + off[1]) for l, (x, y) in P["hombros"].items()}
    brazo, antebrazo = 1.05 * s, 1.0 * s
    segs, manos = [], []
    for lado, sgn in (("L", -1), ("R", 1)):
        dx, dy, tipo, giro = DEF_POSES[pose][lado]
        hx, hy = hombros[lado]
        objetivo = (hx + dx * s, hy + dy * s)
        codo, muneca = _ik((hx, hy), objetivo, brazo, antebrazo, sgn)
        segs.append(((hx, hy), codo))
        segs.append((codo, muneca))
        manos.append((tipo, muneca, (muneca[0] - codo[0], muneca[1] - codo[1]), giro))
    # silueta de los brazos nuevos: contorno neón con el grosor medido
    ext = Image.new("L", (W2, H2), 0)
    inn = Image.new("L", (W2, H2), 0)
    _tubos(ext, segs, P["ancho_brazo"] + P["trazo"])
    _tubos(inn, segs, max(1.0, P["ancho_brazo"] - P["trazo"]))
    ext_a, inn_a = np.asarray(ext) > 127, np.asarray(inn) > 127
    delante = pose in ("brazos_cruzados", "pensando")
    lienzo = np.zeros((H2, W2, 3), np.float32) + np.array(d.get("fondo", [0, 0, 0]), np.float32)
    trazo_brazos = ext_a & ~inn_a
    if brillo:
        hr = d["halo_render"]
        fuentes = [(c, m) for c, m in zip(d["capas"], capas)] + [({"color": P["color"], "color_halo": P["color_halo"]}, trazo_brazos)]
        for c, m in fuentes:
            mi = Image.fromarray((m * 255).astype(np.uint8))
            luz = np.zeros((H2, W2), np.float32)
            for s_, a_ in ((hr["s1"], hr["a1"]), (hr["s2"], hr["a2"])):
                luz += a_ * np.asarray(mi.filter(ImageFilter.GaussianBlur(s_ * k)), np.float32) / 255
            lienzo += np.clip(luz, 0, 1)[..., None] * np.array(c.get("color_halo", c["color"]), np.float32)
    lienzo = np.clip(lienzo, 0, 255)
    color = np.array(P["color"], np.float32)

    def brazos_dibujar(a):
        a[ext_a] = color
        a[inn_a] = 0
    if not delante:
        brazos_dibujar(lienzo)
    lienzo[interior] = 0
    for c, m in zip(d["capas"], capas):
        lienzo[m] = np.array(c["color"], np.float32)
    if delante:
        brazos_dibujar(lienzo)
    img = Image.fromarray(lienzo.astype(np.uint8))
    for tipo, muneca, direc, giro in manos:
        _pegar_mano(img, tipo, muneca, direc, dict(P, k=k), giro)
    dd = dict(d)
    dd["rostro"] = {"medio": [d["rostro"]["medio"][0] + margen / k, d["rostro"]["medio"][1] + margen / k],
                    "escala": d["rostro"]["escala"]}
    fiel.dibujar_rostro(img, dd, k, expresion)
    return img
