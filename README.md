# PILO STUDIO — Youtube-automation

Fábrica de videos *faceless* (stickman 2D neón sobre fondo negro) para YouTube, Shorts, TikTok e Instagram.
Arquitectura modular de **10 canales**, en piloto con **3**: `FACT_STICK`, `WILD_MONEY`, `MONEY_HOUSE`.

**El Tubo:** Idea → Estructura → Guion → Prompts numerados → Imágenes numeradas → Voz → Subtítulos → Mezcla → Render MP4 → Borrador de publicación (**publicación manual**).

Documentación completa: [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md).

## Requisitos
Python 3.11+. Sin dependencias obligatorias (Pillow opcional para el QA de fondo negro; ffmpeg/ffprobe para QA final).

## Uso rápido
```bash
python -m pilo_studio channels                                   # 10 slots, activos y preguntas abiertas
python -m pilo_studio system-prompt --brand FACT_STICK --format SHORT --out prompt.md
#   → pega prompt.md en Claude/ChatGPT/Gemini, guarda la respuesta JSON como plan.json
python -m pilo_studio validate plan.json                         # QA gratis antes de gastar
python -m pilo_studio new --plan plan.json                       # crea el proyecto y corre el Tubo
python -m pilo_studio run output/FACT_STICK/proyectos/<carpeta>  # reanudar tras añadir imágenes, etc.
python -m pilo_studio status output/FACT_STICK/proyectos/<carpeta>
python -m pilo_studio ideas --brand FACT_STICK                   # ideas ya producidas
```
Ejemplo listo: `python -m pilo_studio new --plan examples/FACT_STICK_SHORT_bank_money.json`

## Estructura
```
brands/            biblias de marca (JSON editable) + channels.json (10 slots)
config/            pipeline.json (reintentos, presupuestos, proveedores), audio.json (mezcla)
schemas/           esquema JSON del plan de video (salida del Agente Guionista)
references/        imágenes de referencia: references/<MARCA>/<PERSONAJE>/*.png
pilo_studio/
  core/            estilo compartido, formatos, carga de marcas
  agents/          system prompt del Agente Guionista
  qa/              validador del plan + chequeos de imagen/audio/video
  prompts/         constructor de prompts de imagen numerados
  ideas/           registro anti-repetición
  pipeline/        proyecto, estado reanudable, costos, orquestador
  providers/       interfaces para Open Generative AI, Flow, Higgsfield, Kokoro, ElevenLabs, Remotion…
output/            (ignorado por git) proyectos por marca y carpeta LISTOS/
tests/             python -m unittest discover -s tests
```
