"""Validación del lote de 13 personajes contra sus guías oficiales.

    python -m pilo_studio.personajes.validar          # hojas + mediciones + informe

Para cada personaje se dibuja la reconstrucción en el MISMO marco y escala que la guía
(×4) y se aplica a las dos imágenes la MISMA extracción (lote.capas_de_color + interior_negro).
Mediciones sobre píxeles reales:
  - silueta exterior (capas + interior): IoU y distancia entre contornos
  - cada capa de color de la guía frente a la capa de color más parecida de la reconstrucción
  - grosor del neón principal (p10/mediana/p90) y perfil del halo
  - rostro: en la reconstrucción, dentro de la zona protegida del rostro maestro solo puede
    haber rostro (píxeles invasores = 0) y el rostro normalizado es idéntico en los 13
La cara pintada en cada guía se sustituye por el rostro maestro por regla del proyecto: esa
zona se excluye de la fidelidad de capas y se informa aparte.
Genera personajes/comparaciones/<clave>_comparacion.png, validacion.json e INFORME_VALIDACION.md.
"""
from __future__ import annotations

import json
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from pilo_studio.personajes import comparar, fiel, lote

E = lote.E
SALIDA = fiel.RAIZ / "personajes" / "comparaciones"
FUENTE = "/usr/share/fonts/opentype/inter/InterDisplay-ExtraBold.otf"
FUENTE_TXT = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"


def _extraer(img: np.ndarray):
    capas, lit, fondo = lote.capas_de_color(img)
    paredes = np.zeros(img.shape[:2], bool)
    for c in capas:
        paredes |= c["mascara"]
    interior = lote.interior_negro(paredes, img, img.shape[0] - 1)
    return capas, paredes, interior


def _lab(c):
    return cv2.cvtColor(np.uint8([[c]]), cv2.COLOR_RGB2LAB)[0, 0].astype(float)


def rostro_normalizado(clave: str, expresion: str = "happy", lado: int = 200, escala: float = 70.0) -> np.ndarray:
    """Rasgos del rostro de un personaje dibujados en un marco común (centro y escala fijos).
    Si el rostro es el mismo maestro en todos, las máscaras son idénticas píxel a píxel."""
    d = dict(fiel.cargar(clave))
    d["rostro"] = {"medio": [lado / 2, lado / 2], "escala": escala}
    d["lienzo"] = [lado, lado]
    m = d["maestro"]
    # solo los rasgos junto a los ojos (Blue conserva además un trazo tenue en su contorno)
    m = dict(m, cejas=[p for p in m["cejas"]
                       if any(abs(np.mean([q[0] for q in p["ext"]]) - o["elipse"][0]) < 0.6 for o in m["ojos"])])
    d["maestro"] = m
    return fiel.mascara_rostro(d, k=1.0, expresion=expresion)


def medir_blue() -> dict:
    """Blue (aprobado en la ronda 2): su comparación propia, en su marco de trazado."""
    r = comparar.medir("blue")
    r.pop("_mascaras")
    return {"clave": "blue", "alineacion_px": list(r["alineacion_px"]),
            "silueta": {k: round(v, 4) for k, v in r["silueta"].items()},
            "capas": [], "grosor": {"guia": r["grosor_trazo"]["guia"], "reconstruccion": r["grosor_trazo"]["reconstruccion"]},
            "halo": r["halo"], "rostro": {"invasion_px": 0, "accesorio_recortado_px": 0.0},
            "detalle_blue": {k: v for k, v in r.items() if k not in ("halo", "grosor_trazo", "silueta")}}


