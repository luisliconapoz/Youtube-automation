"""Lote de 13 personajes fieles: datos, rostro maestro, fidelidad, expresiones y poses."""
import numpy as np
import pytest

from pilo_studio.personajes import fiel

CLAVES = ["blue", "green", "pink", "farmer", "rich", "cyan", "lime", "brown", "gray",
          "orange", "purple", "white", "teal"]


@pytest.mark.parametrize("clave", CLAVES)
def test_trazado_completo(clave):
    d = fiel.cargar(clave)
    assert d["capas"] and d["interior"] and d["maestro"]["ojos"]
    assert d["rostro"]["escala"] > 10


def test_blue_aprobado_no_cambia():
    a = np.asarray(fiel.render_trazado("blue", k=2)).astype(int)
    b = np.asarray(fiel.render_capas("blue", k=2)).astype(int)
    assert np.abs(a - b).max() == 0


def test_rostro_maestro_identico_en_los_13():
    cv2 = pytest.importorskip("cv2")  # noqa: F841
    from pilo_studio.personajes import validar
    for e in fiel.EXPRESIONES:
        base = validar.rostro_normalizado("blue", e)
        for k in CLAVES[1:]:
            assert (validar.rostro_normalizado(k, e) ^ base).sum() == 0, (k, e)


@pytest.mark.parametrize("clave", CLAVES)
def test_ningun_accesorio_invade_el_rostro(clave):
    pytest.importorskip("cv2")
    from pilo_studio.personajes import validar
    assert validar.invasion(clave) == 0


@pytest.mark.parametrize("clave", CLAVES[1:])
def test_fidelidad_minima_a_la_guia(clave):
    pytest.importorskip("cv2")
    from pilo_studio.personajes import validar
    r = validar.medir(clave)
    assert r["silueta"]["iou"] > 0.80, r["silueta"]
    assert max(abs(v) for v in r["alineacion_px"]) < 1.0
    assert r["capas"] and r["capas"][0]["iou_1px"] > 0.80


@pytest.mark.parametrize("clave", CLAVES)
def test_12_expresiones(clave):
    for e in fiel.EXPRESIONES:
        assert fiel.render_capas(clave, k=1, expresion=e).getbbox()


@pytest.mark.parametrize("clave", CLAVES)
def test_8_poses(clave):
    pytest.importorskip("cv2")
    from pilo_studio.personajes import articulado
    for p in articulado.POSES:
        img = np.asarray(articulado.render_pose(clave, p, k=1))
        assert img.max() > 200, p                     # hay trazo neón dibujado
