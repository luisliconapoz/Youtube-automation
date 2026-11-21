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

## Siguiente (plan de 1 h aprobado)
1. Proveedor voz Kokoro + quitar silencios. 2. Mezcla audio ffmpeg (config/audio.json).
3. Remotion render desde timeline.json. 4. Imágenes de PRUEBA (placeholder, no publicar).
5. Prueba completa del Short de ejemplo hasta final.mp4. 6. Actualizar workflow.

## Pendiente del usuario
Clave API Claude ($5, sin auto-reload) vía formulario seguro; Drive; Notion; decisión imágenes.
