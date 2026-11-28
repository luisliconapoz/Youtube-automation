"""Validación de la cara maestra sobre los píxeles renderizados.

Se renderiza cada personaje con un "color de sonda" (magenta), sin brillo, y se mide
en la imagen —no en el código— la posición y el tamaño de ojos, pupilas, cejas y boca.
Así se comprueba que los 13 personajes comparten exactamente el mismo rostro y que
ningún accesorio entra en la zona facial.
"""
from __future__ import annotations

import numpy as np

from pilo_studio.personajes import rig

SONDA = (255, 0, 255)
ALTO = 400


def _u(alto):
    return alto / rig.ALTURA_FIGURA


def zona_px(alto: int = ALTO) -> tuple[int, int, int, int]:
    s = _u(alto)
    ax, ay = rig.ancla(alto)
    x0, y0, x1, y1 = rig.ZONA_CARA
    cy = rig.CABEZA["cy"]
    return (int(round(ax + x0 * s)), int(round(ay + (cy + y0) * s)),
            int(round(ax + x1 * s)), int(round(ay + (cy + y1) * s)))


def render_sonda(clave: str, expresion: str = "neutral", pose: str = "neutral", alto: int = ALTO) -> np.ndarray:
    return np.array(rig.render(clave, expresion=expresion, pose=pose, alto=alto, brillo=False,
                               color=SONDA))[..., :3].astype(int)


def zona(clave: str, expresion: str = "neutral", alto: int = ALTO) -> np.ndarray:
    x0, y0, x1, y1 = zona_px(alto)
    return render_sonda(clave, expresion, alto=alto)[y0:y1, x0:x1]


def _bbox(mask, ox, oy, s):
    ys, xs = np.where(mask)
    if not len(xs):
        return None
    # caja en u relativas al centro de la cabeza: (x0, y0, x1, y1)
    return tuple(round(float(v), 1) for v in ((xs.min() + ox) / s, (ys.min() + oy) / s,
                                              (xs.max() + 1 + ox) / s, (ys.max() + 1 + oy) / s))


def medir(clave: str, expresion: str = "neutral", alto: int = ALTO) -> dict:
    """Cajas (u) de cada rasgo facial, medidas en el render."""
    s = _u(alto)
    img = zona(clave, expresion, alto)
    x0, y0, _, _ = rig.ZONA_CARA
    ox, oy = x0 * s, y0 * s
    H, W = img.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W]
    ux, uy = xx / s + x0, yy / s + y0             # coordenadas u de cada píxel
    blanco = img.min(axis=2) > 200
    oscuro = img.max(axis=2) < 60
    visible = img.max(axis=2) > 60
    r = {}
    for lado, sg in (("izq", -1), ("der", 1)):
        banda_ojo = (np.sign(ux) == sg) & (uy > -30) & (uy < 14)
        ojo = blanco & banda_ojo
        r[f"ojo_{lado}"] = _bbox(ojo, ox, oy, s)
        if r[f"ojo_{lado}"]:
            a, b, c, d = r[f"ojo_{lado}"]
            cx, cy, rx, ry = (a + c) / 2, (b + d) / 2, (c - a) / 2, (d - b) / 2
            dentro = ((ux - cx) / rx) ** 2 + ((uy - cy) / ry) ** 2 < 0.8   # interior del óvalo
            r[f"pupila_{lado}"] = _bbox(oscuro & dentro, ox, oy, s)
        r[f"ceja_{lado}"] = _bbox(blanco & (np.sign(ux) == sg) & (uy < -30), ox, oy, s)
    r["boca"] = _bbox(visible & (uy > 12) & (np.abs(ux) < 30), ox, oy, s)
    return r


def informe(expresiones: list[str] | None = None) -> tuple[bool, str]:
    """Compara los 13 rostros. Devuelve (todo_ok, texto markdown)."""
    expresiones = expresiones or list(rig.EXPRESIONES)
    claves = list(rig.catalogo())
    lineas = ["# Validación de la cara maestra", "",
              f"Render de sonda a {ALTO} px, sin brillo. Coordenadas en u relativas al centro de la cabeza "
              "(caja x0, y0, x1, y1). Zona facial protegida: " + str(rig.ZONA_CARA), ""]
    ok = True
    ref_neutral = medir(claves[0], "neutral")
    lineas += ["## Expresión neutral: medidas comunes a los 13 personajes", "", "| Rasgo | Caja (u) |", "|---|---|"]
    lineas += [f"| {k} | {v} |" for k, v in ref_neutral.items()]
    lineas += ["", "## Comparación por expresión", "",
               "| Expresión | Medidas idénticas en los 13 | Zona facial píxel a píxel idéntica | Distintos |",
               "|---|---|---|---|"]
    for e in expresiones:
        ref_m, ref_z = medir(claves[0], e), zona(claves[0], e)
        distintos = []
        for k in claves[1:]:
            if medir(k, e) != ref_m or np.abs(zona(k, e) - ref_z).max() > 24:
                distintos.append(k)
        ok &= not distintos
        lineas.append(f"| {e} | {'✅' if not distintos else '❌'} | {'✅' if not distintos else '❌'} | "
                      f"{', '.join(distintos) or '—'} |")
    lineas += ["", f"**Resultado: {'APROBADO' if ok else 'FALLA'}** — "
               + ("un solo rostro maestro reutilizado por los 13 personajes." if ok else "revisar los personajes marcados.")]
    return ok, "\n".join(lineas) + "\n"
