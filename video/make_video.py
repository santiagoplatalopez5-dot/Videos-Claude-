"""Genera el TikTok «¿El choque de puños de Goku Dios y Beerus ya no es canon?».

Uso:
    python3 tts.py <modelo_piper.onnx> <build>/tts 0.76
    python3 make_video.py <build> salida.mp4            # video completo
    python3 make_video.py <build> hoja.png --sheet      # hoja de contactos para revisar

Todo el material visual y sonoro se genera aquí (sin capturas con copyright).
"""
import json, math, os, subprocess, sys, wave
from functools import lru_cache

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from segments import SEGMENTS

W, H, FPS, SR = 1080, 1920, 30, 44100
BUILD = sys.argv[1]
OUT = sys.argv[2]
SHEET = "--sheet" in sys.argv

YEL, RED, PUR, GRN, WHT, BLK = (255, 221, 0), (255, 45, 60), (160, 70, 255), (40, 220, 110), (255, 255, 255), (0, 0, 0)
F_BLACK = "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf"
F_BOLD = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"

# ------------------------------------------------------------------ timeline
DURS = json.load(open(f"{BUILD}/tts/durs.json"))
GAP = {5: 0.38, 6: 0.22, 7: 0.3, 12: 0.32, 14: 0.25, 16: 0.25}  # pausa antes del segmento i
SEG_START, t = [], 0.2
for i, d in enumerate(DURS):
    t += GAP.get(i, 0.1)
    SEG_START.append(t)
    t += d
TOTAL = t + 0.7
SCENES = sorted({s for s, _, _ in SEGMENTS})
SC_START = {}
for i, (s, _, _) in enumerate(SEGMENTS):
    SC_START.setdefault(s, max(0.0, SEG_START[i] - 0.08))
SC_START[SCENES[0]] = 0.0
SC_END = {s: (SC_START[SCENES[k + 1]] if k + 1 < len(SCENES) else TOTAL) for k, s in enumerate(SCENES)}


def word_times(i):
    """Tiempos aproximados por palabra dentro del segmento i (proporcional a longitud)."""
    words = SEGMENTS[i][2].split()
    wts = [len(w.strip("«»¿?¡!.,:")) + 1.5 + (2.5 if w[-1] in ",:.?!»" else 0) for w in words]
    tot, acc, out = sum(wts), 0.0, []
    for w, wt in zip(words, wts):
        a = SEG_START[i] + DURS[i] * acc / tot
        acc += wt
        out.append((w, a, SEG_START[i] + DURS[i] * acc / tot))
    return out


WORDS = [word_times(i) for i in range(len(SEGMENTS))]


def wt(i, sub):
    """Tiempo global en el que empieza la primera palabra del segmento i que contiene `sub`."""
    for w, a, _ in WORDS[i]:
        if sub.lower() in w.lower():
            return a
    raise KeyError(sub)


# Subtítulos: grupos de hasta 3 palabras
CHUNKS = []
for ws in WORDS:
    cur = []
    for w in ws:
        cur.append(w)
        chars = sum(len(x[0]) for x in cur)
        if len(cur) == 3 or chars >= 15 or w[0][-1] in ",:.?!»":
            CHUNKS.append(cur)
            cur = []
    if cur:
        CHUNKS.append(cur)

# ------------------------------------------------------------------ helpers
@lru_cache(None)
def font(size, path=F_BLACK):
    return ImageFont.truetype(path, size)


@lru_cache(None)
def text_img(text, size, fill=WHT, stroke=10, stroke_fill=BLK, maxw=940, path=F_BLACK, spacing=0.0):
    while True:
        f = font(size, path)
        d = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
        sp = int(size * spacing)
        box = d.multiline_textbbox((0, 0), text, font=f, stroke_width=stroke, align="center", spacing=sp)
        box = (math.floor(box[0]), math.floor(box[1]), math.ceil(box[2]), math.ceil(box[3]))
        if box[2] - box[0] <= maxw or size <= 30:
            break
        size -= 4
    pad = 8
    im = Image.new("RGBA", (box[2] - box[0] + 2 * pad, box[3] - box[1] + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(im).multiline_text((pad - box[0], pad - box[1]), text, font=f, fill=fill, stroke_width=stroke,
                                      stroke_fill=stroke_fill, align="center", spacing=sp)
    return im


@lru_cache(None)
def label_img(text, size, fg=BLK, bg=YEL, maxw=940, pad=28, radius=22):
    ti = text_img(text, size, fg, 0, fg, maxw - 2 * pad)
    im = Image.new("RGBA", (ti.width + 2 * pad, ti.height + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius, fill=bg)
    im.alpha_composite(ti, (pad, pad))
    return im


def put(frame, im, cx, cy, scale=1.0, alpha=1.0, angle=0.0):
    if scale <= 0.01 or alpha <= 0.01:
        return
    if abs(scale - 1) > 0.01:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
    if angle:
        im = im.rotate(angle, expand=True, resample=Image.BILINEAR)
    if alpha < 0.99:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    frame.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)),
                          ) if 0 <= int(cx - im.width / 2) and 0 <= int(cy - im.height / 2) \
        and int(cx + im.width / 2) < W and int(cy + im.height / 2) < H else _put_clip(frame, im, cx, cy)


def _put_clip(frame, im, cx, cy):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    layer.paste(im, (int(cx - im.width / 2), int(cy - im.height / 2)))
    frame.alpha_composite(layer)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def pop(t, d=0.22):
    """Escala con rebote: 0 -> 1 en d segundos."""
    if t <= 0:
        return 0.0
    x = clamp(t / d)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def slam(t, d=0.16):
    """Sello: entra grande y cae a escala 1."""
    if t <= 0:
        return 0.0
    return 1 + 1.6 * (1 - clamp(t / d)) ** 2


