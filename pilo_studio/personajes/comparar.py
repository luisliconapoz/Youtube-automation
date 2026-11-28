"""Hoja de comparación de fidelidad con la guía oficial.

    python -m pilo_studio.personajes.comparar blue

Paneles: referencia | reconstrucción | superposición 50 % | diferencias (rojo = solo guía,
verde = solo reconstrucción, amarillo = coinciden). Las dos imágenes están en el mismo marco
y escala (la reconstrucción se dibuja en coordenadas de la guía ×4) y la alineación se
comprueba por correlación de fase. A ambas se les aplica la MISMA extracción
(trazar.mascaras) y se miden por separado: silueta, ojos/pupilas, cejas/boca, mechón,
manos/brazos y grosor/halo neón. Requiere opencv (herramienta de desarrollo).
"""
from __future__ import annotations

import json
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from pilo_studio.personajes import fiel, trazar

E = trazar.E
FUENTE = "/usr/share/fonts/opentype/inter/InterDisplay-ExtraBold.otf"
FUENTE_TXT = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
ALTO = 210            # la guía corta el retrato en y≈210 (debajo está el texto de la tarjeta)

# zonas de medida en px de guía (x0, y0, x1, y1)
ZONAS = {"blue": {
    "mechon": (110, 4, 168, 47),
    "brazo_izq_y_puno": (28, 115, 90, 202),
    "brazo_der_y_mano": (115, 104, 216, 180),
    "cabeza": (52, 14, 166, 116),
}}


def _iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 1.0


def _borde(m):
    m8 = m.astype(np.uint8)
    return (m8 - cv2.erode(m8, np.ones((3, 3), np.uint8))) > 0


def _dist_contorno(a, b):
    """Distancia media y p95 (px de guía) entre los contornos de dos máscaras."""
    ba, bb = _borde(a), _borde(b)
    if not ba.any() or not bb.any():
        return float("nan"), float("nan")
    da = cv2.distanceTransform((~bb).astype(np.uint8), cv2.DIST_L2, 5)[ba]
    db = cv2.distanceTransform((~ba).astype(np.uint8), cv2.DIST_L2, 5)[bb]
    d = np.concatenate([da, db]) / E
    return float(d.mean()), float(np.percentile(d, 95))


def _caja(m, z):
    x0, y0, x1, y1 = (v * E for v in z)
    r = np.zeros_like(m)
    r[y0:y1, x0:x1] = m[y0:y1, x0:x1]
    return r


def _grosor(trazo):
    """Grosor del neón (px de guía): 2 × distancia al borde sobre la línea media del trazo."""
    dt = cv2.distanceTransform(trazo.astype(np.uint8), cv2.DIST_L2, 5)
    cresta = (dt >= cv2.dilate(dt, np.ones((3, 3), np.uint8))) & (dt > 1)
    v = 2 * dt[cresta] / E
    return [round(float(np.percentile(v, q)), 2) for q in (10, 50, 90)]


