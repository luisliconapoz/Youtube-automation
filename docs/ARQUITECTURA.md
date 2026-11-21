# PILO STUDIO — Arquitectura del programa

Este documento cubre los 4 bloques de la instrucción maestra: (1) arquitectura de "El Tubo", (2) Agente Guionista y su fórmula, (3) integración de visuales, voz, audio, subtítulos y render, y (4) el plan de implementación.

---

## 1. Arquitectura: "El Tubo"

```
                       ┌──────────────── brands/*.json (biblias de marca, 10 slots) ────────────────┐
                       │                 pilo_studio/core/style.py (identidad visual compartida)    │
                       ▼                                                                            ▼
 [AGENTE DIRECTOR] ── pilo_studio/pipeline/orchestrator.py ─────────────────────────────────────────────────────
     │
     ├─ 1. PLAN           Agente Guionista → plan.json → 00_idea.json, 01_structure.json, 02_script.md
     ├─ 2. QA_PLAN        GATE 1 (validator.py): reglas de marca/formato/actuación + anti-repetición  ◄── $0 gastado aún
     ├─ 3. IMAGE_PROMPTS  03_prompts/001.json … + prompts.md (diseño canónico inyectado, sin texto)
     ├─ 4. IMAGES         04_images/001.png … (Open Generative AI → Google Flow → Higgsfield) + referencias
     ├─ 5. QA_IMAGES      GATE 2: existen todas, proporción, resolución, fondo negro
     ├─ 6. VOICE          05_audio/voice_001.wav … (Kokoro → VoiceStudio → ElevenLabs)
     ├─ 7. SUBTITLES      06_subtitles/subs.srt + timeline.json (re-sincronizado con la duración real de la voz)
     ├─ 8. AUDIO_MIX      voz + música sin copyright + SFX, ducking, -14 LUFS (config/audio.json)
     ├─ 9. RENDER         Remotion (o Adobe) → 07_render/final.mp4
     ├─10. QA_FINAL       GATE 3: duración, resolución, pista de audio
     └─11. PUBLISH_DRAFT  08_publish/metadata_draft.md + copia a output/<MARCA>/LISTOS/  ── PUBLICACIÓN MANUAL
```

### Principios de diseño
| Principio | Cómo se implementa |
|---|---|
| **Modular 10 canales, arranque con 3** | `brands/channels.json` tiene 10 slots; solo `active: true` producen. Activar un canal = crear su `brands/<ID>.json` y poner `active: true`. Cero cambios de código. |
| **Personajes jamás se mezclan** | IDs únicos por marca, comprobados por `check_character_exclusivity` y por el validador (`FOREIGN_CHARACTER`). |
| **Reanudable** | `state.json` por video. Si se corta, `pilo run <carpeta>` sigue desde la última etapa; las imágenes/voces ya hechas no se regeneran ni se pagan dos veces. |
| **QA antes de gastar** | El plan se valida ANTES de llamar a cualquier generador. Un plan malo cuesta $0. |
| **Reintentos inteligentes** | Errores transitorios (red, GPU, timeout): hasta 3 intentos con backoff 5/20/60 s. Errores de QA o presupuesto: **no** se reintentan (reintentar no cambia nada y gasta). |
| **Control de costos** | `costs.json` por video; tope por video (`LONG $3`, `SHORT $0.75`) y por día en `config/pipeline.json`. Se estima antes de cada etapa de pago; si no alcanza, se detiene. |
| **Proveedores intercambiables** | `providers/base.py`: `LLMProvider`, `ImageProvider`, `TTSProvider`, `Renderer`. Cambiar Flow por Higgsfield = cambiar una clase, no el Tubo. |
| **BLOCKED ≠ FAILED** | Si falta un proveedor o insumo (p. ej. imágenes en modo manual), la etapa queda `blocked` con instrucciones, sin error. |
| **Publicación siempre manual** | El Tubo termina en un borrador + checklist humano. Nunca sube nada. |

### Medición de tiempos
Cada etapa guarda `seconds` en `state.json` y `pipeline.log`. En la fase piloto (3 canales) se mide el tiempo por etapa y por video para dimensionar cuántos videos/día caben antes de activar los 10 canales.