def ease(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


# fondos a baja resolución
LW, LH = 135, 240
GX, GY = np.meshgrid((np.arange(LW) + 0.5) * (W / LW), (np.arange(LH) + 0.5) * (H / LH))
RNG = np.random.default_rng(7)
STARS = Image.new("RGBA", (W, H), (0, 0, 0, 0))
_sd = ImageDraw.Draw(STARS)
for _ in range(260):
    x, y, r = RNG.integers(0, W), RNG.integers(0, H), RNG.choice([1, 1, 2, 2, 3])
    _sd.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, int(RNG.integers(70, 220))))


def glow(cx, cy, s):
    return np.exp(-((GX - cx) ** 2 + (GY - cy) ** 2) / (2 * s * s))


def ring(cx, cy, r, w):
    d = np.sqrt((GX - cx) ** 2 + (GY - cy) ** 2)
    return np.exp(-((d - r) / w) ** 2)


def bg_from(arr):
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").resize((W, H), Image.BILINEAR).convert("RGBA")


def col(c, m):
    return m[..., None] * np.array(c, dtype=np.float32)[None, None, :]


def base(c_top, c_bot):
    g = (GY / H)[..., None]
    return np.array(c_top, np.float32) * (1 - g) + np.array(c_bot, np.float32) * g


def speedlines(frame, cx, cy, inner, color, seed, n=64, alpha=255):
    r = np.random.default_rng(seed)
    d = ImageDraw.Draw(frame, "RGBA")
    for _ in range(n):
        a, dw, ir = r.uniform(0, 2 * math.pi), r.uniform(0.004, 0.022), inner * r.uniform(0.85, 1.5)
        d.polygon([(cx + 2400 * math.cos(a - dw), cy + 2400 * math.sin(a - dw)),
                   (cx + 2400 * math.cos(a + dw), cy + 2400 * math.sin(a + dw)),
                   (cx + ir * math.cos(a), cy + ir * math.sin(a))], fill=color + (alpha,))


def burst(d, cx, cy, r1, r2, n, fill, rot=0.0):
    pts = []
    for k in range(2 * n):
        a = rot + math.pi * k / n
        r = r1 if k % 2 == 0 else r2
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(pts, fill=fill)


def check(d, cx, cy, s, color=WHT, w=None):
    w = w or int(s * 0.28)
    d.line([(cx - s, cy), (cx - s * 0.3, cy + s * 0.7), (cx + s, cy - s * 0.7)], fill=color, width=w, joint="curve")


def cross(d, cx, cy, s, color=RED, w=26):
    d.line([(cx - s, cy - s), (cx + s, cy + s)], fill=color, width=w)
    d.line([(cx - s, cy + s), (cx + s, cy - s)], fill=color, width=w)


@lru_cache(None)
def stamp_img(text, size, color, pad=34):
    ti = text_img(text, size, color, 0, color, 860)
    im = Image.new("RGBA", (ti.width + 2 * pad + 24, ti.height + 2 * pad + 24), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((6, 6, im.width - 7, im.height - 7), 26, fill=(0, 0, 0, 150), outline=color, width=14)
    im.alpha_composite(ti, (pad + 12, pad + 12))
    return im


SHAKES = []  # (tiempo global, intensidad, duración)


def shake_at(t):
    dx = dy = 0.0
    for t0, amp, dur in SHAKES:
        if t0 <= t < t0 + dur:
            k = amp * (1 - (t - t0) / dur)
            dx += k * math.sin(t * 91.0)
            dy += k * math.cos(t * 77.0)
    return int(dx), int(dy)


FLASHES = []  # (tiempo global, color, duración)

# ------------------------------------------------------------------ escenas
def collision_bg(tl, t_imp, loop=False):
    """Dos orbes (rojo y morado) que chocan en el centro."""
    cx, cy = W / 2, 820
    p = ease(tl / t_imp) if tl < t_imp else 1.0
    after = max(0.0, tl - t_imp)
    a = base((6, 4, 22), (18, 6, 40))
    off = 620 * (1 - p) + 70
    rx, ry = cx - off, cy + off * 0.25
    px, py = cx + off, cy - off * 0.25
    pulse = 1 + 0.08 * math.sin(tl * 18)
    a += col((255, 50, 40), glow(rx, ry, 150 * pulse)) + col((255, 220, 200), glow(rx, ry, 55))
    a += col((150, 60, 255), glow(px, py, 150 * pulse)) + col((235, 210, 255), glow(px, py, 55))
    if after > 0:
        a += col((255, 255, 255), glow(cx, cy, 120 + 60 * math.sin(tl * 25))) * 0.9
        period = 0.55
        for k in range(4):
            ta = after - k * 0.16
            if loop:
                ta = ta % (period * 2.4)
            if ta > 0:
                r = 2100 * (1 - math.exp(-ta * 1.6))
                a += col((255, 240, 200), ring(cx, cy, r, 26 + r * 0.03)) * clamp(1.4 - ta * 0.6)
    return a, (cx, cy), after


def scene1(t, tl, dur):
    t_imp = wt(0, "puños") - SC_START[1]
    a, (cx, cy), after = collision_bg(tl, t_imp)
    f = bg_from(a)
    f.alpha_composite(STARS)
    if after > 0:
        speedlines(f, cx, cy, 300 + 500 * clamp(after * 3), WHT, int(t * 15), 56, 235)
        d = ImageDraw.Draw(f, "RGBA")
        burst(d, cx, cy, 190 + 20 * math.sin(tl * 40), 90, 12, (255, 255, 255, 255), tl * 2)
    t_q = wt(0, "ya") - SC_START[1]
    put(f, text_img("GOKU DIOS  vs  BEERUS", 64, WHT, 8), W / 2, 300, pop(tl - 0.25), 1)
    if tl > t_q:
        put(f, text_img("¿YA NO ES\nCANON?", 190, YEL, 16), W / 2, 1010, pop(tl - t_q, 0.2), 1, -5)
    return f


def scene2(t, tl, dur):
    a = base((40, 8, 70), (10, 2, 26)) + col((120, 40, 200), glow(W / 2, 780, 520 + 40 * math.sin(tl * 9)))
    f = bg_from(a)
    speedlines(f, W / 2, 780, 520, (20, 4, 40), int(t * 12), 60, 200)
    t2 = wt(1, "Dame") - SC_START[2]
    if tl < t2:
        put(f, text_img("¡POR FAVOR!", 170, WHT, 16), W / 2, 780, pop(tl - 0.05) * (1 + 0.03 * math.sin(tl * 30)), 1, 4)
    else:
        u = tl - t2
        put(f, text_img("TE LO\nDESMONTO", 160, WHT, 16), W / 2, 560, pop(u), 1)
        d = ImageDraw.Draw(f, "RGBA")
        cx, cy, r = W / 2, 1010, 150
        if u > 0.25:
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(0, 0, 0, 170), outline=WHT + (255,), width=10)
            d.pieslice((cx - r + 18, cy - r + 18, cx + r - 18, cy + r - 18), -90, -90 + 360 * clamp((u - 0.25) / 1.6),
                       fill=YEL + (255,))
            put(f, text_img("40 s", 96, WHT, 10), cx, cy, pop(u - 0.3), 1)
    return f


