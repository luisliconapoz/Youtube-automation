"""Paso 2 · Ilustraciones + animación + subtítulos + exportación MP4.

Todo se dibuja con código (Pillow): estilo neón 2D sobre fondo oscuro.
Cada escena es una función draw(img, p) donde p∈[0,1] es el avance de la escena,
así los elementos aparecen y se mueven. Los fotogramas se envían en crudo a FFmpeg
junto con audio/narracion.wav → salida/video_final.mp4 (1080x1920, 30 fps, H.264 + AAC).

También guarda:
  imagenes/escena_N.png  – fotograma clave de cada escena (sin subtítulos)
  salida/subtitulos.srt  – los mismos subtítulos que se queman en pantalla
"""
import json
import math
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE = Path(__file__).resolve().parent.parent
W, H, FPS = 1080, 1920, 30
XFADE = 0.30  # duración del fundido entre escenas (s)

guion = json.loads((BASE / "guion.json").read_text(encoding="utf-8"))
tiempos = json.loads((BASE / "audio" / "tiempos.json").read_text())
DUR = tiempos["duracion"]

FD = "/usr/share/fonts/opentype/inter/"
def font(size, peso="InterDisplay-Black"):
    return ImageFont.truetype(FD + peso + ".otf", size)

F_TIT, F_LBL, F_SML, F_SUB, F_BIG = font(118), font(54, "InterDisplay-ExtraBold"), font(40, "Inter-Bold"), font(80), font(150)

BG = (8, 8, 18)
CYAN, MAG, LIME, ORANGE, RED, YEL, WHITE = (0, 229, 255), (255, 46, 160), (120, 255, 90), (255, 150, 30), (255, 60, 70), (255, 222, 40), (240, 240, 255)


# ───────── utilidades de dibujo ─────────
def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3

def seg(p, a, b):
    """Avance local de p dentro del tramo [a, b] con suavizado."""
    return ease((p - a) / (b - a))

def neon(base, dibujar):
    """Dibuja en una capa y le añade un halo difuminado (glow) barato."""
    capa = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dibujar(ImageDraw.Draw(capa))
    peq = capa.resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(6))
    halo = peq.resize((W, H), Image.BILINEAR)
    base.alpha_composite(halo)
    base.alpha_composite(halo)
    base.alpha_composite(capa)

def texto_c(d, xy, txt, f, fill, stroke=0, sc=(0, 0, 0)):
    d.text(xy, txt, font=f, fill=fill, anchor="mm", stroke_width=stroke, stroke_fill=sc)

def moneda(d, cx, cy, r=34, col=YEL):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col, width=7)
    texto_c(d, (cx, cy + 2), "$", font(int(r * 1.3)), col)

def fondo(p):
    img = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(img)
    off = int(p * 60)  # rejilla que se desplaza lento: sensación de movimiento
    for y in range(-80 + off % 80, H, 80):
        d.line([(0, y), (W, y)], fill=(22, 22, 44), width=2)
    for x in range(0, W, 80):
        d.line([(x, 0), (x, H)], fill=(22, 22, 44), width=2)
    return img