---

## 2. Agente Guionista y fórmula

- **System prompt:** `pilo_studio/agents/scriptwriter_system_prompt.md`, renderizado por marca y formato con `python -m pilo_studio system-prompt --brand X --format LONG|SHORT [--topic "..."]`.
- Inyecta automáticamente: biblia de la marca, personajes exclusivos con color/accesorios/rol, expresiones y poses permitidas, ideas ya producidas (anti-repetición), ritmo (ppm) y duración por formato, y el esquema JSON de salida.
- **Esquema de salida:** `schemas/video_plan.schema.json` (sirve como *structured output* para Claude/ChatGPT/Gemini).
- **Orden de entrega:** nicho → formato y tema → título → estructura de la idea → estructura del guion → guion completo → escena por escena (narración, personajes, expresión, pose, acción, escenario, objetos, cámara, movimiento, transición, texto superpuesto, énfasis, SFX).

### Fórmula de retención (resumen; detalle en el system prompt)
**LARGO (8–10 min):** Hook 0–30 s (contradicción → apuesta → promesa + bucle abierto) · Contexto rápido · 4–7 capítulos (mini-hook → ejemplo → payoff → puente) · re-hook cada 60–90 s · CTA *después* del primer gran payoff (35–45 %) · giro en 55–65 % · payoff que cierra el bucle del hook · outro hacia el siguiente video. Imagen nueva cada 3–8 s.

**SHORT (52–59 s):** gancho desde la primera palabra (≤1,5 s) · apuesta · 2–3 golpes con mini-sorpresa · giro · **loop**: la última frase conecta con la primera para que la repetición sea continua. Imagen nueva cada 1,5–3,5 s.

**Psicología aplicada:** bucles abiertos (Zeigarnik), brecha de curiosidad, escalada de apuestas, interrupción de patrón (personaje/plano/expresión/SFX), especificidad, identificación (el personaje "persona común" hace las preguntas del espectador), contraste rico/pobre, recompensa variable.

> La fórmula es la hipótesis inicial basada en prácticas establecidas de retención. Se debe calibrar con datos reales de YouTube Studio (curva de retención, CTR, % que pasa del segundo 30) durante la fase piloto: los números de `core/formats.py` y del system prompt son los parámetros a ajustar.

### Dirección de actuación (Bloque 2) — reglas que el validador hace cumplir
- Solo personajes de la marca; máx. 3 por escena; una idea visual principal; máx. 3 objetos clave.
- Solo las 12 expresiones y 8 poses oficiales.
- **Un personaje no repite pose ni expresión en escenas seguidas.**
- Cero texto/números/comillas/3D/fotorealismo en campos visuales; fondo siempre negro.
- FACT STICK: BLUE no puede estar solo en >60 % de las escenas (balance de colores).
- La narración debe caber en la duración de la escena según el ritmo del formato.

---

## 3. Integraciones (visual, voz, audio, subtítulos, render, derivados)

### 3.1 Imágenes — elegir la herramienta más eficiente, no todas
| Prioridad | Herramienta | Cuándo |
|---|---|---|
| 1 | **Open Generative AI** (local, GPU) | Por defecto: costo $0, sin límite. Usar con imágenes de referencia de cada personaje (`references/<MARCA>/<PERSONAJE>/`). |
| 2 | **Google Flow** | Si la GPU local no está disponible o la calidad de continuidad no alcanza. |
| 3 | **Higgsfield** | Solo planos especiales (clips animados, movimientos de cámara) o cuando 1 y 2 fallan. |

El constructor de prompts (`prompts/image_prompt.py`) inyecta en cada prompt: estilo PILO, descripción canónica del personaje (sin nombres propios ni códigos hex, para que el modelo no los dibuje como texto), expresión, pose, fondo negro, composición 16:9 o 9:16 dejando espacio para subtítulos, y un negativo anti-texto/anti-3D. **Modo manual disponible hoy:** `03_prompts/prompts.md` listo para copiar/pegar; guarda los resultados como `04_images/001.png…` y vuelve a correr `pilo run`.