def card(d, box, tag, tagcol):
    d.rounded_rectangle(box, 36, fill=(14, 18, 44, 235), outline=tagcol + (255,), width=8)


def scene3(t, tl, dur):
    a = base((8, 14, 46), (4, 6, 20)) + col((40, 70, 200), glow(W / 2, 300, 600))
    f = bg_from(a)
    d = ImageDraw.Draw(f, "RGBA")
    t_b = SEG_START[3] - SC_START[3]
    if tl < t_b:
        put(f, label_img("EL RUMOR", 84, BLK, YEL), W / 2, 560, pop(tl - 0.05), 1, -3)
        u = tl - (wt(2, "Dragon") - SC_START[3])
        put(f, text_img("DRAGON BALL SUPER:", 86, WHT, 12), W / 2, 780, pop(u), 1)
        put(f, text_img("BEERUS", 210, PUR, 16, WHT), W / 2, 960, pop(u - 0.35), 1)
        put(f, text_img("REMAKE 2026", 60, WHT, 8), W / 2, 1130, pop(u - 0.6), 1)
        return f
    u = tl - t_b
    put(f, label_img("CAPÍTULO 5", 92, BLK, YEL), W / 2, 330, pop(u), 1, -2)
    # tarjeta 1: anime 2015
    s1 = ease(u / 0.35)
    y1 = 470 + (1 - s1) * 80
    if s1 > 0:
        card(d, (80, y1, 1000, y1 + 330), "", GRN)
        put(f, label_img("ANIME 2015", 46, BLK, GRN, pad=16, radius=14), 250, y1, 1, s1)
        put(f, text_img("LOS KAIOSHIN AVISAN:\n«¡EL UNIVERSO PELIGRA!»", 60, WHT, 0, maxw=700, path=F_BOLD), 470, y1 + 175, 1, s1)
        d.ellipse((835, y1 + 105, 965, y1 + 235), fill=GRN + (int(255 * s1),))
        check(d, 900, y1 + 172, 38)
    # tarjeta 2: remake
    u2 = u - 0.5
    s2 = ease(u2 / 0.35)
    y2 = 850 + (1 - s2) * 80
    if s2 > 0:
        card(d, (80, y2, 1000, y2 + 330), "", RED)
        put(f, label_img("REMAKE 2026", 46, WHT, RED, pad=16, radius=14), 260, y2, 1, s2)
        put(f, text_img("LOS KAIOSHIN AVISAN:\n«¡EL UNIVERSO PELIGRA!»", 60, (120, 126, 150), 0, maxw=700, path=F_BOLD),
            470, y2 + 175, 1, s2)
        uc = tl - (wt(3, "desaparecen") - SC_START[3])
        if uc > 0:
            k = ease(uc / 0.25)
            d.line([(130, y2 + 150), (130 + 680 * k, y2 + 150)], fill=RED + (255,), width=14)
            d.line([(130, y2 + 215), (130 + 680 * k, y2 + 215)], fill=RED + (255,), width=14)
            cross(d, 900, y2 + 172, 46 * clamp(pop(uc - 0.1)))
            put(f, stamp_img("ESCENA RECORTADA", 84, RED), W / 2, y2 + 175, slam(uc - 0.3), clamp((uc - 0.3) * 20), -8)
    return f


COMMENTS = [("¡LO BORRARON\nDEL CANON!", 540, 760, 92, RED, 0.0), ("ya no cuenta...", 330, 420, 56, (90, 170, 255), 0.25),
            ("RIP Goku Dios", 760, 560, 56, (255, 160, 60), 0.5), ("entonces nunca pasó??", 420, 1010, 54, (120, 230, 140), 0.75),
            ("el remake lo cambió TODO", 600, 1150, 54, (230, 120, 255), 1.0), ("adiós al choque de puños", 480, 280, 52, (255, 220, 80), 1.2)]


