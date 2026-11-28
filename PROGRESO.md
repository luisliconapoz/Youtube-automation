# PILO STUDIO · Registro de progreso

Archivo para reanudar el trabajo sin repetir tareas. Se actualiza al cerrar cada fase.

## Estado por fase
| Fase | Estado | Notas |
|---|---|---|
| 0 · Auditoría | ✅ Hecha (2026-11-28) | Ver auditoría en la conversación; sin cambios en el repo desde entonces. |
| 1 · Personajes | 🟡 **13 personajes fieles entregados en lote** (comparaciones, 12 expresiones, 8 poses, tests) · pendiente de aprobación | `pilo_studio/personajes/`, `personajes/personajes.yaml`, `personajes/hojas/`, `tests/test_rig.py` |
| 2 · Biblioteca visual | ⏳ **No iniciar** hasta la aprobación visual explícita del director | Partir de `pruebas/prueba-produccion-01/scripts/02_montaje.py` |
| 3 · Audio | ⏳ | Kokoro funciona técnicamente; **falta la escucha humana** de `pruebas/prueba-produccion-01/audio/narracion.wav` |
| 4 · Motor | ⏳ | |
| 5 · Integraciones | ⏳ | Notion conectado (lectura OK). OneDrive: falta `RCLONE_CONF_B64`. |
| 6–9 | ⏳ | |

## Decisiones del director
- **Repositorio oficial: `luisliconapoz/Youtube-automation`** (confirmado 2026-11-28). Trabajar solo aquí;
  no abrir ni modificar `pilo-studio-engine`. Rama de trabajo: `claude/dreamy-planck-cbs5du`.
- Regla de rostro único (13 personajes, una cara maestra) — implementada y validada.

## Fase 1 · lote de 13 personajes fieles (2026-11-28, orden del director: una sola entrega)
- **Herramientas** (`pilo_studio/personajes/`):
  - `lote.py` — traza los 12 restantes desde sus guías: capas de color por k-means en Lab (semilla fija),
    halo descartado y regenerado, interior negro por cierre (unión de radios + crecimiento geodésico),
    retirada de la cara pintada y colocación del ROSTRO MAESTRO (Blue) por semejanza; accesorios que
    invadan el rostro se recortan; bigote de Farmer escalado (sin deformar) al hueco ojos–boca.
    Zonas de cada personaje en `PERSONAJES`; opciones por personaje en `OPCIONES`.
  - `fiel.py` — `render_capas` dibuja cualquiera de los 13 (Blue idéntico píxel a píxel a la ronda 2),
    `dibujar_rostro` con 12 expresiones sobre las medidas del rostro maestro.
  - `articulado.py` — piezas (cuerpo / brazos de la guía / pivotes), 8 poses: brazos redibujados con
    ancho, trazo, color y halo medidos en cada personaje; manos de la biblioteca trazada (abierta y puño
    de Blue, índice de Green). `render_pose(clave, pose, expresion)`.
  - `validar.py` — mediciones reales por personaje → `personajes/comparaciones/` (13 hojas de 4 paneles,
    `validacion.json`, `INFORME_VALIDACION.md`).
  - `hojas_fieles.py` — `personajes/hojas_fieles/` (personajes, 12 expresiones, 8 poses, rostros).
- **Resultado**: silueta IoU 0,84–0,99; rostro maestro idéntico en los 13 y las 12 expresiones (0 px);
  invasión del rostro 0 px en los 13; 140 tests pasan.
- **Limitaciones conocidas (pendientes de decisión o mejora)**:
  - En las 8 poses las manos quedan libres: los objetos sostenidos (horquilla, calculadora, llave, casa,
    tableta) solo aparecen en la pose de la guía.
  - Rich y Purple: la franja del torso tapada por los brazos cruzados en la guía no es visible; en otras
    poses se rellena prolongando la fila de encima (inferencia).
  - Cyan y Gray tienen pelo en sus guías y se conserva (la regla antigua «solo Blue tiene mechón» choca
    con «conservar los diseños originales»): decisión del director.
  - Halo con error de 8–11 niveles en Cyan, Lime y White; silueta de Farmer (0,84) y Lime (0,90) más
    baja por zonas ambiguas (degradado del sombrero, hueco oscuro junto al brazo).
- El rig geométrico antiguo (`rig.py`, `hoja.py`, `personajes/hojas/`) no está aprobado; se conserva sin uso.

## Último estado verificado
- 2026-11-28 · lote de 13 personajes fieles · **140 tests pasan**.
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
1. Aprobación visual del lote (`personajes/hojas_fieles/`, `personajes/comparaciones/`).
2. ~~Repositorio oficial~~ → resuelto: `Youtube-automation`.
3. Voz: escuchar Kokoro (`em_alex`).
4. OneDrive: autorizar rclone (`scripts/conectar_onedrive.sh` → secreto `RCLONE_CONF_B64`).