### 3.2 Voz
Kokoro (local, gratis) por defecto → VoiceStudio → ElevenLabs (premium, solo si hace falta). **Una voz fija por marca** (`voice` en la biblia) para consistencia. Se sintetiza por escena (`voice_001.wav…`), lo que permite: regenerar solo la frase mala, sincronización exacta imagen-voz y quitar silencios por clip.

### 3.3 Música, SFX y mezcla (Bloque 3)
Reglas numéricas en `config/audio.json`: master a -14 LUFS, música 18–22 dB por debajo de la voz con ducking, SFX espaciados (≥6 s en LONG, ≥2,5 s en SHORT), eliminación de silencios (umbral -40 dB, >350 ms), licencias registradas en `05_audio/LICENSES.txt`. El módulo **Music & SFX Curator** (Fase 3) elegirá pistas de una biblioteca local etiquetada por `music_mood` y BPM, solo con licencias aptas para monetización (CC0, YouTube Audio Library, royalty-free con monetización permitida).

### 3.4 Subtítulos y textos en pantalla
Generados desde la narración y los tiempos reales de voz. LONG: abajo, 2 líneas máx. SHORT: 1–3 palabras, palabra por palabra, la palabra clave en el color del narrador. Los `on_screen_text` (máx. 4 palabras, cifras) se superponen en edición — nunca dentro de la imagen.

### 3.5 Render
**Remotion** (por defecto): lee `timeline.json` (imagen, voz, inicio, duración, movimiento, transición, SFX, texto superpuesto) y renderiza 1920×1080 o 1080×1920 a 30 fps. Animación: zoom lento / paneo / pop-in sobre cada imagen; cortes secos por defecto, whoosh en cambios de idea, fade solo entre capítulos. Adobe queda como alternativa vía el mismo `timeline.json`.

### 3.6 Derivados Largo ↔ Short (Bloque 5)
- Cada plan LONG trae 2–4 `derivatives`: escenas fuente, hook nuevo autónomo, línea de loop y escenas nuevas necesarias.
- El derivador (Fase 5) re-encuadra las imágenes 16:9 a 9:16 (o regenera solo las que no encajan), reutiliza la voz donde sirve y genera un plan SHORT que pasa por el mismo QA.
- Un mismo MP4 SHORT sirve para YouTube Shorts, TikTok e Instagram Reels (por eso el objetivo es <60 s).
- Publicación y metadatos: siempre manuales.

### Nota sobre monetización
YouTube no monetiza contenido "inauténtico" producido en masa y repetitivo. Lo que protege al canal: valor educativo real, guiones distintos (anti-repetición), datos verificados, revisión humana de cada video, títulos/miniaturas personalizados a mano, y publicación manual. El checklist de `metadata_draft.md` existe para eso. Si el video usa contenido sintético realista hay que declararlo; los stickmen 2D normalmente no lo requieren, pero la casilla está en el checklist.

---

## 4. Plan de implementación (orden de construcción)

| Fase | Entregable | Estado |
|---|---|---|
| **0. Componente base** | Biblias de 3 marcas + registro de 10 slots, estilo compartido, formatos, esquema JSON, validador QA, constructor de prompts numerados, registro anti-repetición, proyecto/carpetas, estado reanudable, costos, reintentos, orquestador, CLI, tests | ✅ **Hecho** |
| **1. Agente Guionista conectado** | `providers/llm_claude.py` (API de Claude con structured output) + reparación automática: si QA falla, se reenvía el reporte al agente (máx. 2 rondas) | Siguiente |
| **2. Imágenes** | `providers/image_open_generative.py` (GPU local) con referencias de personaje; luego Flow/Higgsfield como respaldo. Regenerar solo las que fallen QA | |
| **3. Voz + audio** | `providers/tts_kokoro.py`, quitar silencios, Music & SFX Curator, mezcla con ffmpeg según `config/audio.json` | |
| **4. Render** | Proyecto Remotion (`render/`) que consume `timeline.json`; QA final | |
| **5. Derivados** | Largo → Shorts automáticos | |
| **6. Lotes y piloto** | `pilo batch --brands all --long 1 --short 2` nocturno; medir tiempos y costos 2 semanas con 3 canales | |
| **7. Escalar a 10** | Crear biblias de los slots 4–10 y activarlos según capacidad medida | |