def titular(img, txt, col, p):
    a = seg(p, 0.0, 0.18)
    dy = int((1 - a) * 60)
    f, size = F_TIT, 118
    while ImageDraw.Draw(img).textlength(txt, font=f) > W - 90:  # ajusta el titular al ancho
        size -= 4; f = font(size)
    def dib(d):
        texto_c(d, (W // 2, 300 + dy), txt, f, col + (int(255 * a),))
    neon(img, dib)

def tienda(d, cx, by, s, col, w=8):
    """Icono de tienda: cuerpo, toldo, puerta. by = base, s = escala."""
    bw, bh = 300 * s, 220 * s
    d.rectangle([cx - bw / 2, by - bh, cx + bw / 2, by], outline=col, width=w)
    d.polygon([(cx - bw / 2 - 25 * s, by - bh), (cx + bw / 2 + 25 * s, by - bh), (cx + bw / 2, by - bh - 70 * s), (cx - bw / 2, by - bh - 70 * s)], outline=col, width=w)
    for i in range(1, 5):
        x = cx - bw / 2 - 25 * s + i * (bw + 50 * s) / 5
        d.line([(x, by - bh), (x + (cx - x) * 0.07, by - bh - 70 * s)], fill=col, width=max(3, w // 2))
    d.rectangle([cx - 45 * s, by - 130 * s, cx + 45 * s, by], outline=col, width=w)


# ───────── escenas ─────────
def escena1(img, p):  # HOOK: ventas suben, caja se vacía
    titular(img, "VENDE MUCHO…", CYAN, p)
    def dib(d):
        tienda(d, 540, 1000, 1.25, CYAN)
        # ventas (barras verdes que suben)
        for i, h in enumerate([90, 150, 220, 300]):
            hh = h * seg(p, 0.05 + i * 0.08, 0.35 + i * 0.08)
            x = 120 + i * 62
            d.rectangle([x, 1290 - hh, x + 44, 1290], fill=LIME)
        texto_c(d, (215, 1340), "VENTAS ▲", F_SML, LIME)
        # caja (batería que se vacía)
        nivel = 1 - 0.88 * seg(p, 0.25, 0.9)
        col = LIME if nivel > 0.6 else (ORANGE if nivel > 0.3 else RED)
        d.rounded_rectangle([780, 980, 960, 1290], 16, outline=WHITE, width=7)
        d.rectangle([840, 958, 900, 980], fill=WHITE)
        d.rectangle([796, 1274 - 278 * nivel, 944, 1274], fill=col)
        texto_c(d, (870, 1340), "CAJA ▼", F_SML, col)
        if p > 0.55:
            a = seg(p, 0.55, 0.75)
            texto_c(d, (540, 520), "¿SIN DINERO?", font(96), RED + (int(255 * a),))
    neon(img, dib)

def escena2(img, p):  # primero paga
    titular(img, "PRIMERO PAGA", MAG, p)
    gastos = [("MATERIALES", 200), ("SUELDOS", 540), ("ALQUILER", 880)]
    def dib(d):
        cx, cy = 540, 720
        d.rounded_rectangle([cx - 150, cy - 95, cx + 150, cy + 95], 26, outline=CYAN, width=8)
        texto_c(d, (cx, cy), "EMPRESA", F_LBL, CYAN)
        for i, (nom, x) in enumerate(gastos):
            a0 = 0.08 + i * 0.22
            ap = seg(p, a0, a0 + 0.12)
            if ap <= 0:
                continue
            y = 1180
            d.rounded_rectangle([x - 150, y - 70, x + 150, y + 70], 20, outline=MAG + (int(255 * ap),), width=7)
            texto_c(d, (x, y), nom, font(38, "InterDisplay-ExtraBold"), MAG + (int(255 * ap),))
            # monedas que viajan de la empresa al gasto
            for k in range(3):
                m = seg(p, a0 + k * 0.05, a0 + 0.2 + k * 0.05)
                if 0 < m < 1:
                    mx, my = cx + (x - cx) * m, cy + 100 + (y - 170 - cy) * m
                    moneda(d, mx, my, 30)
            texto_c(d, (x, y + 115), "– $", F_LBL, RED + (int(255 * ap),))
    neon(img, dib)

def escena3(img, p):  # cobra después: hueco de caja
    titular(img, "COBRA DESPUÉS", LIME, p)
    def dib(d):
        y, x0, x1 = 960, 140, 940
        lp = seg(p, 0.05, 0.6)
        xe = x0 + (x1 - x0) * lp
        # hueco sombreado entre pagar y cobrar
        for x in range(x0, int(xe), 28):
            d.line([(x, y - 120), (x + 60, y - 60)], fill=MAG + (110,), width=4)
        d.line([(x0, y), (xe, y)], fill=WHITE, width=8)
        d.ellipse([x0 - 22, y - 22, x0 + 22, y + 22], fill=RED)
        texto_c(d, (x0 + 40, y + 80), "HOY", F_LBL, RED)
        texto_c(d, (x0 + 40, y + 140), "pagas", F_SML, RED)
        if lp > 0.98:
            a = seg(p, 0.6, 0.72)
            d.ellipse([x1 - 22, y - 22, x1 + 22, y + 22], fill=LIME)
            texto_c(d, (x1 - 50, y + 80), "DÍA 60", F_LBL, LIME + (int(255 * a),))
            texto_c(d, (x1 - 50, y + 140), "cobras", F_SML, LIME + (int(255 * a),))
            moneda(d, x1, y - 210 + int(30 * math.sin(p * 20)), 44)
        a2 = seg(p, 0.35, 0.55)
        texto_c(d, (540, y - 250), "HUECO DE CAJA", F_LBL, MAG + (int(255 * a2),))
        # calendario
        cal = seg(p, 0.0, 0.2)
        d.rounded_rectangle([420, 1270, 660, 1470], 18, outline=CYAN + (int(255 * cal),), width=6)
        d.rectangle([420, 1270, 660, 1320], fill=CYAN + (int(255 * cal),))
        texto_c(d, (540, 1400), str(int(60 * lp)), F_TIT, WHITE + (int(255 * cal),))
    neon(img, dib)

def escena4(img, p):  # crecer cuesta hoy
    titular(img, "CRECER CUESTA HOY", ORANGE, p)
    def dib(d):
        pos = [(230, 0.7), (540, 0.95), (850, 1.2)]
        for i, (x, s) in enumerate(pos):
            a = seg(p, 0.05 + i * 0.18, 0.25 + i * 0.18)
            if a > 0:
                tienda(d, x, 1150, s * 0.75 * a + 0.01, (CYAN, LIME, YEL)[i] + (int(255 * a),), w=7)
        # flecha de crecimiento
        fa = seg(p, 0.3, 0.8)
        pts = [(150 + 760 * t, 1250 - 600 * (t ** 1.8)) for t in [k / 30 * fa for k in range(31)]]
        if fa > 0.02:
            d.line(pts, fill=ORANGE, width=10, joint="curve")
            (ex, ey), (px, py) = pts[-1], pts[-3]
            ang = math.atan2(ey - py, ex - px)
            d.polygon([(ex + 30 * math.cos(ang), ey + 30 * math.sin(ang)),
                       (ex + 30 * math.cos(ang + 2.4), ey + 30 * math.sin(ang + 2.4)),
                       (ex + 30 * math.cos(ang - 2.4), ey + 30 * math.sin(ang - 2.4))], fill=ORANGE)
        a1, a2 = seg(p, 0.15, 0.3), seg(p, 0.6, 0.75)
        texto_c(d, (250, 1320), "HOY: – $", F_LBL, RED + (int(255 * a1),))
        texto_c(d, (790, 560), "MAÑANA: + $$$", F_LBL, LIME + (int(255 * a2),))
    neon(img, dib)

def escena5(img, p):  # préstamos / inversores = combustible
    titular(img, "COMBUSTIBLE", YEL, p)
    def dib(d):
        sube = seg(p, 0.45, 1.0) * 160
        cx, cy = 540, 980 - sube
        # cohete
        d.polygon([(cx, cy - 230), (cx + 75, cy - 90), (cx + 75, cy + 120), (cx - 75, cy + 120), (cx - 75, cy - 90)], outline=WHITE, width=8)
        d.ellipse([cx - 32, cy - 80, cx + 32, cy - 16], outline=CYAN, width=7)
        d.polygon([(cx - 75, cy + 30), (cx - 140, cy + 140), (cx - 75, cy + 120)], outline=WHITE, width=7)
        d.polygon([(cx + 75, cy + 30), (cx + 140, cy + 140), (cx + 75, cy + 120)], outline=WHITE, width=7)
        llama = 70 + 40 * abs(math.sin(p * 40)) + sube * 0.6
        d.polygon([(cx - 50, cy + 125), (cx + 50, cy + 125), (cx, cy + 125 + llama)], fill=ORANGE)
        d.polygon([(cx - 25, cy + 125), (cx + 25, cy + 125), (cx, cy + 125 + llama * 0.6)], fill=YEL)
        # fuentes de dinero
        a3 = seg(p, 0.62, 0.8)
        for i, (nom, x, col) in enumerate([("PRÉSTAMOS", 220, CYAN), ("INVERSORES", 855, MAG)]):
            a = seg(p, 0.02 + i * 0.12, 0.15 + i * 0.12) * (1 - a3)
            texto_c(d, (x, 1330), nom, font(50, "InterDisplay-ExtraBold"), col + (int(255 * a),))
            for k in range(4):
                m = ((p * 2.2 + k * 0.25) % 1.0) if a > 0.5 and p < 0.75 else -1
                if m >= 0:
                    moneda(d, x + (cx - x) * m, 1260 + (cy + 60 - 1260) * m, 26)
        if a3 > 0:
            d.rounded_rectangle([90, 1240, 990, 1400], 30, fill=BG + (int(235 * a3),), outline=YEL + (int(255 * a3),), width=6)
            texto_c(d, (540, 1320), "DINERO = CRECIMIENTO", font(66), YEL + (int(255 * a3),))
    neon(img, dib)

ESCENAS = [escena1, escena2, escena3, escena4, escena5]


# ───────── tiempos de escena y subtítulos ─────────
esc_t = tiempos["escenas"]
limites = [0.0] + [(esc_t[i]["voz_fin"] + esc_t[i + 1]["voz_inicio"]) / 2 for i in range(len(esc_t) - 1)] + [DUR]

subs = []  # (inicio, fin, texto)
for esc, t in zip(guion["escenas"], esc_t):
    palabras = esc["narracion"].split()
    trozos, act = [], []
    for w in palabras:
        act.append(w)
        if len(act) == 3 or re.search(r"[,.:…?!]$", w):
            trozos.append(" ".join(act)); act = []
    if act:
        trozos.append(" ".join(act))
    # reparto del tiempo de voz proporcional a la longitud de cada trozo
    total = sum(len(x) + 2 for x in trozos)
    t0, dur = t["voz_inicio"], t["voz_fin"] - t["voz_inicio"]
    for x in trozos:
        d = dur * (len(x) + 2) / total
        subs.append((t0, t0 + d, x)); t0 += d

def sub_en(t):
    for a, b, x in subs:
        if a - 0.05 <= t < b + 0.05:
            return x
    return None

def dibujar_sub(img, txt):
    d = ImageDraw.Draw(img)
    l, tp, r, bt = d.textbbox((0, 0), txt, font=F_SUB, stroke_width=10)
    if r - l > W - 80:  # salvaguarda: reduce si no cabe
        f = font(int(80 * (W - 80) / (r - l)))
    else:
        f = F_SUB
    d.text((W // 2, 1600), txt, font=f, fill=WHITE, anchor="mm", stroke_width=10, stroke_fill=(0, 0, 0))

def fotograma(t):
    i = max(k for k in range(len(ESCENAS)) if limites[k] <= t) if t < DUR else len(ESCENAS) - 1
    def render(k):
        p = (t - limites[k]) / (limites[k + 1] - limites[k])
        img = fondo(t / DUR)
        ESCENAS[k](img, max(0.0, min(1.0, p)))
        return img
    img = render(i)
    # crossfade con la escena siguiente alrededor del límite
    if i + 1 < len(ESCENAS) and t > limites[i + 1] - XFADE:
        a = (t - (limites[i + 1] - XFADE)) / XFADE
        img = Image.blend(img, render(i + 1), min(1.0, a))
    return img


def srt_tc(s):
    ms = int(round(s * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); se, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{se:02},{ms:03}"


if __name__ == "__main__":
    (BASE / "imagenes").mkdir(exist_ok=True)
    (BASE / "salida").mkdir(exist_ok=True)

    # imágenes clave de cada escena
    for k, f in enumerate(ESCENAS):
        img = fondo(0.5); f(img, 0.9)
        img.convert("RGB").save(BASE / "imagenes" / f"escena_{k + 1}.png")

    # subtítulos .srt
    with open(BASE / "salida" / "subtitulos.srt", "w", encoding="utf-8") as fh:
        for n, (a, b, x) in enumerate(subs, 1):
            fh.write(f"{n}\n{srt_tc(a)} --> {srt_tc(b)}\n{x}\n\n")

    n = math.ceil(DUR * FPS)
    salida = BASE / "salida" / "video_final.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", str(BASE / "audio" / "narracion.wav"),
           "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-profile:v", "high",
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-t", f"{DUR:.3f}", "-movflags", "+faststart", str(salida)]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for j in range(n):
        t = j / FPS
        img = fotograma(t)
        s = sub_en(t)
        if s:
            dibujar_sub(img, s)
        if t > DUR - 0.4:  # fundido a negro final
            img = Image.blend(img, Image.new("RGBA", (W, H), (0, 0, 0, 255)), (t - (DUR - 0.4)) / 0.4)
        ff.stdin.write(img.convert("RGB").tobytes())
        if j % 60 == 0:
            print(f"  fotograma {j}/{n}", flush=True)
    ff.stdin.close()
    ff.wait()
    print("OK:", salida, "código", ff.returncode)