@lru_cache(None)
def bubble_img(text, size, accent, big):
    ti = text_img(text, size, BLK if not big else WHT, 0, BLK, 820, F_BLACK if big else F_BOLD)
    pad, av = 30, (0 if big else 64)
    im = Image.new("RGBA", (ti.width + 2 * pad + av + (16 if av else 0), max(ti.height, av) + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, im.width - 1, im.height - 1), 34, fill=(RED if big else (245, 245, 250)), outline=BLK, width=6)
    if av:
        d.ellipse((pad, pad, pad + av, pad + av), fill=accent)
    im.alpha_composite(ti, (pad + av + (16 if av else 0), (im.height - ti.height) // 2))
    return im


def scene4(t, tl, dur):
    a = base((30, 6, 14), (8, 4, 18)) + col((200, 30, 50), glow(W / 2, 760, 560 + 50 * math.sin(tl * 12)))
    f = bg_from(a)
    t_q = wt(4, "«¡lo") - SC_START[4]
    for k, (txt, x, y, size, acc, dt) in enumerate(COMMENTS[1:]):
        u = tl - 0.1 - dt * 0.7
        put(f, bubble_img(txt, size, acc, False), x + 6 * math.sin(tl * 7 + k), y + 6 * math.cos(tl * 6 + k * 2), pop(u), 1,
            (-4, 3, -2, 4, -3)[k])
    u = tl - t_q
    txt, x, y, size, acc, _ = COMMENTS[0]
    put(f, bubble_img(txt, 110, acc, True), x, y, pop(u, 0.18) * (1 + 0.025 * math.sin(tl * 34)), 1, -4)
    return f


def scene5(t, tl, dur):
    t2 = SEG_START[6] - SC_START[5]
    f = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    if tl < t2:
        put(f, text_img("PUES NO.", 230, WHT, 0), W / 2, 800, slam(tl - 0.05, 0.14), 1)
        d = ImageDraw.Draw(f, "RGBA")
        d.rectangle((140, 960, 140 + 800 * ease((tl - 0.15) / 0.2), 984), fill=RED + (255,))
        return f
    u = tl - t2
    f = bg_from(base((20, 16, 4), (4, 4, 4)) + col((120, 100, 0), glow(W / 2, 800, 520)))
    put(f, text_img("RECORTAR", 170, WHT, 14), W / 2, 560, pop(u - 0.05), 1)
    put(f, text_img("≠", 300, RED, 14, WHT, path=F_BOLD), W / 2, 800, pop(u - (wt(6, "no") - SEG_START[6])), 1)
    put(f, label_img("BORRAR", 170, BLK, YEL), W / 2, 1060, pop(u - (wt(6, "borra") - SEG_START[6])), 1, -3)
    return f


@lru_cache(None)
def page_img():
    """Página de manga genérica (viñetas vacías)."""
    im = Image.new("RGBA", (620, 860), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, 619, 859), 10, fill=(250, 248, 240), outline=BLK, width=6)
    for box, g in [((30, 30, 590, 300), 200), ((30, 320, 290, 560), 225), ((310, 320, 590, 560), 170),
                   ((30, 580, 590, 830), 210)]:
        d.rectangle(box, fill=(g, g, g), outline=BLK, width=6)
    r = np.random.default_rng(3)
    for _ in range(40):
        a = r.uniform(0, 6.28)
        d.line([(310, 165), (310 + 400 * math.cos(a), 165 + 400 * math.sin(a))], fill=(60, 60, 60), width=2)
    d.rectangle((0, 0, 30, 859), fill=(250, 248, 240))
    d.rectangle((590, 0, 619, 859), fill=(250, 248, 240))
    d.rectangle((30, 300, 590, 320), fill=(250, 248, 240))
    d.rounded_rectangle((0, 0, 619, 859), 10, outline=BLK, width=6)
    d.rectangle((30, 30, 590, 300), outline=BLK, width=6)
    burst(d, 310, 165, 95, 45, 10, WHT)
    d.ellipse((380, 600, 560, 700), fill=WHT, outline=BLK, width=5)
    d.ellipse((60, 350, 200, 430), fill=WHT, outline=BLK, width=5)
    return im


def scene6(t, tl, dur):
    a = base((26, 16, 6), (6, 4, 2)) + col((255, 190, 90), glow(W / 2, 860, 480)) * 0.75
    f = bg_from(a)
    t2 = SEG_START[8] - SC_START[6]
    if tl < t2:
        put(f, label_img("LA PRUEBA", 170, BLK, YEL), W / 2, 780, slam(tl - 0.05), 1, -4)
        return f
    u = tl - t2
    k = ease(u / 0.45)
    put(f, page_img(), W / 2 - 230 + 0 * k, 900 + (1 - k) * 900, 0.9, 1, 7)
    put(f, page_img(), W / 2 + 190, 880 + (1 - k) * 1100, 0.95, 1, -5)
    put(f, text_img("MANGA", 150, WHT, 16), W / 2, 270, pop(u), 1)
    put(f, label_img("CAPÍTULO 4", 120, BLK, YEL), W / 2, 450, pop(tl - (wt(8, "capítulo") - SC_START[6])), 1, -2)
    put(f, label_img("DIBUJO: TOYOTARO", 62, WHT, (20, 20, 20), radius=16), W / 2, 880,
        pop(tl - (wt(8, "dibujado") - SC_START[6])), 1)
    put(f, label_img("HISTORIA: AKIRA TORIYAMA", 62, WHT, (20, 20, 20), radius=16), W / 2, 1010,
        pop(tl - (wt(8, "historia") - SC_START[6])), 1)
    return f


def scene7(t, tl, dur):
    """Viñeta en blanco y negro: impacto y ondas que llegan a un planeta."""
    f = Image.new("RGBA", (W, H), (246, 244, 236, 255))
    cx, cy = 430, 930
    t_imp = wt(9, "chocan") - SC_START[7]
    t_wave = wt(9, "ondas") - SC_START[7]
    t_pl = wt(9, "planeta") - SC_START[7]
    d = ImageDraw.Draw(f, "RGBA")
    speedlines(f, cx, cy, 330, BLK, int(t * 10), 80, 255)
    # dos cuñas que chocan
    p = ease(tl / t_imp)
    off = 700 * (1 - p)
    for sgn in (-1, 1):
        x0 = cx + sgn * (off + 40)
        d.polygon([(x0, cy), (x0 + sgn * 520, cy - 150 - sgn * 60), (x0 + sgn * 520, cy + 150 - sgn * 60)], fill=BLK)
    if tl > t_imp:
        u = tl - t_imp
        burst(d, cx, cy, 250 + 25 * math.sin(tl * 40), 110, 14, BLK + (255,), tl)
        burst(d, cx, cy, 190 + 25 * math.sin(tl * 40), 80, 14, WHT + (255,), tl)
    if tl > t_wave:
        u = tl - t_wave
        for k in range(5):
            r = (u - k * 0.22) * 900
            if r > 0:
                d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=BLK + (255,), width=max(4, int(22 - r * 0.008)))
    # planeta
    px, py = 860, 520
    k = ease((tl - t_wave) / 0.3)
    if k > 0:
        hit = tl > t_pl
        jx = 10 * math.sin(tl * 60) if hit else 0
        r = 95 * k
        d.ellipse((px - r + jx, py - r, px + r + jx, py + r), fill=(205, 205, 205, 255), outline=BLK + (255,), width=8)
        d.ellipse((px - r * 1.7 + jx, py - r * 0.28, px + r * 1.7 + jx, py + r * 0.28), outline=BLK + (255,), width=7)
        put(f, label_img("PLANETA DE LOS KAIOSHIN", 34, WHT, BLK, pad=14, radius=10), 760, 670, pop(tl - t_pl), 1)
    # borde de viñeta
    d.rectangle((24, 150, W - 24, 1500), outline=BLK + (255,), width=16)
    d.rectangle((0, 0, W, 150), fill=BLK + (255,))
    d.rectangle((0, 1500, W, H), fill=BLK + (255,))
    put(f, text_img("CHOQUE DE PUÑOS", 104, WHT, 14), W / 2, 290, pop(tl - t_imp), 1)
    put(f, label_img("ESTÁ EN EL MANGA", 84, BLK, GRN), W / 2, 1180, pop(tl - t_wave - 0.3), 1, -2)
    return f