def medir(clave: str) -> dict:
    datos = fiel.cargar_trazado(clave)
    g_ref, _ = trazar._cargar(clave)
    g_rec = np.array(fiel.render_trazado(datos, k=E)).astype(np.int32)
    h = min(g_ref.shape[0], g_rec.shape[0])
    g_ref, g_rec = g_ref[:h], g_rec[:h]
    A, B = trazar.mascaras(g_ref), trazar.mascaras(g_rec)
    sil_a, sil_b = A["trazo"] | A["interior"], B["trazo"] | B["interior"]
    (dx, dy), _ = cv2.phaseCorrelate(sil_a.astype(np.float32), sil_b.astype(np.float32))
    z = ZONAS[clave]
    r = {"alineacion_px": (round(dx / E, 2), round(dy / E, 2))}
    dm, d95 = _dist_contorno(sil_a, sil_b)
    r["silueta"] = dict(iou=_iou(sil_a, sil_b), dist_media=dm, dist_p95=d95)
    dm, d95 = _dist_contorno(_caja(sil_a, z["cabeza"]), _caja(sil_b, z["cabeza"]))
    r["cabeza"] = dict(iou=_iou(_caja(sil_a, z["cabeza"]), _caja(sil_b, z["cabeza"])), dist_media=dm, dist_p95=d95)
    for i, lado in enumerate(("izq", "der")):
        oa = A["labb"] == A["ojos_ids"][i]
        ob = B["labb"] == B["ojos_ids"][i]
        ya, xa = np.argwhere(oa).mean(0) / E
        yb, xb = np.argwhere(ob).mean(0) / E
        # pupila visible = negro dentro del contorno convexo del blanco del ojo
        def pupila(M, o):
            hull = cv2.convexHull(np.argwhere(o)[:, ::-1].astype(np.int32))
            casco = np.zeros(o.shape, np.uint8)
            cv2.fillConvexPoly(casco, hull, 1)
            return (casco > 0) & ~o & (M["g"].max(2) < 80)
        pa, pb = pupila(A, oa), pupila(B, ob)
        r[f"ojo_{lado}"] = dict(iou=_iou(oa, ob), desplazamiento=round(float(np.hypot(xa - xb, ya - yb)), 2),
                               area_rel=round(float(ob.sum() / oa.sum()), 3))
        r[f"pupila_{lado}"] = dict(iou=_iou(pa, pb), area_rel=round(float(pb.sum() / max(1, pa.sum())), 3))
    ba, bb = np.isin(A["labb"], A["boca_ids"]), np.isin(B["labb"], B["boca_ids"])
    r["boca"] = dict(iou=_iou(ba, bb), dist_media=_dist_contorno(ba, bb)[0])
    r["lengua"] = dict(iou=_iou(A["rojo"], B["rojo"]), dist_media=_dist_contorno(A["rojo"], B["rojo"])[0])
    r["cejas"] = dict(iou=_iou(A["cejas"], B["cejas"]))
    for nombre in ("mechon", "brazo_izq_y_puno", "brazo_der_y_mano"):
        a, b = _caja(sil_a, z[nombre]), _caja(sil_b, z[nombre])
        ta, tb = _caja(A["trazo"], z[nombre]), _caja(B["trazo"], z[nombre])
        dm, d95 = _dist_contorno(a, b)
        r[nombre] = dict(iou=_iou(a, b), dist_media=dm, dist_p95=d95, iou_trazo_1px=_iou(
            cv2.dilate(ta.astype(np.uint8), np.ones((3, 3))) > 0, cv2.dilate(tb.astype(np.uint8), np.ones((3, 3))) > 0))
    r["grosor_trazo"] = dict(guia=_grosor(A["trazo"]), reconstruccion=_grosor(B["trazo"]))
    pa = trazar.medir_halo(g_ref, A["trazo"], A["interior"])["perfil_azul"][:9]
    pb = trazar.medir_halo(g_rec, A["trazo"], A["interior"])["perfil_azul"][:9]
    r["halo"] = dict(guia=pa, reconstruccion=pb, error_medio=round(float(np.abs(np.array(pa) - pb).mean()), 1))
    r["_mascaras"] = (A, B)
    return r


