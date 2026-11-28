# PILO STUDIO · Registro de progreso

Archivo para reanudar el trabajo sin repetir tareas. Se actualiza al cerrar cada fase.

## Estado por fase
| Fase | Estado | Notas |
|---|---|---|
| 0 · Auditoría | ✅ Hecha (2026-11-28) | Ver auditoría en la conversación; sin cambios en el repo desde entonces. |
| 1 · Personajes | 🟡 Corrección final aplicada (rostro único) · **pendiente de aprobación visual** | `pilo_studio/personajes/`, `personajes/personajes.yaml`, `personajes/hojas/`, `tests/test_rig.py` |
| 2 · Biblioteca visual | ⏳ Bloqueada por la aprobación de la fase 1 | Partir de `pruebas/prueba-produccion-01/scripts/02_montaje.py` |
| 3 · Audio | ⏳ | Kokoro funciona técnicamente; **falta la escucha humana** de `pruebas/prueba-produccion-01/audio/narracion.wav` |
| 4 · Motor | ⏳ | |
| 5 · Integraciones | ⏳ | Notion conectado (lectura OK). OneDrive: falta `RCLONE_CONF_B64`. |
| 6–9 | ⏳ | |

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
1. Aprobación visual de las hojas de personajes.
2. Repositorio oficial: `Youtube-automation` o `pilo-studio-engine`.
3. Voz: escuchar Kokoro (`em_alex`).
4. OneDrive: autorizar rclone (`scripts/conectar_onedrive.sh` → secreto `RCLONE_CONF_B64`).
