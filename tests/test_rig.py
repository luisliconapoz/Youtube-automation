"""Consistencia del rig universal: la cara maestra es idéntica en los 13 personajes."""
import numpy as np
import pytest
import yaml

from pilo_studio.personajes import rig, validacion

ALTO = 330
PERSONAJES = list(rig.catalogo())


def test_hay_13_personajes_repartidos_en_tres_marcas():
    assert len(PERSONAJES) == 13
    assert [len(rig.personajes_de(m)) for m in ("fact-stick", "money-lab", "wild-money")] == [5, 4, 4]


def test_catalogo_coincide_con_proyectos_de_cada_marca():
    for marca in ("fact-stick", "money-lab", "wild-money"):
        cfg = yaml.safe_load((rig.RAIZ / "proyectos" / marca / "proyecto.yaml").read_text(encoding="utf-8"))
        nombres = {n.lower() for n in cfg["estilo"]["personajes"]}
        assert nombres == set(rig.personajes_de(marca)), marca


def test_solo_blue_tiene_mechon_y_reglas_de_identidad():
    cat = rig.catalogo()
    assert [k for k, p in cat.items() if "mechon" in p["accesorios"]] == ["blue"]
    # la cara solo admite cejas, mirada y boca: no hay parámetros de párpados ni pestañas
    for e in rig.EXPRESIONES.values():
        assert set(e) == {"ci", "cd", "mirada", "boca"}


@pytest.mark.parametrize("expresion", list(rig.EXPRESIONES))
def test_rasgos_faciales_identicos_en_todos(expresion):
    """Dentro de la máscara de ojos, pupilas, cejas y boca, los 13 renders son idénticos
    (ningún accesorio tapa ni deforma la cara)."""
    mascara = np.array(rig.mascara_cara(expresion, ALTO)) > 250
    ref = None
    for k in PERSONAJES:
        # color de sonda: así un accesorio blanco sobre un ojo blanco también se detecta
        img = np.array(rig.render(k, expresion=expresion, pose="neutral", alto=ALTO, brillo=False,
                                  color=(255, 0, 255)))[..., :3]
        rasgos = img[mascara].astype(int)
        if ref is None:
            ref = rasgos
        diff = np.abs(rasgos - ref).max(axis=1)
        assert (diff > 24).mean() < 0.002, f"{k} altera la cara en '{expresion}'"


@pytest.mark.parametrize("pose", list(rig.POSES))
def test_todas_las_poses_caben_en_el_lienzo(pose):
    for k in PERSONAJES:
        a = np.array(rig.render(k, pose=pose, alto=200, brillo=False).getchannel("A"))
        bordes = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
        assert bordes.max() == 0, f"{k} se sale del lienzo en '{pose}'"


def test_la_geometria_de_la_cabeza_no_depende_del_personaje():
    """El círculo de la cabeza tiene el mismo centro y radio en todos (mismo contorno)."""
    cajas = set()
    for k in PERSONAJES:
        a = np.array(rig.render(k, pose="neutral", alto=ALTO, brillo=False, accesorios=False).getchannel("A"))
        filas, cols = np.where(a > 0)
        cajas.add((int(filas.min()), int(cols[filas == filas.min()].mean())))
    assert len(cajas) == 1


def test_rostro_neutral_mismas_coordenadas_y_dimensiones():
    """Ojos, pupilas, cejas y boca medidos en el render: idénticos en los 13."""
    ref = validacion.medir("blue", "neutral")
    assert all(ref.values()), ref
    for k in PERSONAJES:
        assert validacion.medir(k, "neutral") == ref, k


@pytest.mark.parametrize("expresion", list(rig.EXPRESIONES))
def test_zona_facial_identica_y_sin_accesorios(expresion):
    """Toda la zona facial (no solo los rasgos) es idéntica píxel a píxel: ningún accesorio la invade."""
    ref = validacion.zona("blue", expresion)
    for k in PERSONAJES:
        assert np.abs(validacion.zona(k, expresion) - ref).max() <= 24, f"{k} invade la zona facial en '{expresion}'"


def test_sin_expresiones_propias_ni_accesorios_faciales():
    for k, p in rig.catalogo().items():
        assert "expresion" not in p, f"{k} no puede tener expresión propia"
        assert "bigote" not in p["accesorios"], k
