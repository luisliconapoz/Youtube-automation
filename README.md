# 🎬 Pilo Studio

Fábrica de **Shorts/Reels verticales (9:16, de 40 a 60 s)** para tres canales, cada uno con su nicho y
sus personajes oficiales. También puede hacer videos largos (7–10 min, 16:9).
Funciona **100 % en la nube**, desde un **iPad**, con GitHub Codespaces o GitHub Actions. No hay que instalar nada.

| Canal | Nicho | Personajes oficiales |
|---|---|---|
| `fact-stick` | Finanzas personales, ahorro, inversión | Blue, Green, Pink, Farmer, Rich |
| `money-lab` | Bienes raíces, crédito, deudas, seguros | Cyan, Lime, Brown, Gray |
| `wild-money` | Negocios, multimillonarios, lujo, cómo funcionan las empresas | Orange, Purple, White, Teal |

```
 canal + idea ─► [1] DIRECCIÓN Y GUION   Claude escribe el guion y un prompt de imagen avanzado por escena
                                    (neón 2D sobre negro, personajes oficiales, expresión y pose)
          ─► [2] IMÁGENES ∥ VOZ     lote de imágenes en paralelo  +  voz con edge-tts, al mismo tiempo
          ─► [3] ENSAMBLAJE         MoviePy + FFmpeg, subtítulos sincronizados quemados en pantalla
          ─► [4] EXPORTACIÓN        .mp4 + miniatura + .srt + publicacion.txt → salida/ y OneDrive
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

El modo guiado te pide el canal, la idea y el formato (Enter = Short).
O en una sola línea (el formato por defecto es el Short 9:16 de 40–60 s):

```bash
python pilo.py "Por qué el interés compuesto te hace rico" --canal fact-stick
python pilo.py "Rentar o comprar casa: qué conviene" --canal money-lab
python pilo.py "Cómo gana dinero Costco con sus membresías" --canal wild-money
python pilo.py "Cómo funciona Amazon" --canal wild-money --formato largo   # video largo 16:9
python pilo.py --diagnostico
```

Cuando termina, el video está en `salida/<fecha>_<título>_<formato>/` y, si conectaste OneDrive, también en
`OneDrive/PiloStudio/Videos/`. Para descargarlo al iPad: en el **explorador** (izquierda), clic derecho
(pulsación larga) sobre el `.mp4` → **Download** → se guarda en la app Archivos.

Al terminar verás un resumen **LISTO PARA REVISAR Y SUBIR** con todos los archivos.

### Opción B: GitHub Actions (sin abrir el Codespace)
Ideal para videos largos o para lanzar varios seguidos desde el móvil:

1. Repositorio → pestaña **Actions** → **Producir video** → **Run workflow**.
2. Elige el **canal**, escribe la idea y pulsa **Run** (el formato por defecto es el Short).
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

## 4. Dirección de arte: neón 2D y personajes oficiales

### Reglas fijas para todas las imágenes
Están en `config/settings.yaml → direccion_arte` y se aplican a cada imagen de la secuencia
(`image_001.png`, `image_002.png`…):

- **Estilo:** ilustración vectorial minimalista en neón 2D sobre fondo negro puro: personajes *stick figure*
  con cabeza negra redonda, ojos blancos grandes y contorno neón. Limpia, profesional y con una idea clara
  por imagen (9:16 en el Short, 16:9 en el video largo).
- **Personajes:** Claude **solo puede usar** los personajes oficiales del universo. Es una lista cerrada:
  si intenta usar otro, la respuesta se rechaza. Cada personaje aparece con su rol, sus colores y su aspecto
  oficial, tomados de su ficha.
- **Expresión y pose:** para cada personaje de cada escena, Claude elige una expresión y una pose de las
  listas oficiales según lo que se dice, más una acción breve (qué hace o sostiene).
- **Prohibido:** texto, títulos, letras, números, marcas de agua, logos, renders 3D y fotos realistas.
  Se aplica de cuatro formas:
  1. está en las instrucciones de Claude;
  2. cada prompt se limpia antes de enviarlo (se borran las frases entre comillas y las cifras; los códigos
     de color se convierten en nombres);
  3. cada prompt termina con la lista de prohibiciones;
  4. la lista se envía también como prompt negativo al generador.

El orden de cada prompt es siempre el mismo:
`estilo neón 2D → escena → ficha de cada personaje (rol, colores, aspecto, expresión, pose) → escenario →
paleta → encuadre → prohibiciones`. Si un prompt es demasiado largo, se recorta la descripción de la escena,
nunca las reglas.

### Los tres canales
Cada canal es una carpeta en `proyectos/` con:

```
proyecto.yaml          ← nicho, personajes oficiales (rol, personalidad, color, aspecto), escenarios, reglas propias
guia/guia_oficial.jpg  ← la guía visual oficial ("Visual Production Guide")
```

- **Personajes:** su aspecto está transcrito de la guía. Por ejemplo, Purple lleva corona dorada, capa y traje;
  Farmer, sombrero de paja, bigote, overol y horca. Cada imagen recibe la ficha completa del personaje.
- **Expresiones y poses:** son las listas oficiales, comunes a los tres canales.
  - Expresiones: Neutral, Happy, Talking, Surprised, Confused, Thinking, Concerned, Skeptical, Excited, Angry,
    Serious, Smug.
  - Poses: Explaining, Pointing, Thinking, Presenting, Questioning, Arms crossed, Thumbs up, Celebrating.

  Claude solo puede elegir de estas listas; cualquier otro valor se rechaza.
- **La guía se envía a Claude como imagen** con cada guion, para que respete personajes, colores, poses y la
  sección *AVOID*.
- **Reglas propias** de cada canal en `reglas_extra`. Por ejemplo, en Fact Stick: "combinación equilibrada de
  colores, no solo Blue".
- Canal por defecto: `universo_por_defecto` en `config/settings.yaml`. Se cambia por video con `--canal`.

Para corregir un personaje, edita su ficha en `proyecto.yaml`. Si añades imágenes oficiales sueltas de cada
personaje en `referencias/` (por ejemplo `Purple.png`), se usan como respaldo cuando la nube falla.
Las guías no se usan como respaldo porque llevan texto.

> Los generadores gratuitos (Pollinations, Hugging Face) no copian una imagen de referencia: dibujan a partir
> de la descripción. Por eso las fichas son muy detalladas y la semilla es fija. Aun así, puede haber
> pequeñas variaciones entre imágenes.

### Duración de los Shorts (40–60 s)
- Claude escribe unas 125 palabras repartidas en **8–12 escenas** (una idea clara cada 4–6 s).
- Tras generar la voz, se mide la duración. Si pasa de 58 s, la voz se vuelve a generar algo más rápida
  (hasta +25 %). Si queda por debajo de 40 s, aparece un aviso.
- Se ajusta en `formatos.short` de `config/settings.yaml`.

**Miniatura:** el fondo se genera con el mismo estilo neón y sin texto. Después se le añade el titular grande,
como en una miniatura de YouTube. Para no añadirlo, pon `miniatura.titular: false`.

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
`proyectos/x/build/<formato>/guion.json` y vuelve a ejecutar sin `--hasta`. Los pasos válidos para `--hasta`
son `guion`, `medios`, `montaje` y `exportar`. Cada paso guarda caché, así que una ejecución interrumpida
continúa donde se quedó.

---

## 6. Cómo se generan las imágenes (en lote)

En lugar de pedir las imágenes una por una, Pilo Studio mete **todas** las del video (secuencia y miniatura)
en una **cola compartida**. Mientras tanto, edge-tts genera la voz en paralelo:

```
cola ──┬─► Pollinations   4 hilos  (con clave; sin clave 1 hilo, 1 imagen / 16 s)
       └─► Hugging Face   2 hilos  (si hay HF_TOKEN)
            │
            └─► lo que falle se reintenta, pasa al otro servicio y tiene una ronda extra
                a los 30 s. Solo si todo falla, se reutiliza la imagen vecina de la secuencia
                (o una referencia oficial).
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
├── pipeline.py            # orquestador de los 4 pasos (imágenes ∥ voz, caché reanudable)
├── director/guionista.py  # 1 · Claude (salida estructurada) / guion manual / plantilla
├── audio/locutor.py       # 2 · edge-tts + marcas de tiempo por palabra
├── visuals/estilo.py      # 1 · dirección de arte: neón 2D, fichas de personaje, limpieza de prompts
├── visuals/cola.py        # 2 · cola en lote: hilos por proveedor, ritmo, reintentos, cortacircuitos
├── visuals/generador.py   #     proveedores (Pollinations, Hugging Face) + respaldo local
├── visuals/miniatura.py   #     miniatura con titular
├── assembly/subtitulos.py #     SRT + ASS sincronizados con la voz
├── assembly/montador.py   # 3 · MoviePy (Ken Burns) + FFmpeg (subtítulos, música)
├── storage/exportador.py  # 4 · salida/ + publicacion.txt
└── storage/nube.py        #     subida con rclone (OneDrive, Drive, Dropbox…)
.devcontainer/             # configuración del Codespace
.github/workflows/         # producir.yml (videos en Actions) · tests.yml
scripts/conectar_onedrive.sh
```

Pruebas (se ejecutan solas en cada push): `pytest -q`
