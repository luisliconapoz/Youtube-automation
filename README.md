# 🎬 Pilo Studio

Fábrica de videos **100 % en la nube**: largos (7–10 min, 16:9) y Shorts/Reels (9:16).
Funciona desde un **iPad** con GitHub Codespaces o GitHub Actions. No hay que instalar nada.

```
 tu idea ─► [1] Claude escribe el guion por escenas (+ texto y concepto de la miniatura)
          ─► [2] LOTE de imágenes: todas las escenas + la miniatura, en paralelo (gratis)
          ─► [3] edge-tts pone la voz (gratis)
          ─► [4] MoviePy + FFmpeg montan el video y queman los subtítulos
          ─► [5] salida/  +  OneDrive (subida automática con rclone)
```

Un solo comando hace todo. Tu única tarea es **revisar y subir**. Cada video entrega:

| Archivo | Contenido |
|---|---|
| `<fecha>_<título>_<formato>.mp4` | El video final con subtítulos incrustados |
| `…_miniatura.jpg` | Miniatura con titular grande (1280×720 para el largo, portada 1080×1920 para el Short) |
| `….srt` | Subtítulos aparte (por si la plataforma los pide) |
| `publicacion.txt` | Título, descripción, hashtags y etiquetas listos para copiar y pegar |
| `guion.json` | El guion completo |

---

## 1. Preparación (una sola vez, desde Safari en el iPad)

### 1.1 Secretos
Los secretos son claves privadas que Codespaces y Actions inyectan como variables. Nunca se guardan en el código.

