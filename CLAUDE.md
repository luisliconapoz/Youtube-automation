# PILO STUDIO — Memoria del proyecto (leer esto, no el historial)

Usuario: habla español, no es técnico. Respuestas cortas y simples (skill concise-responses). Ahorrar tokens.

## Qué es
Fábrica de videos faceless para YouTube (+Shorts/TikTok/IG). Stickman 2D neón, fondo negro, sin texto en imágenes.
Canales activos: FACT_STICK, WILD_MONEY, MONEY_HOUSE (guía visual "MONEY LAB"). Diseño para 10 canales.
Publicación SIEMPRE manual (anti-desmonetización). Un video por canal por ronda (round-robin).
Largos 7–15 min (prom. 8–10), ~1 imagen cada 5 s (100–300 imágenes). Shorts 52–59 s.

## Hecho (rama claude/hola-bro-6vwaq1)
- Biblias de marca `brands/*.json` según guías visuales; referencias `references/<MARCA>/<PJ>/ref_01.png`.
- Validador QA, prompts de imagen numerados, registro anti-repetición, orquestador reanudable (reintentos, costos).
- Agente Guionista: system prompt + API Claude (urllib) + bucle de corrección QA (`pilo new --brand X --format Y`).
- `pilo batch --count N` y workflow `.github/workflows/pilo-studio.yml` (cron diario + manual, rclone a Drive).
- Docs: `docs/ARQUITECTURA.md`, `docs/PROMPTS_REFERENCIAS_CHATGPT.md`. Tests: `python -m unittest discover -s tests`.

## Decisiones
- Edición: Remotion con timeline generado (el usuario no escribe código; evitar look genérico).
- Voz: Kokoro (gratis, CPU). ElevenLabs solo si hace falta.
- Imágenes: no hay API gratis real. Opciones: GPU alquilada por lote o pagar al tener ingresos. Pendiente decidir.
- Carpeta final: Google Drive (u OneDrive) vía rclone.

## Tubo completo funcionando (prueba E2E OK: Short 57.8 s, $0, ~2.5 min)
- Voz: `providers/tts_kokoro.py` (kokoro-onnx, CPU, gratis; auto-acelera si se pasa del formato, máx. x1.2).
- Mezcla: `media/audio_mix.py` (voz+música `assets/music/`+SFX `assets/sfx/`, ducking, -14 LUFS).
- Montaje: `providers/render_ffmpeg.py` (zoom/paneo, subtítulos 3 palabras en Shorts). Remotion = mejora futura.
- Imágenes de PRUEBA: `providers/image_placeholder.py` (`--test-images`, NO publicar).
- Comandos: `pilo new --plan X --test-images`, `pilo batch --count N --test-images`.

## Piloto con IA real (OK)
- Imágenes: ElevenLabs gemini-3.1-flash-image con referencias por URL raw de GitHub (repo público). ~609-812 créditos/imagen; plan gratis = 3 imágenes/día. Usuario quiere imágenes con Gemini/otra IA, ElevenLabs solo audio.
- Voz ElevenLabs: voz Daniel (onwK4e9ZLuTAKqWW03F9), eleven_flash_v2_5, ~30 créditos/frase; gratis 10k/mes.
- Entorno de red 'Youtube-automation' permite elevenlabsusercontent.com.
- Las imágenes IA a veces copian el marco de la hoja de referencia: recortar o poner margen negro.

- Gemini: `providers/image_gemini.py` listo; activar con PILO_IMAGES=gemini + clave (secreto de red del entorno para generativelanguage.googleapis.com, header x-goog-api-key). Usuario rechazó el formulario la 1.ª vez: no volver a pedir salvo que lo pida.

## Falta
Imágenes reales (proveedor), clave Claude, música/SFX con licencia, Google Drive (rclone), Notion.

## Pendiente del usuario
Clave API Claude ($5, sin auto-reload) vía formulario seguro; Drive; Notion; decisión imágenes.

## Mapa de archivos (leer solo lo necesario)
| Necesito… | Archivo |
|---|---|
| Personajes, colores, roles | `brands/<MARCA>.json`, `brands/channels.json` (10 slots) |
| Reglas visuales compartidas | `pilo_studio/core/style.py` |
| Duraciones, ritmo, LONG/SHORT | `pilo_studio/core/formats.py` |
| Reglas de QA del plan | `pilo_studio/qa/validator.py` |
| QA imágenes / MP4 | `pilo_studio/qa/image_checks.py` |
| Prompt del guionista | `pilo_studio/agents/scriptwriter_system_prompt.md` (+ `scriptwriter.py`) |
| Bucle de corrección del plan | `pilo_studio/agents/generate.py` |
| Prompts de imagen | `pilo_studio/prompts/image_prompt.py` |
| Etapas del Tubo, reintentos, costos | `pilo_studio/pipeline/orchestrator.py`, `state.py`, `project.py` |
| Conectar herramientas (imagen/voz/render) | `pilo_studio/providers/` (base, llm_claude, tts_kokoro, render_ffmpeg, image_placeholder) |
| Mezcla de audio | `pilo_studio/media/audio_mix.py` |
| Anti-repetición de ideas | `pilo_studio/ideas/registry.py` |
| Comandos | `pilo_studio/cli.py` (`python -m pilo_studio …`) |
| Config | `config/pipeline.json` (presupuesto, reintentos, LLM), `config/audio.json` (mezcla) |
| Esquema del plan | `schemas/video_plan.schema.json`; ejemplo `examples/` |
| Workflow nube | `.github/workflows/pilo-studio.yml` |
