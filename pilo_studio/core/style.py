"""Identidad visual compartida de PILO STUDIO.

Fuente única de verdad para las reglas visuales que TODAS las marcas comparten.
El validador (qa/validator.py) y el constructor de prompts (prompts/image_prompt.py)
leen de aquí; si cambias una regla, cámbiala solo en este archivo.
"""

# Expresiones estándar permitidas (Biblia PILO STUDIO, Parte 2.1)
EXPRESSIONS = (
    "Neutral", "Happy", "Talking", "Surprised", "Confused", "Thinking",
    "Concerned", "Skeptical", "Excited", "Angry", "Serious", "Smug",
)

# Poses estándar permitidas
POSES = (
    "Explaining", "Pointing", "Thinking", "Presenting", "Questioning",
    "Thumbs up", "Arms crossed", "Celebrating",
)

# Descripción en inglés de cada expresión/pose para los generadores de imagen
# (los modelos de imagen responden mejor a prompts en inglés).
EXPRESSION_PROMPTS = {
    "Neutral": "calm neutral face, relaxed white eyes",
    "Happy": "happy face, smiling, bright curved white eyes",
    "Talking": "mouth open mid-sentence, engaged white eyes",
    "Surprised": "surprised face, wide round white eyes, open mouth",
    "Confused": "confused face, one eyebrow raised, tilted head",
    "Thinking": "thoughtful face, eyes looking up and to the side",
    "Concerned": "worried face, eyebrows angled up in the middle",
    "Skeptical": "skeptical face, narrowed white eyes, one brow raised",
    "Excited": "excited face, huge smile, sparkling wide white eyes",
    "Angry": "angry face, eyebrows sharply angled down, frowning",
    "Serious": "serious face, focused flat white eyes, straight mouth",
    "Smug": "smug face, half-closed eyes, confident side smirk",
}

POSE_PROMPTS = {
    "Explaining": "explaining pose, one hand open palm gesturing outward",
    "Pointing": "pointing pose, arm extended pointing at the key object",
    "Thinking": "thinking pose, hand on chin",
    "Presenting": "presenting pose, both arms open toward the key object",
    "Questioning": "questioning pose, shrugging with palms up",
    "Thumbs up": "thumbs up pose, one arm raised with thumb up",
    "Arms crossed": "arms crossed over chest, weight on one leg",
    "Celebrating": "celebrating pose, both arms raised in victory",
}

# Estilo base que se antepone a CADA prompt de imagen.
STYLE_PREAMBLE = (
    "2D flat vector animation frame, minimalist editorial stickman style, "
    "solid pure black background, characters with solid black bodies "
    "and glowing neon outlines in their official color, expressive white eyes, "
    "simple facial features, soft neon glow around characters and key objects, "
    "clean simple scene with a single main visual idea, generous negative space, "
    "consistent character proportions, professional and polished"
)

# Negativo: se envía como negative prompt (si la herramienta lo soporta) y se
# añade como cláusula "no ..." en las que no lo soportan.
NEGATIVE_PROMPT = (
    "text, letters, words, numbers, digits, captions, subtitles, titles, labels, "
    "logos, watermark, signature, speech bubbles with text, 3D render, CGI, "
    "photorealistic, photograph, realistic skin, gradient background, white "
    "background, colored background, cluttered scene, busy background, extra "
    "limbs, deformed hands, changed character colors, off-model character"
)

# Palabras que delatan texto incrustado en la imagen (PROHIBIDO).
TEXT_IN_IMAGE_MARKERS = (
    "text", "title", "caption", "subtitle", "label", "headline", "banner",
    "sign that says", "written", "writing", "letters", "words", "logo",
    "watermark", "says \"", "reading \"", "typography", "font",
    # español, por si el guionista escribe en español
    "texto", "título", "titulo", "subtítulo", "subtitulo", "letrero", "etiqueta",
    "palabras", "letras", "escrito",
)

# Palabras que delatan estilo prohibido (3D / foto realista).
FORBIDDEN_STYLE_MARKERS = (
    "3d", "photorealistic", "photo-realistic", "photograph", "photo of",
    "realistic", "hyperrealistic", "cgi", "octane", "unreal engine",
    "fotorrealista", "fotografía", "fotografia", "realista",
)

# Fondos permitidos: siempre negro.
BACKGROUND_RULE = "solid pure black background"

MAX_CHARACTERS_PER_SCENE = 3