| Secreto | ¿Obligatorio? | Dónde se consigue | Para qué |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Recomendado | [console.anthropic.com](https://console.anthropic.com) → API Keys | Claude escribe el guion. Sin ella, cada párrafo de tu idea se convierte en una escena. |
| `POLLINATIONS_API_KEY` | Opcional | [enter.pollinations.ai](https://enter.pollinations.ai) (registro gratuito) | Imágenes más rápidas. Sin ella, el modo anónimo genera ~1 imagen cada 16 s. |
| `HF_TOKEN` | Opcional | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) (gratis, permiso *Read*) | Respaldo de imágenes si Pollinations falla. |
| `RCLONE_CONF_B64` | Opcional | Lo genera `scripts/conectar_onedrive.sh` (paso 3) | Subida automática a OneDrive. |

> 💲 La API de Claude es de pago por uso. Un guion cuesta céntimos, pero no es gratis. Todo lo demás (voz, imágenes, montaje y almacenamiento) cuesta cero.

**Para Codespaces:** github.com → foto de perfil → **Settings → Codespaces → Secrets → New secret**.
En *Repository access* elige este repositorio.

**Para Actions:** en el repositorio → **Settings → Secrets and variables → Actions → New repository secret**.
Son independientes de los de Codespaces: crea los mismos nombres en los dos sitios si vas a usar ambos.

### 1.2 Crear el Codespace
1. Abre el repositorio en Safari → botón verde **Code** → pestaña **Codespaces** → **Create codespace on `<rama>`**.
2. Espera 2–4 minutos: se instalan solos Python, FFmpeg, rclone y las dependencias (`.devcontainer/`).
3. En la terminal (abajo) aparecerá el **diagnóstico**, que muestra qué está listo.

> 💡 Consejo para iPad: en Safari, *Compartir → Añadir a pantalla de inicio* abre el Codespace a pantalla completa.
> Un teclado externo ayuda mucho en la terminal.

---

## 2. Producir videos

### Opción A: Codespace (interactivo)
En la terminal:

```bash
python pilo.py
```

El modo guiado te pide la idea, el formato y si quieres reutilizar los personajes de un proyecto existente.
O en una sola línea:

```bash
python pilo.py "Por qué los gatos ronronean" --formato ambos
python pilo.py "Viaje a Marte" --formato short --universo proyectos/ejemplo-pilo-espacio
python pilo.py --proyecto proyectos/ejemplo-pilo-espacio --formato largo
python pilo.py --diagnostico
```

Cuando termina, el video está en `salida/<fecha>_<título>_<formato>/` y, si conectaste OneDrive, también en
`OneDrive/PiloStudio/Videos/`. Para descargarlo al iPad: en el **explorador** (izquierda), clic derecho
(pulsación larga) sobre el `.mp4` → **Download** → se guarda en la app Archivos.

Al terminar verás un resumen **LISTO PARA REVISAR Y SUBIR** con todos los archivos.

### Opción B: GitHub Actions (sin abrir el Codespace)
Ideal para videos largos o para lanzar varios seguidos desde el móvil:

1. Repositorio → pestaña **Actions** → **Producir video** → **Run workflow**.
2. Escribe la idea (o la ruta de un proyecto), elige el formato y pulsa **Run**.
3. Al terminar (unos 10–30 min para un video largo), el video aparece en OneDrive (si configuraste
   `RCLONE_CONF_B64`) y siempre como **artefacto** descargable al final de la página de la ejecución (dura 14 días).

> En repositorios públicos los minutos de Actions son gratuitos. En privados, el plan Free incluye 2.000 min/mes.

---

## 3. Conectar OneDrive (una vez)

En la terminal del Codespace:

```bash
bash scripts/conectar_onedrive.sh
```

El script te guía paso a paso. Lo único raro en el iPad: tras iniciar sesión en Microsoft, Safari mostrará un
**error en una página `localhost:53682`**. Copia esa URL completa y ejecútala en una segunda terminal con
`curl "URL"`. Al final, el script imprime un texto largo. Guárdalo como secreto `RCLONE_CONF_B64`
(en Codespaces y/o Actions) y no tendrás que repetir el proceso.

¿Prefieres Google Drive o Dropbox? Crea el remoto con el mismo método (`rclone config`) y cambia
`salida.nube.destino` en `config/settings.yaml` (por ejemplo, `gdrive:PiloStudio/Videos`).

---

## 4. Personajes y estilo visual consistentes

Cada proyecto vive en `proyectos/<nombre>/`:

```
idea.md         ← la idea (lo único obligatorio)
proyecto.yaml   ← estilo, personajes y escenarios
referencias/    ← imágenes de referencia (opcional)
```

Ejemplo de `proyecto.yaml` (ver `proyectos/ejemplo-pilo-espacio/`):

```yaml
estilo:
  descripcion: "3D animated movie style, soft volumetric lighting, vibrant colors"
  paleta: ["#0b132b", "#5bc0be", "#ffb703"]   # vacío = se extrae de referencias/
  personajes:
    Pilo: "a small friendly orange robot with round glowing blue eyes and a single antenna"
  escenarios:
    nave: "inside a cozy retro-futuristic spaceship cockpit"
```

Para mantener la consistencia, Pilo Studio:
- antepone el mismo estilo a todos los prompts;
- inyecta la descripción fija de cada personaje cuando aparece;
- añade la paleta de color;
- usa la misma semilla en todo el proyecto.

**Subir referencias desde el iPad:** en el Codespace, clic derecho en la carpeta `referencias/` → **Upload…**.
O en github.com: entra en la carpeta → **Add file → Upload files** (necesario si vas a usar Actions).
Si una imagen se llama como un personaje (`Pilo.png`), se usa como respaldo para sus escenas.

Para crear un "universo" reutilizable, prepara un proyecto con personajes y referencias. Luego produce
nuevas ideas con `--universo proyectos/mi-universo`.

---

## 5. Ajustes útiles (`config/settings.yaml`)

| Clave | Qué cambia |
|---|---|
| `audio.voz` | Voz de edge-tts. Lista: `python -m pilo_studio voces --idioma es` |
| `guion.claude.modelo` / `esfuerzo` | Modelo de Claude y nivel de elaboración |
| `formatos.largo.duracion_objetivo_min` | Duración objetivo del video largo |
| `video.musica.archivo` | Música de fondo libre de derechos (p. ej. `assets/music/fondo.mp3`) |
| `salida.nube.destino` | Remoto y carpeta de rclone |

Cualquier clave puede sobrescribirse por proyecto en `proyecto.yaml → config:`.

**Revisar el guion antes de renderizar:** `python pilo.py --proyecto proyectos/x --hasta guion`, edita
`proyectos/x/build/<formato>/guion.json` y vuelve a ejecutar sin `--hasta`. Cada fase guarda caché, así que
una ejecución interrumpida continúa donde se quedó.

---

## 6. Cómo se generan las imágenes (en lote)

En lugar de pedir las imágenes una por una, Pilo Studio mete **todas** las del video (escenas y miniatura)
en una **cola compartida** antes de pasar a la voz y al montaje:

```
cola ──┬─► Pollinations   4 hilos  (con clave; sin clave 1 hilo, 1 imagen / 16 s)
       └─► Hugging Face   2 hilos  (si hay HF_TOKEN)
            │
            └─► lo que falle se reintenta, pasa al otro servicio y, en último caso,
                se resuelve al instante con tus referencias o un fondo de la paleta
```

- Los dos servicios trabajan **a la vez** sobre la misma cola, así que se suman sus velocidades.
- Cada servicio respeta su ritmo máximo y hace una pausa automática si responde "demasiadas peticiones" (429).
  Así no se satura ni te bloquea.
- Si un servicio falla muchas veces seguidas, se desactiva (cortacircuitos) y los demás terminan el trabajo.
- Las imágenes ya generadas se guardan. Si repites la ejecución, solo se piden las que falten.

Para ajustar los hilos y ritmos, usa la sección `imagenes:` de `config/settings.yaml`.

**Velocidad aproximada para un video largo de 20 escenas:**

| Configuración | Tiempo de imágenes |
|---|---|
| Sin claves (Pollinations anónimo) | ~6 min |
| Con `HF_TOKEN` | ~2–3 min |
| Con `POLLINATIONS_API_KEY` (+ `HF_TOKEN`) | menos de 1 min |

---

## 7. Límites a tener en cuenta

- **Codespaces gratis:** 120 horas-núcleo al mes (60 h con la máquina de 2 núcleos). Un video largo tarda
  unos 15–30 min en renderizar. El Codespace se suspende tras 30 min sin actividad; súbelo en
  *Settings → Codespaces → Default idle timeout*, o usa Actions para los videos largos.
  **Detén el Codespace** cuando termines (github.com/codespaces → ⋯ → Stop).
- Si todos los servicios de imágenes fallan, el video se genera igualmente con fondos de la paleta del proyecto.

---

## Estructura del código

```
pilo.py                    # ★ programa maestro
pilo_studio/
├── pipeline.py            # orquestador de las 5 fases (con caché reanudable)
├── director/guionista.py  # 1 · Claude (salida estructurada) / guion manual / plantilla
├── audio/locutor.py       # 3 · edge-tts + marcas de tiempo por palabra
├── visuals/estilo.py      #     biblia de estilo (consistencia)
├── visuals/cola.py        # 2 · cola en lote: hilos por proveedor, ritmo, reintentos, cortacircuitos
├── visuals/generador.py   #     proveedores (Pollinations, Hugging Face) + respaldo local
├── visuals/miniatura.py   #     miniatura con titular
├── assembly/subtitulos.py #     SRT + ASS sincronizados con la voz
├── assembly/montador.py   # 4 · MoviePy (Ken Burns) + FFmpeg (subtítulos, música)
├── storage/exportador.py  # 5 · salida/ + publicacion.txt
└── storage/nube.py        #     subida con rclone (OneDrive, Drive, Dropbox…)
.devcontainer/             # configuración del Codespace
.github/workflows/         # producir.yml (videos en Actions) · tests.yml
scripts/conectar_onedrive.sh
```

Pruebas (se ejecutan solas en cada push): `pytest -q`
