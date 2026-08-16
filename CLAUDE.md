# Clip House Factory — contexto persistente

Fábrica de contenido automatizada para 4 canales de YouTube Shorts, todos
administrados desde la misma cuenta de Google. El usuario aporta el material
crudo (clips) y el tema/guion de cada video; Claude produce el video
terminado, la miniatura, la metadata y lo sube programado a YouTube.

## Canales

| Canal | Handle | Formato | Carpeta |
|---|---|---|---|
| Clip House | @ClipHouseHD | "others vs this one" (versus) | `clip_house` |
| The Crazy Iguana | @TheCrazyIguana | "others vs this one" (versus) | `crazy_iguana` |
| POZMOT | @PozMot7 | "others vs this one" (versus) | `pozmot` |
| The Real Ranker | @TheRankerOficial | Top 5 (cuenta descendente 5→1, remate en #1) | `real_ranker` |

Clip House, Crazy Iguana y POZMOT comparten plantilla visual y estructura de
guion base (solo cambia el tema). The Real Ranker usa plantilla y estructura
de guion propias.

## División de responsabilidades

- **Usuario**: produce/consigue los clips crudos, los sube manualmente a
  `clips_raw/[canal]/[nombre_video]/`, y da el tema + guion o idea de cada
  video (en el chat o en `guion.txt` junto a los clips). El usuario NUNCA
  pide a Claude que genere o descargue material crudo.
- **Claude**: completa/redacta el guion final si no vino completo, edita el
  video con ffmpeg según la plantilla del canal, genera la miniatura con
  Python + Pillow, genera título/descripción/tags optimizados, sube y
  programa el video en el canal correcto vía YouTube Data API, y actualiza
  el estado en Notion.

## Flujo por video

1. Usuario sube clips a `clips_raw/[canal]/[nombre_video]/` (+ opcional
   `guion.txt`).
2. Usuario da tema + guion/idea.
3. Claude genera el guion final (`generar_guion.py`) siguiendo la estructura
   del canal (versus o top 5) si no se dio completo.
4. Claude edita el video (`editar_video.py`): corta/ordena clips, subtítulos
   quemados, zooms, transiciones, marca de agua/logo del canal — según
   `channels/[canal].json`.
5. Claude genera la miniatura (`generar_thumbnail.py`) con el estilo del
   canal.
6. Claude genera título/descripción/tags (`generar_metadata.py`) para el
   nicho de ese canal.
7. Claude sube el video (`subir_youtube.py`) al canal correcto con miniatura,
   metadata y fecha de publicación programada, usando las credenciales de
   ese canal.
8. Claude actualiza el estado en Notion (`notion_sync.py`):
   Pendiente → Guion listo → Editado → Publicado.

`scripts/pipeline.py` orquesta los 8 pasos de punta a punta para un video.

## Estructura del proyecto

```
clip-house-factory/
├── CLAUDE.md
├── channels/           → 1 JSON por canal: plantilla visual, formato de
│                          metadata, credenciales YouTube
├── clips_raw/[canal]/[video]/   → material crudo subido por el usuario
├── output/[canal]/     → videos terminados
├── thumbnails/[canal]/ → miniaturas generadas
├── assets/[canal]/     → logos, fuentes, overlays fijos del canal
├── credentials/        → client_secret / token por canal (NO se versiona)
└── scripts/
    ├── generar_guion.py
    ├── generar_metadata.py
    ├── editar_video.py
    ├── generar_thumbnail.py
    ├── subir_youtube.py
    ├── notion_sync.py
    └── pipeline.py
```

## Reglas

- Nunca commitear `clips_raw/`, `output/`, `thumbnails/` (pesado) ni
  `credentials/` (secretos) — ver `.gitignore`.
- Todo el texto orientado al usuario (guiones, metadata, mensajes) va en
  español salvo que el usuario pida lo contrario.
- Cada canal tiene sus propias credenciales OAuth de YouTube (mismo proyecto
  de Google Cloud, mismo usuario dueño, pero un `client_secret`/`token` por
  canal — YouTube Data API autentica por canal, no por cuenta de Google).
- Pendiente de configurar: acceso OAuth a los 4 canales de YouTube y
  especificación visual de cada plantilla (colores, fuente de subtítulos,
  posición de logo, timing de zoom/transición). Ver conversación con el
  usuario para el estado actual de estos dos puntos antes de asumir valores.