CRACKS = []
_r = np.random.default_rng(11)
for _ in range(11):
    a, pts, x, y = _r.uniform(0, 6.28), [], W / 2, 560.0
    pts.append((x, y))
    for _s in range(9):
        a += _r.uniform(-0.6, 0.6)
        step = _r.uniform(90, 190)
        x, y = x + step * math.cos(a), y + step * math.sin(a)
        pts.append((x, y))
    CRACKS.append(pts)


def scene8(t, tl, dur):
    t2 = SEG_START[11] - SC_START[8]
    a = base((6, 4, 26), (22, 4, 34)) + col((255, 60, 60), glow(W / 2, 560, 300 + 80 * clamp(tl - t2)))
    f = bg_from(a)
    f.alpha_composite(STARS)
    d = ImageDraw.Draw(f, "RGBA")
    if tl < t2:
        put(f, text_img("¿QUÉ DICE EL", 100, WHT, 14), W / 2, 620, pop(tl - 0.05), 1)
        put(f, label_img("KAIOSHIN ANCIANO?", 96, BLK, YEL), W / 2, 790, pop(tl - 0.3), 1, -2)
        return f
    u = tl - t2
    if tl < wt(11, "Siete") - SC_START[8]:
        put(f, label_img("KAIOSHIN ANCIANO:", 76, BLK, YEL), W / 2, 330, 1, 1, -2)
    g = clamp(u / (dur - t2) * 1.3)
    for pts in CRACKS:
        n = g * (len(pts) - 1)
        seg = pts[:int(n) + 1]
        if int(n) + 1 < len(pts):
            p0, p1 = pts[int(n)], pts[int(n) + 1]
            fr = n - int(n)
            seg = seg + [(p0[0] + (p1[0] - p0[0]) * fr, p0[1] + (p1[1] - p0[1]) * fr)]
        if len(seg) > 1:
            d.line(seg, fill=(255, 255, 255, 255), width=9, joint="curve")
            d.line(seg, fill=(255, 190, 120, 255), width=3, joint="curve")
    # globo de diálogo
    s = pop(u - (wt(11, "universo") - SEG_START[11]) + 0.15)
    if s > 0:
        bw, bh = 470 * s, 250 * s
        bx, by = W / 2, 930
        d.polygon([(bx - 60 * s, by + bh - 30), (bx - 230 * s, by + bh + 110 * s), (bx + 40 * s, by + bh - 20)], fill=WHT + (255,),
                  outline=BLK + (255,))
        d.ellipse((bx - bw, by - bh, bx + bw, by + bh), fill=WHT + (255,), outline=BLK + (255,), width=10)
        put(f, text_img("¡EL UNIVERSO\nSE DESMORONA!", 100, BLK, 0, maxw=800), bx, by, s, 1)
        put(f, label_img("KAIOSHIN ANCIANO · CAP. 4 (PARÁFRASIS)", 34, WHT, (30, 30, 30), pad=14, radius=10), W / 2, 1238, 1, clamp(u * 3))
    put(f, label_img("UNIVERSO 7 EN PELIGRO", 76, WHT, RED), W / 2, 330, pop(tl - (wt(11, "Siete") - SC_START[8])), 1, -2)
    return f


def scene9(t, tl, dur):
    a = base((34, 30, 22), (10, 8, 6)) + col((150, 130, 90), glow(W / 2, 800, 600))
    f = bg_from(a)
    put(f, page_img(), W / 2, 820, 1.45, 0.22, -6)
    put(f, stamp_img("IMPRESO.", 150, WHT), W / 2, 500, slam(tl - (wt(12, "impreso") - SC_START[9])),
        clamp((tl - (wt(12, "impreso") - SC_START[9])) * 20), -4)
    put(f, stamp_img("TOMO 1.", 150, YEL), W / 2, 790, slam(tl - (wt(12, "tomo") - SC_START[9])),
        clamp((tl - (wt(12, "tomo") - SC_START[9])) * 20), 3)
    put(f, stamp_img("INTACTO.", 150, GRN), W / 2, 1080, slam(tl - (wt(13, "nadie") - SC_START[9])),
        clamp((tl - (wt(13, "nadie") - SC_START[9])) * 20), -5)
    return f


