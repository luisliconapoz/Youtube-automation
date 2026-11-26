# Informe técnico · Prueba de producción audiovisual 01

**Tema:** ¿Por qué las empresas necesitan dinero para crecer?
**Resultado:** `salida/video_final.mp4` · 1080×1920 (9:16) · 30 fps · H.264 + AAC · **18,63 s** · 2,2 MB
**Fecha:** 2026-11-26 · Generado en el contenedor en la nube de Claude Code, sin servicios de pago.

## Entregables

| Pide la prueba | Archivo |
|---|---|
| Video MP4 | `salida/video_final.mp4` (subtítulos quemados) |
| Guion | `guion.md` (legible) y `guion.json` (el que leen los scripts) |
| Imágenes | `imagenes/escena_1..5.png` (1080×1920, fotograma clave de cada escena) |
| Audio | `audio/narracion.wav` (completo) y `audio/escena_N.wav` (por escena) |
| Subtítulos aparte | `salida/subtitulos.srt` |
| Scripts | `scripts/01_voz.py`, `scripts/02_montaje.py`, `scripts/03_verificar.py`, `scripts/run.sh` |
| Pruebas de control | `salida/verificacion/fotograma_escena_N.jpg` |

Para regenerar todo: `bash scripts/run.sh` (descarga el modelo de voz a `modelos/`, que no se sube al repositorio por pesar 354 MB).

## 1. Herramientas comprobadas

| Herramienta | Estado | Uso |
|---|---|---|
| FFmpeg 6.1.1 / ffprobe | Instalado | Codificación final, mezcla de audio, verificación |
| Python 3.13 + Pillow 13 + NumPy | Instalado | Dibujo de ilustraciones y fotogramas |
| onnxruntime 1.29 | Instalado | Motor de inferencia del TTS |
| **Kokoro v1.0** (`kokoro-onnx` 0.6.1, Apache-2.0) | Instalado en esta prueba | **TTS usado** |
| Piper TTS | Paquete instalable, pero **sus voces están en Hugging Face, bloqueado por la red** (403) | No usado |
| edge-tts (el que usa Pilo Studio hoy) | **Bloqueado**: el proxy rechaza `speech.platform.bing.com` | No usado |
| espeak-ng 1.51 | Instalado con apt como respaldo | No usado (voz robótica) |
| ElevenLabs (conector MCP disponible) | Disponible, pero **consume créditos de pago** | Descartado por la restricción de no usar APIs de pago |
| Whisper / Vosk (para transcribir y comprobar la voz) | **Bloqueados** (hosts de los modelos rechazados) | No hubo verificación automática de lo que dice la voz |
| Navegador / SVG (rsvg, Inkscape) | No disponibles como CLI | Se dibujó todo con Pillow |

## 2. Cómo se generaron las imágenes

Todas las ilustraciones son **originales y 100 % hechas con código** (`02_montaje.py`), sin bancos de imágenes ni IA generativa:
- Estilo neón 2D sobre fondo oscuro con rejilla en movimiento (coherente con la dirección de arte de Pilo Studio).
- Formas vectoriales dibujadas con Pillow (tienda, batería, monedas, línea de tiempo, calendario, cohete) y un halo *glow* barato (capa reducida a ¼, desenfoque gaussiano, reescalada).
- Cada escena es una función `draw(img, p)` donde `p` (0→1) es el avance de la escena, de modo que los elementos **se animan**: barras que suben, batería que se vacía, monedas que viajan, contador 0→60, cohete que despega.
- Tipografía: Inter / Inter Display (licencia SIL OFL, instalada en el sistema).

## 3. Cómo se generó el audio

- **TTS local real:** Kokoro v1.0 (modelo ONNX de 82 M parámetros, Apache-2.0), voz `em_alex` (masculina, español), velocidad 1,08. **Una sola voz** en todo el video.
- Se sintetiza cada escena por separado, se recortan los silencios de borde y se concatena con pausas fijas (0,30 s entre escenas). Así se conoce el tiempo exacto de inicio y fin de cada frase (`audio/tiempos.json`), que gobierna escenas y subtítulos.
- Normalizado a ~-1 dBFS. Síntesis completa: ~5 s en CPU.
- Sin música de fondo (no se añadió material de terceros).

## 4. Cómo se hizo la edición

- Las escenas cambian en el punto medio de la pausa entre frases, con un **fundido cruzado de 0,3 s**, y un fundido a negro final de 0,4 s.
- **Subtítulos** quemados en cada fotograma (Inter Display Black 80 px, blanco con contorno negro de 10 px, en la franja inferior), en bloques de hasta 3 palabras, cortando también en la puntuación. También se exporta `.srt`.
- Los 559 fotogramas se envían en crudo a FFmpeg junto con la narración → H.264 (CRF 20, yuv420p, `+faststart`) + AAC 192 kbps 48 kHz.

