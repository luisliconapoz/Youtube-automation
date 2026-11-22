"""Cola de trabajo compartida para generar imágenes en lote.

Todas las imágenes del video (escenas + miniatura) entran en una cola única.
Cada proveedor en la nube (Pollinations, Hugging Face…) lanza sus propios
trabajadores, que sacan trabajos de la misma cola en paralelo:

    cola ──┬─► pollinations  ×N hilos  (limitador de ritmo propio)
           └─► huggingface   ×M hilos  (limitador de ritmo propio)

* El rendimiento total es la suma de todos los proveedores.
* Cada proveedor respeta su ritmo máximo, así no se satura ni se bloquea.
* Si un proveedor falla un trabajo, este vuelve a la cola (al final) para
  reintentarse más tarde o que lo tome otro proveedor. Si fallan todos, queda para el respaldo local.
* Un proveedor que acumula fallos seguidos se desactiva (cortacircuitos).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from PIL import Image

from pilo_studio.utils import log


@dataclass
class Trabajo:
    clave: str                 # "escena_003", "miniatura"…
    prompt: str
    ancho: int
    alto: int
    ruta: Path
    intentados: set[str] = field(default_factory=set)   # proveedores agotados para este trabajo
    fallos: dict[str, int] = field(default_factory=dict)
    origen: str | None = None


class Limitador:
    """Garantiza un intervalo mínimo entre peticiones (seguro entre hilos)."""

    def __init__(self, intervalo: float):
        self.intervalo = max(0.0, intervalo)
        self._cerrojo = threading.Lock()
        self._siguiente = 0.0

    def esperar(self) -> None:
        with self._cerrojo:
            ahora = time.monotonic()
            turno = max(ahora, self._siguiente)
            self._siguiente = turno + self.intervalo
        if turno > ahora:
            time.sleep(turno - ahora)

    def penalizar(self, segundos: float) -> None:
        """Retrasa el siguiente turno (p. ej. tras un HTTP 429)."""
        with self._cerrojo:
            self._siguiente = max(self._siguiente, time.monotonic() + segundos)


@dataclass
class Proveedor:
    nombre: str
    generar: Callable[[Trabajo], Image.Image | None]
    concurrencia: int = 1
    intervalo: float = 0.0
    reintentos: int = 3            # intentos por trabajo antes de cederlo a otro proveedor
    max_fallos_seguidos: int = 8   # cortacircuitos

    def __post_init__(self):
        self.limitador = Limitador(self.intervalo)
        self.fallos_seguidos = 0


class Cola:
    def __init__(self, trabajos: list[Trabajo], proveedores: list[Proveedor], guardar: Callable[[Trabajo, Image.Image], None]):
        self.pendientes = list(trabajos)
        self.total = len(trabajos)
        self.hechos = 0
        self.fallidos: list[Trabajo] = []
        self.en_curso = 0
        self.activos = {p.nombre for p in proveedores}
        self.proveedores = proveedores
        self.guardar = guardar
        self.cv = threading.Condition()

    # ---------------------------------------------------------------- scheduling
    def _tomar(self, prov: str) -> Trabajo | None:
        with self.cv:
            while prov in self.activos:
                for i, t in enumerate(self.pendientes):
                    if prov not in t.intentados:
                        self.en_curso += 1
                        return self.pendientes.pop(i)
                if self.en_curso == 0:
                    return None  # nada que este proveedor pueda hacer, y nada cambiará
                self.cv.wait()
            return None

    def _reclasificar(self) -> None:
        """Mueve a 'fallidos' los trabajos que ya probaron todos los proveedores activos."""
        quedan = []
        for t in self.pendientes:
            (self.fallidos if self.activos <= t.intentados else quedan).append(t)
        self.pendientes = quedan

    def _terminar(self, t: Trabajo, prov: Proveedor, ok: bool) -> None:
        with self.cv:
            self.en_curso -= 1
            if ok:
                self.hechos += 1
                prov.fallos_seguidos = 0
                log.info("  🖼  %d/%d %s vía %s", self.hechos, self.total, t.clave, prov.nombre)
            else:
                t.fallos[prov.nombre] = t.fallos.get(prov.nombre, 0) + 1
                if t.fallos[prov.nombre] >= prov.reintentos:
                    t.intentados.add(prov.nombre)
                prov.fallos_seguidos += 1
                self.pendientes.append(t)
                if prov.fallos_seguidos >= prov.max_fallos_seguidos and prov.nombre in self.activos:
                    log.warning("  ⛔ %s desactivado tras %d fallos seguidos", prov.nombre, prov.fallos_seguidos)
                    self.activos.discard(prov.nombre)
                self._reclasificar()
            self.cv.notify_all()

    # ---------------------------------------------------------------- ejecución
    def _trabajador(self, prov: Proveedor) -> None:
        while (t := self._tomar(prov.nombre)) is not None:
            img = None
            try:
                prov.limitador.esperar()
                img = prov.generar(t)
                if img is not None:
                    self.guardar(t, img)
                    t.origen = prov.nombre
            except Exception as e:  # un fallo nunca debe tumbar al hilo
                log.warning("  %s falló en %s: %s", prov.nombre, t.clave, e)
                img = None
            self._terminar(t, prov, img is not None)

    def ejecutar(self) -> list[Trabajo]:
        """Procesa la cola. Devuelve los trabajos que ningún proveedor pudo hacer."""
        if not self.proveedores:
            return list(self.pendientes)
        hilos = [threading.Thread(target=self._trabajador, args=(p,), daemon=True, name=f"{p.nombre}-{i}")
                 for p in self.proveedores for i in range(max(1, p.concurrencia))]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        with self.cv:
            self._reclasificar()
            return self.fallidos + self.pendientes