def scene10(t, tl, dur):
    a, (cx, cy), after = collision_bg(tl + 5, 0.01, loop=True)
    f = bg_from(a)
    f.alpha_composite(STARS)
    speedlines(f, cx, cy, 620, WHT, int(t * 12), 44, 150)
    t_c = wt(14, "canon") - SC_START[10]
    t2 = SEG_START[15] - SC_START[10]
    if tl < t2:
        put(f, text_img("SIGUE SIENDO", 110, WHT, 14), W / 2, 500, pop(tl - (wt(14, "sigue") - SC_START[10])), 1)
        put(f, stamp_img("CANON", 250, GRN, 40), W / 2, 820, slam(tl - t_c), clamp((tl - t_c) * 20), -10)
    else:
        u = tl - t2
        put(f, stamp_img("CANON", 150, GRN, 30), W / 2, 380, 1, 1, -6)
        put(f, text_img("EL ANIME\nRECORTÓ", 130, WHT, 14), W / 2, 720, pop(u), 1)
        put(f, label_img("EL MANGA MANDA", 108, BLK, YEL), W / 2, 1050, pop(tl - (wt(15, "manga") - SC_START[10])), 1, -3)
    return f


def scene11(t, tl, dur):
    f = bg_from(base((30, 90, 240), (10, 40, 150)))
    d = ImageDraw.Draw(f, "RGBA")
    d.polygon([(0, 950), (W, 570), (W, H), (0, H)], fill=(240, 110, 20, 255))
    d.line([(0, 950), (W, 570)], fill=BLK + (255,), width=16)
    t2 = SEG_START[17] - SC_START[11]
    if tl < t2 + 0.12:
        put(f, text_img("¿REMAKE", 150, WHT, 16), 400, 430, pop(tl - (wt(16, "remake") - SC_START[11])), 1, -4)
        put(f, text_img("MANGA?", 150, WHT, 16), 690, 1080, pop(tl - (wt(16, "manga") - SC_START[11])), 1, -4)
        s = pop(tl - (wt(16, "o") - SC_START[11]) + 0.1)
        if s > 0:
            d.ellipse((W / 2 - 110 * s, 760 - 110 * s, W / 2 + 110 * s, 760 + 110 * s), fill=BLK + (255,), outline=YEL + (255,), width=10)
            put(f, text_img("VS", 110, YEL, 0), W / 2, 760, s, 1)
    if tl > t2:
        u = tl - t2
        f.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(190 * clamp(u * 6)))))
        put(f, label_img("COMENTA", 150, BLK, YEL), W / 2, 560, pop(u), 1, -3)
        by = 800 + 26 * abs(math.sin(tl * 7))
        if u > 0.2:
            d.polygon([(W / 2 - 90, by), (W / 2 + 90, by), (W / 2, by + 120)], fill=YEL + (255,), outline=BLK + (255,))
            d.rectangle((W / 2 - 34, by - 90, W / 2 + 34, by + 4), fill=YEL + (255,))
        us = tl - (wt(17, "sígueme") - SC_START[11])
        put(f, label_img("+ SÍGUEME", 120, WHT, RED, radius=70, pad=40), W / 2, 1130, pop(us) * (1 + 0.03 * math.sin(tl * 12)), 1)
    return f


SCENE_FN = {1: scene1, 2: scene2, 3: scene3, 4: scene4, 5: scene5, 6: scene6, 7: scene7, 8: scene8, 9: scene9, 10: scene10,
            11: scene11}

# golpes de cámara y destellos
SHAKES += [(wt(0, "puños"), 26, 0.5), (SC_START[2], 14, 0.3), (wt(3, "desaparecen") + 0.3, 16, 0.3), (wt(4, "«¡lo"), 14, 0.4),
           (SEG_START[5], 22, 0.3), (SEG_START[7], 16, 0.3), (wt(9, "chocan"), 28, 0.5), (wt(9, "planeta"), 14, 0.6),
           (wt(11, "desmorona"), 18, 0.7), (wt(12, "impreso"), 16, 0.25), (wt(12, "tomo"), 16, 0.25), (wt(13, "nadie"), 20, 0.3),
           (wt(14, "canon"), 26, 0.4)]
FLASHES += [(wt(0, "puños"), WHT, 0.16), (wt(9, "chocan"), WHT, 0.14), (SEG_START[5], RED, 0.12), (wt(14, "canon"), WHT, 0.12)]
FLASHES += [(SC_START[s], WHT, 0.09) for s in SCENES[1:]]


def captions(f, t):
    for ch in CHUNKS:
        if ch[0][1] - 0.03 <= t < ch[-1][2] + 0.1:
            ims = [text_img(w.upper(), 76, YEL if a <= t < b + 0.02 else WHT, 10, BLK, 900) for w, a, b in ch]
            gap = 22
            tw = sum(i.width for i in ims) + gap * (len(ims) - 1)
            sc = min(1.0, 960 / tw) * (0.85 + 0.15 * clamp((t - ch[0][1] + 0.03) / 0.08))
            x = W / 2 - tw * sc / 2
            for im in ims:
                put(f, im, x + im.width * sc / 2, 1370, sc, 1)
                x += (im.width + gap) * sc
            return


def render(t):
    s = SCENES[0]
    for k in SCENES:
        if SC_START[k] <= t:
            s = k
    f = SCENE_FN[s](t, t - SC_START[s], SC_END[s] - SC_START[s])
    dx, dy = shake_at(t)
    if dx or dy:
        f = ImageChops.offset(f, dx, dy)
    for t0, c, dur in FLASHES:
        if t0 <= t < t0 + dur:
            ov = Image.new("RGBA", (W, H), c + (int(215 * (1 - (t - t0) / dur)),))
            f.alpha_composite(ov)
    captions(f, t)
    return f.convert("RGB")


# ------------------------------------------------------------------ audio
def env(n, a=0.005, decay=6.0):
    x = np.arange(n) / SR
    return np.minimum(1, x / a) * np.exp(-x * decay)


def sweep(f0, f1, dur, shape=1.0):
    x = np.linspace(0, 1, int(dur * SR)) ** shape
    return np.sin(2 * np.pi * np.cumsum(f0 * (f1 / f0) ** x) / SR)


def noise(dur):
    return np.random.default_rng(int(dur * 1e4) + 5).uniform(-1, 1, int(dur * SR))


def lowpass(x, fc):
    X = np.fft.rfft(x)
    fr = np.fft.rfftfreq(len(x), 1 / SR)
    return np.fft.irfft(X / (1 + (fr / fc) ** 4), len(x))


