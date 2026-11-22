# 🎬 Pilo Studio

Fábrica digital **100 % automatizada** de videos — largos (7–10 min, 16:9) y Shorts/Reels (9:16) —
con **presupuesto cero**: solo herramientas open-source y servicios gratuitos.

**Tú aportas:** la idea (`idea.md`) y las referencias visuales (`referencias/` + `proyecto.yaml`).
**Pilo Studio hace el resto:** guion → voz → imágenes → montaje con subtítulos → OneDrive.

```
idea.md + referencias/
        │
 [1] DIRECCIÓN Y GUION   Ollama (LLM local) · guion manual · plantilla offline
        │                  → escenas con narración exacta + prompt visual
 [2] AUDIO               edge-tts (voces neurales gratis) + marcas por palabra
        │
 [3] IMÁGENES            Pollinations (Flux, sin clave) · SD local · referencias · placeholder
        │                  + Biblia de estilo: prefijo, personajes, paleta, semilla fija
 [4] ENSAMBLAJE          MoviePy (Ken Burns + sincronía) · FFmpeg/libass (subtítulos + música)
        │
 [5] ALMACENAMIENTO      ${OneDrive}/PiloStudio/Videos/<fecha>_<titulo>_<formato>/
```

## Estructura

```
pilo_studio/
├── cli.py                 # python -m pilo_studio …
├── pipeline.py            # orquestador de las 5 fases (con caché reanudable)
├── config.py              # settings.yaml global + overrides por proyecto
├── models.py              # Guion / Escena / Palabra
├── proyecto.py            # carga idea, estilo y referencias
├── director/guionista.py  # FASE 1
├── audio/locutor.py       # FASE 2
├── visuals/estilo.py      # biblia de estilo (consistencia)
├── visuals/generador.py   # FASE 3
├── assembly/subtitulos.py # SRT + ASS a partir de marcas de edge-tts
├── assembly/montador.py   # FASE 4
└── storage/exportador.py  # FASE 5
config/settings.yaml       # toda la configuración
proyectos/_plantilla/      # plantilla para nuevos proyectos
proyectos/ejemplo-pilo-espacio/
assets/music/              # música libre de derechos (opcional)
tests/                     # pruebas offline (TTS simulado)
```

## Instalación

Necesitas Python 3.10 o superior y [FFmpeg](https://ffmpeg.org) en el PATH
(Windows: `winget install ffmpeg`).

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**Guiones con IA (recomendado, gratis y local):** instala [Ollama](https://ollama.com) y ejecuta
`ollama pull llama3.1:8b`. Sin Ollama, el sistema usa el modo *plantilla*: cada párrafo de `idea.md`
se convierte en una escena.

## Uso

```bash
# 1. Crear un proyecto
python -m pilo_studio nuevo "Misterios del océano" --idea "Las criaturas más extrañas del fondo marino"

# 2. (Opcional) poner imágenes en proyectos/misterios-del-oceano/referencias/
#    y describir personajes/escenarios en proyecto.yaml

# 3. Producir
python -m pilo_studio producir proyectos/misterios-del-oceano --formato ambos

# Revisar el guion antes de renderizar:
python -m pilo_studio producir proyectos/misterios-del-oceano --hasta guion
#   (edita build/largo/guion.json y vuelve a ejecutar sin --hasta)

# Voces disponibles
python -m pilo_studio voces --idioma es
```

Puedes probar el ejemplo incluido:
`python -m pilo_studio producir proyectos/ejemplo-pilo-espacio --formato short`

## Consistencia visual

| Técnica | Dónde |
|---|---|
| Prefijo de estilo idéntico en todos los prompts | `estilo.descripcion` |
| Descripción canónica de personaje inyectada cuando aparece | `estilo.personajes` |
| Escenarios recurrentes | `estilo.escenarios` |
| Paleta de color (manual o **extraída de tus referencias**) | `estilo.paleta` / `referencias/` |
| Semilla fija por proyecto | automática |
| Imagen de referencia por nombre de archivo (`Pilo.png`) | proveedor `referencias` |

## Salida (OneDrive)

Por defecto: `${OneDrive}/PiloStudio/Videos` (OneDrive define `%OneDrive%` en Windows).
Para usar otra carpeta, cambia `salida.carpeta` o define `PILO_OUTPUT_DIR`. Si la carpeta no
existe, se usa `./salida`. Cada video incluye `.mp4`, `.srt`, `guion.json` y `publicacion.txt`
(título, descripción y hashtags para la subida).

## Pruebas

```bash
pip install -r requirements-dev.txt && pytest -q
```