def _fmt(r) -> list[str]:
    s, c = r["silueta"], r["cabeza"]
    L = [f"Alineación (correlación de fase): desplazamiento residual {r['alineacion_px']} px de guía.",
         f"1. Silueta exterior: IoU {s['iou']:.3f} · distancia media entre contornos {s['dist_media']:.2f} px · p95 {s['dist_p95']:.2f} px",
         f"   Cabeza: IoU {c['iou']:.3f} · distancia media {c['dist_media']:.2f} px · p95 {c['dist_p95']:.2f} px"]
    for lado in ("izq", "der"):
        o, p = r[f"ojo_{lado}"], r[f"pupila_{lado}"]
        L.append(f"2. Ojo {lado}: IoU {o['iou']:.3f} · centro desplazado {o['desplazamiento']:.2f} px · área {o['area_rel']:.0%}"
                 f"   |  pupila {lado}: IoU {p['iou']:.3f} · área {p['area_rel']:.0%}")
    L.append(f"3. Boca (banda blanca): IoU {r['boca']['iou']:.3f} · dist. media {r['boca']['dist_media']:.2f} px  |  "
             f"lengua: IoU {r['lengua']['iou']:.3f} · dist. media {r['lengua']['dist_media']:.2f} px  |  cejas: IoU {r['cejas']['iou']:.3f}")
    m = r["mechon"]
    L.append(f"4. Mechón: IoU {m['iou']:.3f} · dist. media {m['dist_media']:.2f} px · p95 {m['dist_p95']:.2f} px · trazo (±1 px) {m['iou_trazo_1px']:.3f}")
    for n, t in (("brazo_izq_y_puno", "Brazo izq. + puño"), ("brazo_der_y_mano", "Brazo der. + mano")):
        m = r[n]
        L.append(f"5. {t}: IoU {m['iou']:.3f} · dist. media {m['dist_media']:.2f} px · p95 {m['dist_p95']:.2f} px · trazo (±1 px) {m['iou_trazo_1px']:.3f}")
    gr, h = r["grosor_trazo"], r["halo"]
    L.append(f"6. Grosor del neón (p10/mediana/p90, px): guía {gr['guia']} · reconstrucción {gr['reconstruccion']}")
    L.append(f"   Halo (brillo azul a 1…9 px del trazo): guía {h['guia']}")
    L.append(f"                                   reconstrucción {h['reconstruccion']} · error medio {h['error_medio']}")
    return L


def comparar(clave: str):
    r = medir(clave)
    A, B = r.pop("_mascaras")
    ref = Image.fromarray(A["g"].astype("uint8"))
    rec = fiel.render_trazado(clave, k=E).crop((0, 0, ref.width, ref.height))
    sup = Image.blend(ref, rec, 0.5)
    dif = np.zeros(A["g"].shape, "uint8")
    dif[A["trazo"]] = (255, 40, 40)
    dif[B["trazo"]] = (40, 255, 40)
    dif[A["trazo"] & B["trazo"]] = (255, 230, 0)
    for M, col in ((A, (150, 150, 150)), (B, (80, 140, 255))):
        dif[(M["blanco"] | M["rojo"]) & ~(A["blanco"] & B["blanco"]) & ~(A["rojo"] & B["rojo"])] = col
    dif[(A["blanco"] & B["blanco"])] = (255, 255, 255)
    dif[(A["rojo"] & B["rojo"])] = (255, 120, 160)
    dif = Image.fromarray(dif)
    ALTO_PX = ALTO * E
    paneles = [im.crop((0, 0, im.width, ALTO_PX)) for im in (ref, rec, sup, dif)]
    W, H = paneles[0].size
    lineas = _fmt(r)
    img = Image.new("RGB", (W * 4 + 100, H + 200 + 44 * len(lineas)), (8, 8, 18))
    d = ImageDraw.Draw(img)
    f, ft = ImageFont.truetype(FUENTE, 32), ImageFont.truetype(FUENTE_TXT, 27)
    titulos = ("REFERENCIA ORIGINAL (guía)", "RECONSTRUCCIÓN (código)", "SUPERPOSICIÓN 50 %",
               "DIFERENCIAS (rojo guía · verde código)")
    for i, (im, t) in enumerate(zip(paneles, titulos)):
        x = 20 + i * (W + 20)
        img.paste(im, (x, 100))
        d.text((x + W // 2, 55), t, font=f, fill=(240, 240, 255), anchor="mm")
    y = H + 130
    d.text((20, y), f"{clave.upper()} · MEDICIONES INDEPENDIENTES (mismo marco y escala, misma extracción en ambas imágenes)",
           font=f, fill=(255, 230, 0))
    for i, t in enumerate(lineas):
        d.text((20, y + 56 + i * 44), t, font=ft, fill=(220, 220, 235))
    return img, r


if __name__ == "__main__":
    clave = sys.argv[1] if len(sys.argv) > 1 else "blue"
    salida = fiel.RAIZ / "personajes" / "comparaciones"
    salida.mkdir(parents=True, exist_ok=True)
    img, r = comparar(clave)
    img.save(salida / f"{clave}_comparacion.png", optimize=True)
    (salida / f"{clave}_mediciones.json").write_text(json.dumps(r, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("\n".join(_fmt(r)))