def highpass(x, fc):
    return x - lowpass(x, fc)


def sfx_boom():
    n = int(1.1 * SR)
    return np.tanh(2.2 * sweep(110, 32, 1.1, 0.5) * env(n, 0.003, 3.5)) * 0.9 + lowpass(noise(1.1), 900) * env(n, 0.002, 9) * 0.8


def sfx_whoosh(dur=0.45):
    n = int(dur * SR)
    x = np.linspace(0, 1, n)
    return highpass(lowpass(noise(dur), 2600), 300) * np.sin(np.pi * x) ** 2 * 1.4


def sfx_scratch():
    n = int(0.42 * SR)
    x = np.linspace(0, 1, n)
    car = np.sin(2 * np.pi * np.cumsum(900 * (1 - x) ** 1.5 + 120) / SR)
    return (car * 0.6 + highpass(noise(0.42), 1500) * 0.5) * (1 - x) ** 0.7 * (0.6 + 0.4 * np.sign(np.sin(40 * x)))


def sfx_buzzer():
    n = int(0.4 * SR)
    x = np.arange(n) / SR
    return lowpass(np.sign(np.sin(2 * np.pi * 98 * x)) + np.sign(np.sin(2 * np.pi * 104 * x)), 1800) * 0.4 * np.minimum(1, (0.4 - x) * 25)


def sfx_ding():
    n = int(0.9 * SR)
    x = np.arange(n) / SR
    return sum(np.sin(2 * np.pi * f * x) * a for f, a in [(1320, 0.5), (2640, 0.25), (3960, 0.12)]) * env(n, 0.002, 5)


def sfx_pop(f=700):
    return sweep(f, f * 1.7, 0.07) * env(int(0.07 * SR), 0.002, 30) * 0.8


def sfx_stamp():
    n = int(0.35 * SR)
    return np.tanh(3 * sweep(150, 45, 0.35, 0.5) * env(n, 0.002, 11)) * 0.9 + lowpass(noise(0.35), 3000) * env(n, 0.001, 30) * 0.7


def sfx_snip():
    c = highpass(noise(0.05), 3000) * env(int(0.05 * SR), 0.001, 70)
    out = np.zeros(int(0.3 * SR))
    out[:len(c)] += c
    out[int(0.11 * SR):int(0.11 * SR) + len(c)] += c * 0.9
    return out


def sfx_page():
    n = int(0.3 * SR)
    x = np.linspace(0, 1, n)
    return highpass(lowpass(noise(0.3), 5000), 1200) * np.sin(np.pi * x) ** 3 * (0.6 + 0.4 * np.sin(60 * x))


def sfx_riser(dur):
    n = int(dur * SR)
    x = np.linspace(0, 1, n)
    return (sweep(180, 1400, dur, 1.6)[:n] * 0.35 + highpass(noise(dur), 1500)[:n] * 0.4) * x ** 2


def sfx_rumble(dur):
    n = int(dur * SR)
    x = np.linspace(0, 1, n)
    return lowpass(noise(dur), 110)[:n] * 5.0 * np.sin(np.pi * x) ** 0.7


def music(total, t_start, t_duck0, t_duck1):
    """Base original estilo phonk: bombo, 808, palmas, hi-hats y cencerro."""
    bpm = 132
    step = 60 / bpm / 4
    out = np.zeros(int(total * SR) + SR)

    def add(buf, tt, g=1.0):
        i = int(tt * SR)
        if i < 0 or i >= len(out):
            return
        e = min(len(out), i + len(buf))
        out[i:e] += buf[:e - i] * g

    kick = np.tanh(3 * sweep(160, 42, 0.28, 0.4) * env(int(0.28 * SR), 0.002, 9))
    clap = highpass(lowpass(noise(0.14), 4500), 900) * env(int(0.14 * SR), 0.001, 26)
    hat = highpass(noise(0.04), 7000) * env(int(0.04 * SR), 0.001, 90)
    notes808 = {0: 43.65, 6: 43.65, 10: 51.91, 16: 43.65, 22: 38.89, 26: 43.65, 28: 51.91}
    bell_seq = [698.5, 0, 698.5, 830.6, 0, 698.5, 622.3, 0, 698.5, 0, 523.3, 0, 622.3, 0, 698.5, 830.6]

    def bell(fq):
        n = int(0.2 * SR)
        x = np.arange(n) / SR
        return lowpass(np.sign(np.sin(2 * np.pi * fq * x)) + 0.7 * np.sign(np.sin(2 * np.pi * fq * 1.5 * x)), 5000) * env(n, 0.001, 16)

    def bass(fq):
        n = int(0.5 * SR)
        x = np.arange(n) / SR
        return np.tanh(2.5 * np.sin(2 * np.pi * fq * x) * env(n, 0.004, 4.5))

    bells = {fq: bell(fq) for fq in set(bell_seq) if fq}
    basses = {fq: bass(fq) for fq in set(notes808.values())}
    k = 0
    while t_start + k * step < total:
        tt, s32, s16 = t_start + k * step, k % 32, k % 16
        if s32 in notes808:
            add(kick, tt, 0.9)
            add(basses[notes808[s32]], tt, 0.75)
        if s16 in (4, 12):
            add(clap, tt, 0.55)
        if k % 2 == 0 or s16 in (13, 15):
            add(hat, tt, 0.22 if k % 4 else 0.3)
        if bell_seq[s16]:
            add(bells[bell_seq[s16]], tt, 0.2)
        k += 1
    tt = np.arange(len(out)) / SR
    gain = np.where((tt > t_duck0) & (tt < t_duck1), 0.6, 1.0)
    gain = lowpass(gain, 3) if False else np.convolve(gain, np.ones(4410) / 4410, "same")
    gain[tt < t_start] = 0
    gain *= np.clip((total - 0.25 - tt) * 12, 0, 1)
    return (out * gain)[:int(total * SR)]