## 5. Verificación (resultado de `03_verificar.py`)

- ffprobe: h264 1080×1920, 30 fps, 559 fotogramas; audio aac 48 kHz; vídeo 18,633 s y audio 18,634 s.
- Decodificación completa con `ffmpeg -f null`: **sin errores**.
- Sincronía: el arranque de voz de las 5 escenas detectado en el audio del MP4 coincide con el previsto con **+10 ms** de desfase (menos de un fotograma). Las escenas y los subtítulos usan esos mismos tiempos.
- Revisión visual de un fotograma por escena: los textos son legibles, nada se sale del cuadro y los subtítulos no se solapan con las ilustraciones. En una primera pasada el titular de la escena 4 se salía del cuadro y un cartel tapaba etiquetas en la escena 5; se corrigió antes del render final.

## 6. Tiempo empleado

| Fase | Tiempo aprox. |
|---|---|
| Comprobar herramientas e instalar/probar TTS (Piper, edge-tts, espeak-ng, Kokoro) | ~2 min |
| Guion + síntesis de voz | ~1 min |
| Código de ilustraciones y montaje + vista previa y correcciones | ~2 min |
| Render final (559 fotogramas, solo CPU) | **92 s** |
| Verificación + documentación | ~2 min |
| **Total** | **~8–10 min de reloj** |

El trabajo creativo (decidir guion y dibujar cada escena en código) es lo que más tiempo requiere; el cómputo es pequeño.

## 7. Limitaciones encontradas (honestas)

1. **No he escuchado el audio.** No puedo oír y, al estar bloqueados Whisper/Vosk, no pude transcribirlo para comprobar automáticamente la pronunciación. Sé que existe, que dura lo previsto, que tiene voz donde debe y silencio donde debe, pero **la calidad y naturalidad de la voz en español debe validarla una persona**. Kokoro es más fuerte en inglés que en español; puede haber acentuación extraña en alguna palabra.
2. **Subtítulos con tiempos estimados dentro de cada frase.** El inicio y el fin de cada frase son exactos; el reparto por bloques de palabras dentro de la frase es proporcional a la longitud del texto, no un alineado palabra por palabra. Puede haber adelantos o retrasos de unas décimas.
3. **Las ilustraciones son esquemáticas** (iconos y gráficos). Sirven para explicar, pero no tienen personajes ni el nivel de detalle de una ilustración hecha a mano o con IA de imagen. Cada escena nueva requiere código nuevo.
4. **La red del entorno** bloquea Hugging Face, Bing (edge-tts) y los modelos de ASR, por lo que el TTS que usa hoy Pilo Studio (edge-tts) **no funciona en este entorno**.
5. Sin música ni efectos de sonido.

## 8. Qué necesitaríamos para producir tres videos diarios

1. **Plantillas de escena reutilizables** en lugar de dibujar cada escena desde cero: biblioteca de 15–20 «escenas tipo» parametrizables (comparación A/B, línea de tiempo, gráfico que sube/baja, flujo de dinero, lista de 3, cifra gigante, cierre/CTA). El guion (JSON) elegiría plantilla + textos + números. Es la mejora que más ahorra tiempo.
2. **Voz decidida y validada por una persona:** escuchar esta prueba y decidir entre Kokoro (gratis, local, quizá menos natural en español), edge-tts (gratis, muy natural, pero necesita red hacia Bing) o una voz de pago. Si se queda Kokoro, conviene un diccionario de pronunciación para términos financieros.
3. **Alineado palabra a palabra** para subtítulos dinámicos (resaltar la palabra que se dice): Whisper o un alineador forzado, que requieren permitir la descarga del modelo en la red del entorno.
4. **Red del entorno:** permitir `huggingface.co` (voces Piper, Whisper) y, si se quiere edge-tts, `speech.platform.bing.com`; o dejar los modelos ya incluidos en el script de configuración del entorno, para no descargar 354 MB en cada sesión.
5. **Música y efectos libres de derechos** (biblioteca propia con licencia verificada, o generados por código) y normalización de sonoridad a -14 LUFS para redes sociales.
6. **Encadenamiento y control de calidad automáticos:** un comando que reciba 3 temas, genere los 3 videos en paralelo (~1,5 min de render cada uno con solo CPU) y produzca una hoja de revisión (fotogramas de control + duración + sincronía), dejando a la persona solo la escucha final y la publicación.
7. Integrar esto con el pipeline existente de Pilo Studio (`pilo_studio/`) **solo después** de validar esta prueba, como se pidió.