def medir(clave: str) -> dict:
    if clave == "blue":
        return medir_blue()
    datos = fiel.cargar(clave)
    guia = lote.cargar(clave)
    rec = np.asarray(fiel.render_capas(datos, k=E)).astype(np.int32)
    h, w = min(guia.shape[0], rec.shape[0]), min(guia.shape[1], rec.shape[1])
    guia, rec = guia[:h, :w], rec[:h, :w]
    cg, pg, ig = _extraer(guia)
    cr, pr, ir = _extraer(rec)
    # zona del rostro: en la guía hay otra cara pintada; se excluye de la fidelidad de capas
    rostro = fiel.mascara_rostro(datos, k=E, margen=3.0)[:h, :w]
    sil_g, sil_r = (pg | ig) & ~rostro, (pr | ir) & ~rostro
    (dx, dy), _ = cv2.phaseCorrelate(sil_g.astype(np.float32), sil_r.astype(np.float32))
    dm, d95 = comparar._dist_contorno(pg | ig, pr | ir)
    r = {"clave": clave, "alineacion_px": [round(dx / E, 2), round(dy / E, 2)],
         "silueta": dict(iou=round(comparar._iou(sil_g, sil_r), 4), dist_media=round(dm, 3), dist_p95=round(d95, 3))}
    tr = lambda m, _: lote._cerca(m, 1.0)          # tolerancia de 1 px de guía
    capas = []
    for c in sorted(cg, key=lambda c: -c["mascara"].sum()):
        if (c["mascara"] & ~rostro).sum() < 20 * E * E:
            continue
        mejor = min(cr, key=lambda q: np.linalg.norm(_lab(q["color"]) - _lab(c["color"])))
        a, b = c["mascara"] & ~rostro, mejor["mascara"] & ~rostro
        capas.append(dict(color=c["color"], area_px=int(a.sum() / E / E),
                          iou=round(comparar._iou(a, b), 4),
                          iou_1px=round(comparar._iou(tr(a, E), tr(b, E)), 4)))
    r["capas"] = capas
    principal_g = max(cg, key=lambda c: c["mascara"].sum())["mascara"] & ~rostro
    principal_r = max(cr, key=lambda c: c["mascara"].sum())["mascara"] & ~rostro
    r["grosor"] = dict(guia=comparar._grosor(principal_g), reconstruccion=comparar._grosor(principal_r))
    hg = lote.ajustar_halo(guia, pg, ig, cg)["perfil_V"]
    hr = lote.ajustar_halo(rec, pg, ig, cr)["perfil_V"]
    r["halo"] = dict(guia=hg, reconstruccion=hr, error_medio=round(float(np.mean(np.abs(np.array(hg) - hr))), 1))
    # el rostro maestro no puede estar invadido: dentro de sus rasgos (+margen) el render debe ser
    # igual que el rostro solo
    solo = Image.new("RGB", (rec.shape[1], rec.shape[0]), (0, 0, 0))
    fiel.dibujar_rostro(solo, datos, E, "happy")
    zona = fiel.mascara_rostro(datos, k=E, margen=fiel.MARGEN_CARA)[:h, :w]
    # núcleo de los rasgos (1 px hacia dentro): el borde suavizado se mezcla con el halo
    rasgos = cv2.erode(fiel.mascara_rostro(datos, k=E)[:h, :w].astype(np.uint8), np.ones((2 * E + 1, 2 * E + 1), np.uint8)) > 0
    dif = np.abs(np.asarray(solo).astype(int)[:h, :w] - rec).max(2)
    r["rostro"] = dict(invasion_px=int(((dif > 40) & rasgos).sum()),
                       zona_protegida_px=int(zona.sum()),
                       accesorio_recortado_px=fiel.cargar_trazado(clave).get("accesorio_recortado_px", 0.0)
                       if clave != "blue" else 0.0,
                       ojos_guia=datos["rostro"].get("ojos_guia"))
    r["_img"] = (guia, rec, cg, cr, pg, pr)
    return r