def build_audio(path):
    n = int(TOTAL * SR)
    voice, fx = np.zeros(n), np.zeros(n)

    def add(buf, tt, g=1.0, dst=None):
        dst = fx if dst is None else dst
        i = max(0, int(tt * SR))
        e = min(n, i + len(buf))
        if e > i:
            dst[i:e] += buf[:e - i] * g

    for i in range(len(SEGMENTS)):
        with wave.open(f"{BUILD}/tts/seg{i:02d}.wav") as w:
            x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768
        add(x, SEG_START[i], 1.0, voice)
    voice *= 0.92 / max(1e-6, np.abs(voice).max())

    add(sfx_whoosh(0.5), wt(0, "puños") - 0.5, 0.5)
    add(sfx_boom(), wt(0, "puños"), 0.75)
    add(sfx_scratch(), wt(0, "ya") - 0.1, 0.35)
    add(sfx_whoosh(0.35), SC_START[2] - 0.2, 0.5)
    add(sfx_boom(), SC_START[2], 0.5)
    add(sfx_pop(), wt(1, "Dame"), 0.4)
    add(sfx_whoosh(0.3), SC_START[3] - 0.15, 0.4)
    add(sfx_pop(600), wt(2, "Dragon"), 0.35)
    add(sfx_whoosh(0.3), SEG_START[3] - 0.1, 0.4)
    add(sfx_pop(500), SEG_START[3] + 0.5, 0.35)
    add(sfx_snip(), wt(3, "desaparecen"), 0.6)
    add(sfx_stamp(), wt(3, "desaparecen") + 0.3, 0.6)
    for k, c in enumerate(COMMENTS[1:]):
        add(sfx_pop(650 + 90 * k), SC_START[4] + 0.1 + c[5] * 0.7, 0.3)
    add(sfx_stamp(), wt(4, "«¡lo"), 0.5)
    add(sfx_buzzer(), SEG_START[5] - 0.02, 0.5)
    add(sfx_pop(500), SEG_START[6] + 0.05, 0.3)
    add(sfx_stamp(), wt(6, "borra"), 0.5)
    add(sfx_stamp(), SEG_START[7], 0.6)
    add(sfx_page(), SEG_START[8], 0.7)
    add(sfx_page(), SEG_START[8] + 0.25, 0.6)
    add(sfx_pop(700), wt(8, "capítulo"), 0.35)
    add(sfx_pop(600), wt(8, "dibujado"), 0.3)
    add(sfx_pop(650), wt(8, "historia"), 0.3)
    rd = wt(9, "chocan") - (SC_START[7] - 1.0)
    add(sfx_riser(rd), SC_START[7] - 1.0, 0.3)
    add(sfx_boom(), wt(9, "chocan"), 0.85)
    add(sfx_rumble(SC_END[7] - wt(9, "ondas")), wt(9, "ondas"), 0.5)
    add(sfx_pop(550), wt(9, "ondas") + 0.3, 0.3)
    add(sfx_whoosh(0.3), SC_START[8] - 0.1, 0.4)
    add(sfx_ding(), wt(11, "universo") - 0.15, 0.35)
    add(sfx_stamp(), wt(11, "Siete"), 0.5)
    add(sfx_rumble(1.2), wt(11, "desmorona") - 0.2, 0.6)
    add(sfx_stamp(), wt(12, "impreso"), 0.65)
    add(sfx_stamp(), wt(12, "tomo"), 0.65)
    add(sfx_stamp(), wt(13, "nadie"), 0.75)
    add(sfx_whoosh(0.3), SC_START[10] - 0.15, 0.4)
    add(sfx_boom(), wt(14, "canon"), 0.8)
    add(sfx_pop(600), SEG_START[15], 0.3)
    add(sfx_stamp(), wt(15, "manga"), 0.5)
    add(sfx_whoosh(0.3), SC_START[11] - 0.15, 0.4)
    add(sfx_pop(600), wt(16, "remake"), 0.35)
    add(sfx_pop(800), wt(16, "manga"), 0.35)
    add(sfx_pop(900), SEG_START[17], 0.4)
    add(sfx_ding(), wt(17, "sígueme"), 0.3)
    add(sfx_whoosh(0.4), TOTAL - 0.55, 0.5)

    mus = music(TOTAL, SC_START[2], SC_START[6], SC_START[10])
    # la música baja cuando hay voz
    lvl = np.convolve(np.abs(voice), np.ones(6000) / 6000, "same")
    duck = 1 - 0.45 * np.clip(lvl * 12, 0, 1)
    mix = voice * 1.0 + fx * 0.55 + mus * 0.2 * duck
    mix = np.tanh(mix * 1.15)
    mix *= 0.95 / np.abs(mix).max()
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())


# ------------------------------------------------------------------ main
if __name__ == "__main__":
    print(f"duración total: {TOTAL:.2f}s")
    for s in SCENES:
        print(f"  escena {s:2d}: {SC_START[s]:6.2f} - {SC_END[s]:6.2f}")
    if SHEET:
        times = []
        for s in SCENES:
            a, b = SC_START[s], SC_END[s]
            times += [a + (b - a) * 0.45, b - 0.12]
        thumbs = [render(tt).resize((270, 480), Image.BILINEAR) for tt in times]
        cols = 8
        sheet = Image.new("RGB", (cols * 270, ((len(thumbs) + cols - 1) // cols) * 480))
        for k, th in enumerate(thumbs):
            sheet.paste(th, ((k % cols) * 270, (k // cols) * 480))
        sheet.save(OUT)
        sys.exit()
    wav = f"{BUILD}/mix.wav"
    build_audio(wav)
    nframes = int(TOTAL * FPS)
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                           "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                           "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
                           "-movflags", "+faststart", "-shortest", OUT], stdin=subprocess.PIPE)
    for k in range(nframes):
        ff.stdin.write(render(k / FPS).tobytes())
        if k % 150 == 0:
            print(f"  frame {k}/{nframes}", flush=True)
    ff.stdin.close()
    ff.wait()
    print("listo:", OUT)
