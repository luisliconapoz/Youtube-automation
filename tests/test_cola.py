"""Pruebas de la cola de imágenes en lote (sin red)."""

from __future__ import annotations

import threading
import time

from PIL import Image

from pilo_studio.visuals.cola import Cola, Limitador, Proveedor, Trabajo


def _trabajos(tmp_path, n):
    return [Trabajo(f"escena_{i:03d}", f"p{i}", 8, 8, tmp_path / f"{i}.png") for i in range(n)]


def _guardar(t, img):
    img.save(t.ruta)


def _ok(retardo=0.0, registro=None, nombre=""):
    def gen(t):
        time.sleep(retardo)
        if registro is not None:
            registro.append((nombre, t.clave))
        return Image.new("RGB", (8, 8))
    return gen


def test_reparte_entre_proveedores_en_paralelo(tmp_path):
    reg = []
    provs = [Proveedor("a", _ok(0.05, reg, "a"), concurrencia=3), Proveedor("b", _ok(0.05, reg, "b"), concurrencia=2)]
    t0 = time.monotonic()
    pendientes = Cola(_trabajos(tmp_path, 20), provs, _guardar).ejecutar()
    dur = time.monotonic() - t0
    assert pendientes == []
    assert {n for n, _ in reg} == {"a", "b"}           # ambos proveedores trabajaron
    assert len({c for _, c in reg}) == 20               # sin duplicados
    assert dur < 20 * 0.05 / 2                          # mucho más rápido que en serie (1 s)


def test_trabajo_fallido_pasa_a_otro_proveedor(tmp_path):
    def falla(t):
        raise RuntimeError("caído")
    reg = []
    provs = [Proveedor("malo", falla, reintentos=2, max_fallos_seguidos=100), Proveedor("bueno", _ok(0.01, reg, "bueno"))]
    assert Cola(_trabajos(tmp_path, 5), provs, _guardar).ejecutar() == []
    assert len(reg) == 5


def test_reintenta_errores_transitorios(tmp_path):
    intentos = {}
    cerrojo = threading.Lock()

    def inestable(t):
        with cerrojo:
            intentos[t.clave] = intentos.get(t.clave, 0) + 1
            if intentos[t.clave] < 2:
                raise RuntimeError("429")
        return Image.new("RGB", (8, 8))

    assert Cola(_trabajos(tmp_path, 3), [Proveedor("solo", inestable, reintentos=3)], _guardar).ejecutar() == []
    assert all(v == 2 for v in intentos.values())


def test_cortacircuitos_y_respaldo(tmp_path):
    llamadas = []

    def falla(t):
        llamadas.append(t.clave)
        raise RuntimeError("x")

    pendientes = Cola(_trabajos(tmp_path, 10), [Proveedor("roto", falla, reintentos=5, max_fallos_seguidos=3)],
                      _guardar).ejecutar()
    assert len(pendientes) == 10       # todo queda para el respaldo local
    assert len(llamadas) < 10          # se desactivó sin martillar el servicio


def test_limitador_espacia_peticiones():
    lim = Limitador(0.05)
    t0 = time.monotonic()
    for _ in range(4):
        lim.esperar()
    assert time.monotonic() - t0 >= 0.15