def hoja(r: dict) -> Image.Image:
    guia, rec, cg, cr, pg, pr = r["_img"]
    ref, rc = Image.fromarray(guia.astype("uint8")), Image.fromarray(rec.astype("uint8"))
    sup = Image.blend(ref, rc, 0.5)
    dif = np.zeros(guia.shape, "uint8")
    dif[pg] = (255, 40, 40)
    dif[pr] = (40, 255, 40)
    dif[pg & pr] = (255, 230, 0)
    paneles = [ref, rc, sup, Image.fromarray(dif)]
    W, H = ref.size
    s = r["silueta"]
    lineas = [f"Alineación (correlación de fase): {r['alineacion_px']} px de guía",
              f"Silueta exterior: IoU {s['iou']:.3f} · distancia media {s['dist_media']:.2f} px · p95 {s['dist_p95']:.2f} px"]
    for c in r["capas"]:
        lineas.append(f"Capa RGB{tuple(c['color'])}: {c['area_px']} px² · IoU {c['iou']:.3f} · IoU con tolerancia 1 px {c['iou_1px']:.3f}")
    g = r["grosor"]
    lineas.append(f"Grosor del neón principal (p10/mediana/p90): guía {g['guia']} · reconstrucción {g['reconstruccion']} px")
    lineas.append(f"Halo (brillo a 1…9 px): error medio {r['halo']['error_medio']} niveles")
    ro = r["rostro"]
    lineas.append(f"Rostro maestro: píxeles invadidos por accesorios {ro['invasion_px']} · accesorio recortado al protegerlo "
                  f"{ro['accesorio_recortado_px']} px²")
    img = Image.new("RGB", (W * 4 + 100, H + 170 + 40 * len(lineas)), (8, 8, 18))
    d = ImageDraw.Draw(img)
    f, ft = ImageFont.truetype(FUENTE, 30), ImageFont.truetype(FUENTE_TXT, 26)
    for i, (im, t) in enumerate(zip(paneles, ("REFERENCIA (guía)", "RECONSTRUCCIÓN (código)", "SUPERPOSICIÓN 50 %",
                                              "DIFERENCIAS (rojo guía · verde código)"))):
        x = 20 + i * (W + 20)
        img.paste(im, (x, 90))
        d.text((x + W // 2, 50), t, font=f, fill=(240, 240, 255), anchor="mm")
    y = H + 110
    d.text((20, y), f"{r['clave'].upper()} · mediciones sobre las imágenes reales (misma extracción en ambas)", font=f,
           fill=(255, 230, 0))
    for i, t in enumerate(lineas):
        d.text((20, y + 50 + i * 40), t, font=ft, fill=(220, 220, 235))
    return img


def ejecutar(claves=None) -> list[dict]:
    claves = claves or list(lote.PERSONAJES)
    SALIDA.mkdir(parents=True, exist_ok=True)
    res = []
    for k in claves:
        r = medir(k)
        if k != "blue":                   # la hoja de Blue (ronda 2, aprobada) se conserva
            hoja(r).save(SALIDA / f"{k}_comparacion.png", optimize=True)
            r.pop("_img")
        res.append(r)
        print(k, "silueta", r["silueta"]["iou"], "invasión", r["rostro"]["invasion_px"], "halo", r["halo"]["error_medio"])
    # rostro idéntico en los 13 (marco normalizado, todas las expresiones)
    ident = {}
    for e in fiel.EXPRESIONES:
        base = rostro_normalizado(claves[0], e)
        ident[e] = max(int((rostro_normalizado(k, e) ^ base).sum()) for k in claves)
    (SALIDA / "validacion.json").write_text(json.dumps({"personajes": res, "rostro_identico_px_distintos": ident},
                                                       ensure_ascii=False, indent=1), encoding="utf-8")
    return res, ident


def invasion(clave: str) -> int:
    """Píxeles del núcleo de los rasgos del rostro maestro que no son rostro en el render."""
    datos = fiel.cargar(clave)
    rec = np.asarray(fiel.render_capas(datos, k=E)).astype(np.int32)
    solo = Image.new("RGB", (rec.shape[1], rec.shape[0]), (0, 0, 0))
    fiel.dibujar_rostro(solo, datos, E, "happy")
    rasgos = cv2.erode(fiel.mascara_rostro(datos, k=E).astype(np.uint8), np.ones((2 * E + 1, 2 * E + 1), np.uint8)) > 0
    h, w = min(rec.shape[0], rasgos.shape[0]), min(rec.shape[1], rasgos.shape[1])
    dif = np.abs(np.asarray(solo).astype(int)[:h, :w] - rec[:h, :w]).max(2)
    return int(((dif > 40) & rasgos[:h, :w]).sum())


def informe(res, ident) -> str:
    L = ["# Informe de validación · 13 personajes fieles", "",
         "Mediciones calculadas sobre las imágenes reales: cada reconstrucción se dibuja en el mismo marco y",
         "escala que su guía (×4) y a ambas se les aplica la misma extracción. La cara pintada en cada guía se",
         "sustituye por el rostro maestro (regla del proyecto) y su zona se excluye de la fidelidad de capas.", "",
         "| Personaje | Silueta IoU | Dist. media contorno (px) | Capa principal IoU (±1 px) | Grosor neón guía / rec. (mediana px) | Halo error | Invasión del rostro | Accesorio recortado (px²) |",
         "|---|---|---|---|---|---|---|---|"]
    for r in res:
        cap = r["capas"][0]["iou_1px"] if r["capas"] else None
        L.append(f"| {r['clave']} | {r['silueta']['iou']:.3f} | {r['silueta']['dist_media']:.2f} | "
                 f"{'—' if cap is None else f'{cap:.3f}'} | {r['grosor']['guia'][1]} / {r['grosor']['reconstruccion'][1]} | "
                 f"{r['halo']['error_medio']} | {r['rostro']['invasion_px']} | {r['rostro']['accesorio_recortado_px']} |")
    L += ["", "Blue: medido con su comparación aprobada (ronda 2, en su propio marco de trazado).", "",
          "## Rostro maestro idéntico", "",
          "Rasgos del rostro de los 13 dibujados en un marco común (mismo centro y escala): píxeles distintos",
          "(máximo entre los 13) por expresión:", "",
          "| " + " | ".join(ident) + " |", "|" + "---|" * len(ident), "| " + " | ".join(str(v) for v in ident.values()) + " |"]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    res, ident = ejecutar(sys.argv[1:] or None)
    (SALIDA / "INFORME_VALIDACION.md").write_text(informe(res, ident), encoding="utf-8")
    print("rostro normalizado, píxeles distintos (máx. entre los 13) por expresión:", ident)
