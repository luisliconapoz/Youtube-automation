# PILO STUDIO · Registro de progreso

Archivo para reanudar el trabajo sin repetir tareas. Se actualiza al cerrar cada fase.

## Estado por fase
| Fase | Estado | Notas |
|---|---|---|
| 0 · Auditoría | ✅ Hecha (2026-11-28) | Ver auditoría en la conversación; sin cambios en el repo desde entonces. |
| 1 · Personajes | 🔴 Hojas del rig **no aprobadas** (no fieles a las guías) · 🟡 **Prueba de fidelidad de BLUE pendiente de aprobación** | `pilo_studio/personajes/`, `personajes/personajes.yaml`, `personajes/hojas/`, `tests/test_rig.py` |
| 2 · Biblioteca visual | ⏳ **No iniciar** hasta la aprobación visual explícita del director | Partir de `pruebas/prueba-produccion-01/scripts/02_montaje.py` |
| 3 · Audio | ⏳ | Kokoro funciona técnicamente; **falta la escucha humana** de `pruebas/prueba-produccion-01/audio/narracion.wav` |
| 4 · Motor | ⏳ | |
| 5 · Integraciones | ⏳ | Notion conectado (lectura OK). OneDrive: falta `RCLONE_CONF_B64`. |
| 6–9 | ⏳ | |

## Decisiones del director
- **Repositorio oficial: `luisliconapoz/Youtube-automation`** (confirmado 2026-11-28). Trabajar solo aquí;
  no abrir ni modificar `pilo-studio-engine`. Rama de trabajo: `claude/dreamy-planck-cbs5du`.
- Regla de rostro único (13 personajes, una cara maestra) — implementada y validada.

## Fase 1 · nuevo procedimiento de fidelidad (2026-11-28, orden del director)
- El rig geométrico (`rig.py`) **no está aprobado**: simplificaba los personajes. No se borra (tests y API siguen),
  pero no es la referencia visual.
- Nuevo método en `pilo_studio/personajes/fiel.py`: cada forma se **mide sobre la guía original**
  (coordenadas en píxeles del recorte, `REFERENCIAS`) y se dibuja por código; el neón se calcula sobre la
  silueta unida, como en la guía. La cara maestra (`CARA`) está medida sobre Blue.
- `python -m pilo_studio.personajes.comparar blue` → `personajes/comparaciones/blue_comparacion.png`
  (guía | reconstrucción | superposición | mapa de diferencias + % de coincidencia del trazo).
- Estado: **solo BLUE**. Coincidencia del trazo: 92 % (2 px) / 81 % (1 px). Los otros 12 NO se tocan
  hasta que el director apruebe Blue; después, mismo procedimiento personaje a personaje.
- Siguiente tras aprobar Blue: aplicar la cara maestra medida y el método a los demás; después, convertir las
  medidas en un rig con poses/expresiones (las poses de cuerpo entero salen de la fila "Common poses" de la guía).

## Último estado verificado
- 2026-11-28 · prueba de fidelidad de Blue añadida · **71 tests pasan** (rig confirmado sin cambios).
- Hojas entregadas para revisión: `personajes/hojas/` (rostros, personajes, expresiones, poses, validacion_rostro.md).

## Decisiones técnicas tomadas
- Rig en **Python + Pillow** con supermuestreo ×3 (sin dependencias nuevas, el mismo motor que la prueba 01).
- Cara maestra única: `CABEZA`, `OJO`, `PUPILA`, `CEJA`, `BOCA` en `rig.py`. Las expresiones solo tocan cejas, mirada y boca.
- Ningún tocado baja de `Y_TOCADO` (por encima de las cejas); gafas y monóculo son anillos ceñidos que no tapan el ojo.
- Poses por cinemática inversa (posición de manos y pies) → poses nuevas en una línea.
- Test de consistencia con **color de sonda**: detecta incluso accesorios blancos sobre ojos blancos.
- **Rostro único (corrección del director, 2026-11-28):** `ZONA_CARA` protegida; sin bigote (Farmer),
  monóculo colgado del traje (Rich), gafas sobre la frente (White); los 13 parten de `neutral` y no
  tienen expresiones propias. `validacion.py` mide los rasgos sobre el render → `personajes/hojas/validacion_rostro.md`.
- Pillow 13: `ImageDraw.chord` falla con ciertas coordenadas → `Lienzo.cuerda` dibuja polígonos.

## Entorno (este contenedor)
- Instalado aquí: `requirements-dev.txt` (moviepy, anthropic, pytest…), kokoro-onnx, piper-tts, espeak-ng.
- Bloqueado por la red: Pollinations, Hugging Face, Bing (edge-tts), Whisper/Vosk.
- Modelo Kokoro: se descarga desde GitHub releases (`pruebas/prueba-produccion-01/scripts/run.sh`).

## Comandos
- Hojas de personajes: `python -m pilo_studio.personajes.hoja`
- Tests: `python -m pytest -q tests`

## Pendiente de decisión del director
1. Aprobación visual de la prueba de fidelidad de **BLUE** (`personajes/comparaciones/blue_comparacion.png`).
2. ~~Repositorio oficial~~ → resuelto: `Youtube-automation`.
3. Voz: escuchar Kokoro (`em_alex`).
4. OneDrive: autorizar rclone (`scripts/conectar_onedrive.sh` → secreto `RCLONE_CONF_B64`).
