"""Fidelidad a las guías oficiales (prueba de BLUE)."""
import pytest

from pilo_studio.personajes import fiel


def test_trazado_de_blue_completo():
    d = fiel.cargar_trazado("blue")
    for clave in ("trazo", "interior", "ojos", "ojos_blanco", "boca", "lengua", "cejas", "halo_render"):
        assert d[clave], clave
    assert len(d["ojos"]) == 2


def test_render_de_blue_en_el_marco_de_la_guia():
    img = fiel.render_trazado("blue", k=2)
    w, h = fiel.cargar_trazado("blue")["lienzo"]
    assert img.size == (w * 2, h * 2)


def test_blue_coincide_con_la_guia_por_partes():
    pytest.importorskip("cv2")
    from pilo_studio.personajes import comparar
    r = comparar.medir("blue")
    assert max(abs(v) for v in r["alineacion_px"]) < 0.5
    assert r["silueta"]["iou"] > 0.98 and r["silueta"]["dist_media"] < 0.5
    assert r["mechon"]["iou"] > 0.95
    assert r["brazo_der_y_mano"]["iou"] > 0.95 and r["brazo_izq_y_puno"]["iou"] > 0.95
    assert r["ojo_izq"]["iou"] > 0.93 and r["ojo_der"]["iou"] > 0.93
    assert r["lengua"]["iou"] > 0.9 and r["boca"]["iou"] > 0.85
    assert r["halo"]["error_medio"] < 6
