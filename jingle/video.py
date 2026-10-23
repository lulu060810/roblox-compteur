"""Rendu vidéo du jingle de manche (texte via la variable TITRE, défaut "MANCHE 1") : 1920x1080, 60 FPS, 5 s."""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS, DUR = 1920, 1080, 60, 5.0
NF = int(FPS * DUR)
HERE = sys.path[0]
U = 2  # sur-échantillonnage de la source pour des zooms nets
FINAL = os.environ.get("THEME") == "final"  # thème "boss final" : enfer rouge/orange et or

# ---------------------------------------------------------------- source
src0 = Image.open(f"{HERE}/source.png").convert("RGB")
SW0, SH0 = src0.size
src_big = src0.resize((SW0 * U, SH0 * U), Image.LANCZOS).filter(ImageFilter.UnsharpMask(2, 60, 2))
SRC = np.asarray(src_big).astype(np.float32)
SH, SW = SRC.shape[:2]

# repères dans l'image d'origine (px)
FACE = (850, 345)
EYES = [(832, 346), (925, 344)]
WEBS = [((480, 150), 175), ((75, 335), 145), ((975, 95), 45), ((1465, 410), 75), ((545, 700), 210)]


def ease_out_expo(x):
    return 1 if x >= 1 else 1 - 2 ** (-10 * x)


def ease_in_cubic(x):
    return x ** 3


def ease_out_back(x, s=2.2):
    x -= 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def clamp01(x):
    return max(0.0, min(1.0, x))


def lerp(a, b, x):
    return a + (b - a) * x


# --------------------------------------------------------------- caméra
def camera(t):
    """Retourne (centre_x, centre_y, largeur_vue) en px de l'image d'origine."""
    if t < 1.0:
        k = ease_out_expo(t / 1.0)
        return lerp(816, 838, k), lerp(481, 440, k), lerp(1570, 1240, k)
    if t < 1.15:  # bond brusque du monstre
        k = ease_out_back(clamp01((t - 1.0) / 0.15), 1.6)
        return lerp(838, 845, k), lerp(440, 400, k), lerp(1240, 960, k)
    if t < 1.75:
        k = (t - 1.15) / 0.6
        return 845, lerp(400, 390, k), lerp(960, 870, k)
    if t < 2.0:  # charge finale sur la caméra
        k = ease_in_cubic((t - 1.75) / 0.25)
        return lerp(845, FACE[0], k), lerp(390, FACE[1] + 10, k), lerp(870, 430, k)
    if t < 4.7:  # plan large derrière le titre, push lent
        k = (t - 2.0) / 2.7
        return 845, lerp(520, 490, k), lerp(1010, 880, k)
    k = (t - 4.7) / 0.3
    k = k ** 3
    return lerp(845, FACE[0], k), lerp(490, 400, k), lerp(880, 380, k)


def shake_amount(t):
    a = 2.0
    if 1.0 <= t < 1.3:
        a += 22 * math.exp(-(t - 1.0) * 10)
    if 1.15 <= t < 2.0:
        a += 5 + 6 * clamp01((t - 1.15) / 0.85)
    if t >= 2.0:
        a += 34 * math.exp(-(t - 2.0) * 5.5)
    if t >= 4.2:
        a += 14 * math.exp(-(t - 4.2) * 9)
    if t < 0.4:
        a += 6 * (1 - t / 0.4)
    return a * (1.25 if FINAL else 1.0)


def shake(t, seed):
    r = np.random.default_rng(seed)
    ph = r.uniform(0, 2 * math.pi, 6)
    fr = r.uniform(13, 29, 6)
    sx = sum(math.sin(2 * math.pi * fr[i] * t + ph[i]) for i in range(3)) / 3
    sy = sum(math.sin(2 * math.pi * fr[i] * t + ph[i]) for i in range(3, 6)) / 3
    return sx, sy


def render_view(img, cx, cy, vw, t):
    a = shake_amount(t)
    sx, sy = shake(t, 11)
    rot = math.radians(sx * a * 0.035)
    vw = min(vw, SW0 * 0.985)
    vh = vw * H / W
    cx = min(max(cx, vw / 2 + 4), SW0 - vw / 2 - 4)
    cy = min(max(cy, vh / 2 + 4), SH0 - vh / 2 - 4)
    s = vw * U / W
    cxu = cx * U + sx * a * s
    cyu = cy * U + sy * a * s
    c, si = math.cos(rot) * s, math.sin(rot) * s
    data = (c, -si, cxu - c * W / 2 + si * H / 2, si, c, cyu - si * W / 2 - c * H / 2)
    return img.transform((W, H), Image.AFFINE, data, resample=Image.BICUBIC)


# ------------------------------------------------- toiles qui vibrent
def web_energy(t):
    e = 0.6 * math.exp(-t * 2.5) + 0.25
    if t >= 1.0:
        e += 1.0 * math.exp(-(t - 1.0) * 4)
    if t >= 2.0:
        e += 1.3 * math.exp(-(t - 2.0) * 3)
    if t >= 4.2:
        e += 0.6 * math.exp(-(t - 4.2) * 5)
    return e


def bilinear(img, xs, ys):
    h, w = img.shape[:2]
    xs = np.clip(xs, 0, w - 1.001)
    ys = np.clip(ys, 0, h - 1.001)
    x0 = xs.astype(np.int32)
    y0 = ys.astype(np.int32)
    fx = (xs - x0)[..., None]
    fy = (ys - y0)[..., None]
    a = img[y0, x0]
    b = img[y0, x0 + 1]
    c = img[y0 + 1, x0]
    d = img[y0 + 1, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def wobble_webs(base, t):
    out = base.copy()
    e = web_energy(t)
    for i, ((wx, wy), r) in enumerate(WEBS):
        r = int(r * U * 1.15)
        cx, cy = wx * U, wy * U
        x0, x1 = max(0, cx - r), min(SW, cx + r)
        y0, y1 = max(0, cy - r), min(SH, cy + r)
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        dx, dy = xx - cx, yy - cy
        d = np.sqrt(dx * dx + dy * dy) / r
        fall = np.clip(1 - d, 0, 1) ** 1.5 * np.clip(d * 4, 0, 1)
        amp = 5.0 * U * e
        ph = i * 1.7
        ox = amp * fall * np.sin(2 * math.pi * 9 * t + ph + d * 6)
        oy = amp * fall * np.cos(2 * math.pi * 7.3 * t + ph * 1.3 + d * 5)
        out[y0:y1, x0:x1] = bilinear(base, xx + ox, yy + oy)
    return out


# --------------------------------------------------- yeux lumineux
def eye_intensity(t):
    k = clamp01((t - 0.25) / 0.35)
    v = k ** 2 * (0.85 + 0.15 * math.sin(t * 40) * math.sin(t * 17))
    if 1.0 <= t < 2.0:
        v *= 1.25
    if t >= 2.0:
        v *= 1.1 + 0.4 * math.exp(-(t - 2.0) * 4)
    if t >= 4.2:
        v += 0.6 * math.exp(-(t - 4.2) * 6)
    return v


def add_eye_glow(img, t):
    v = eye_intensity(t)
    if v <= 0.01:
        return img
    for ex, ey in EYES:
        R = 140 * U
        cx, cy = ex * U, ey * U
        x0, x1, y0, y1 = cx - R * 2, cx + R * 2, cy - R, cy + R
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        dx, dy = (xx - cx) / U, (yy - cy) / U
        d2 = dx * dx + dy * dy
        core = np.exp(-d2 / (2 * 7 ** 2))
        halo = np.exp(-d2 / (2 * 32 ** 2))
        streak = np.exp(-(dy ** 2) / (2 * 2.5 ** 2)) * np.exp(-np.abs(dx) / 110)
        g = (core * 1.0)[..., None] * np.array([255, 210, 190]) + \
            (halo * 0.75)[..., None] * np.array([255, 20, 25]) + \
            (streak * 0.6)[..., None] * np.array([255, 40, 60])
        img[y0:y1, x0:x1] += g * v
    return img


# ------------------------------------------------- éclairages & grading
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
nx, ny = (xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2)
VIGNETTE = np.clip(1 - 0.55 * (nx ** 2 * 0.7 + ny ** 2) ** 1.2, 0, 1)[..., None]
LEAK_RED = np.exp(-(((xx - 0) / 900) ** 2 + ((yy - H) / 650) ** 2))[..., None] * np.array([255, 20, 30], np.float32)
LEAK_VIO = np.exp(-(((xx - W) / 950) ** 2 + ((yy - 0) / 700) ** 2))[..., None] * np.array([150, 40, 255], np.float32)
if FINAL:
    LEAK_RED = np.exp(-(((xx - 0) / 900) ** 2 + ((yy - H) / 650) ** 2))[..., None] * np.array([255, 70, 0], np.float32)
    LEAK_VIO = np.exp(-(((xx - W) / 950) ** 2 + ((yy - 0) / 700) ** 2))[..., None] * np.array([200, 0, 20], np.float32)
FIRE_GLOW = np.exp(-((H - yy) / 260) ** 2)[..., None] * np.array([255, 90, 10], np.float32)
CENTER_DIST = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H / 2) / W) ** 2)


def grade(f, t):
    flick = 0.85 + 0.15 * math.sin(t * 23) * math.sin(t * 7.1)
    dark = lerp(0.55, 0.82, clamp01(t / 0.35))
    f = f * dark
    lum = f.mean(axis=2, keepdims=True)
    tint = [1.3, 0.75, 0.55] if FINAL else [0.9, 0.7, 1.25]
    f = f * 0.88 + lum * 0.12 * np.array(tint, np.float32)  # ombres teintées
    f = f * VIGNETTE
    f = f + LEAK_RED * 0.32 * flick + LEAK_VIO * 0.30 * (1.6 - flick)
    if FINAL:  # lueur de flammes qui monte du bas de l'image
        fire = 0.45 + 0.2 * math.sin(t * 31) * math.sin(t * 13.7) + 0.1 * math.sin(t * 57)
        f = f + FIRE_GLOW * fire
    return f


# ----------------------------------------------------------- titre
FONT = f"{HERE}/LuckiestGuy-Regular.ttf"
TS = 1.5  # super-échantillonnage du titre


def build_title():
    text = os.environ.get("TITRE", "MANCHE 1")
    size = int(335 * TS)
    font = ImageFont.truetype(FONT, size)
    while font.getbbox(text)[2] - font.getbbox(text)[0] > 1640 * TS:  # titre long : on réduit
        size -= 4
        font = ImageFont.truetype(FONT, size)
    bbox = font.getbbox(text)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = int(90 * TS)
    depth = int(26 * TS)
    cw, ch = tw + pad * 2 + depth, th + pad * 2 + depth
    ox, oy = pad - bbox[0], pad - bbox[1]

    def text_mask(dx=0, dy=0, stroke=0):
        m = Image.new("L", (cw, ch), 0)
        ImageDraw.Draw(m).text((ox + dx, oy + dy), text, font=font, fill=255,
                               stroke_width=stroke, stroke_fill=255)
        return m

    layer = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    # ombre portée
    sh = text_mask(depth + 10, depth + 14, int(30 * TS)).filter(ImageFilter.GaussianBlur(14 * TS))
    layer.paste((0, 0, 0, 255), (0, 0), sh.point(lambda v: v * 0.85))
    # extrusion 3D (rouge sombre -> violet profond)
    for i in range(depth, 0, -1):
        k = i / depth
        col = (int(lerp(70, 25, k)), int(lerp(6, 2, k)), int(lerp(60, 30, k)), 255)
        if FINAL:
            col = (int(lerp(110, 35, k)), int(lerp(30, 5, k)), int(lerp(5, 0, k)), 255)
        layer.paste(col, (0, 0), text_mask(i * 0.55, i, int(24 * TS)))
    # contour rouge extérieur
    outer, inner, line = ((225, 18, 40), (150, 45, 255), (40, 8, 70))
    if FINAL:
        outer, inner, line = ((150, 0, 0), (255, 110, 0), (70, 15, 0))
    layer.paste(outer + (255,), (0, 0), text_mask(0, 0, int(24 * TS)))
    # contour intérieur
    layer.paste(inner + (255,), (0, 0), text_mask(0, 0, int(13 * TS)))
    # fine ligne sombre entre le contour et le remplissage
    layer.paste(line + (255,), (0, 0), text_mask(0, 0, int(4 * TS)))
    # remplissage blanc avec léger dégradé et reflet
    fill = text_mask()
    grad = np.zeros((ch, cw, 4), np.uint8)
    gy = np.linspace(0, 1, ch)[:, None]
    top, bot = oy + bbox[1], oy + bbox[3]
    g = np.clip((np.arange(ch)[:, None] - top) / max(1, bot - top), 0, 1) * np.ones((1, cw))
    if FINAL:  # or métallique : clair en haut, ambré en bas, reflet au milieu
        shine = np.exp(-((g - 0.42) / 0.06) ** 2)
        grad[..., 0] = 255
        grad[..., 1] = np.clip(240 - 110 * g + 30 * shine, 0, 255).astype(np.uint8)
        grad[..., 2] = np.clip(170 - 160 * g + 80 * shine, 0, 255).astype(np.uint8)
    else:
        grad[..., 0] = (255 - 25 * g).astype(np.uint8)
        grad[..., 1] = (255 - 45 * g).astype(np.uint8)
        grad[..., 2] = (255 - 10 * g).astype(np.uint8)
    grad[..., 3] = 255
    layer.paste(Image.fromarray(grad, "RGBA"), (0, 0), fill)
    hl = text_mask(0, -int(6 * TS)).filter(ImageFilter.GaussianBlur(2 * TS))
    hl_np = np.asarray(hl).astype(np.float32) * (1 - np.asarray(fill).astype(np.float32) / 255)
    # (reflet sous forme de ligne claire en haut des lettres)
    del hl_np, gy
    glow = text_mask(0, 0, int(30 * TS)).filter(ImageFilter.GaussianBlur(40 * TS))
    return layer, glow


TITLE, TITLE_GLOW = build_title()
TITLE_NP = np.asarray(TITLE).astype(np.float32)
GLOW_NP = np.asarray(TITLE_GLOW).astype(np.float32) / 255


def title_state(t):
    """(échelle, opacité, intensité du glow) ou None."""
    if t < 2.0:
        return None
    d = t - 2.0
    if d < 0.11:
        k = d / 0.11
        sc = lerp(3.2, 1.0, k ** 2)
        op = clamp01(k * 3)
    elif d < 0.6:
        k = (d - 0.11) / 0.49
        sc = 1 - 0.09 * math.exp(-k * 5) * math.cos(k * 14)
        op = 1
    else:
        sc = 1 + 0.012 * math.sin((t - 2.6) * 2 * math.pi * 1.1)
        op = 1
    glow = 0.55 + 0.25 * math.sin(t * 9) * math.sin(t * 3.3)
    if d < 0.5:
        glow += 1.2 * math.exp(-d * 6)
    if t >= 4.2:
        p = t - 4.2
        sc *= 1 + 0.13 * math.exp(-p * 7) * math.sin(min(p * 14, math.pi))
        glow += 1.4 * math.exp(-p * 5)
    if t >= 4.72:
        k = (t - 4.72) / 0.28
        sc *= 1 + 3.5 * k ** 2.5
        op *= 1 - k ** 1.5
    return sc, op, glow


def composite_title(f, t):
    st = title_state(t)
    if st is None:
        return f
    sc, op, gl = st
    sx, sy = shake(t, 99)
    a = shake_amount(t) * 0.5
    cx, cy = W / 2 + sx * a, H / 2 + 50 + sy * a
    s = sc / TS
    tw, th = int(TITLE.width * s), int(TITLE.height * s)
    if tw < 4 or op <= 0:
        return f
    rgba = np.asarray(TITLE.resize((tw, th), Image.BICUBIC)).astype(np.float32)
    glow = np.asarray(TITLE_GLOW.resize((tw, th), Image.BILINEAR)).astype(np.float32) / 255
    x0, y0 = int(cx - tw / 2), int(cy - th / 2)
    fx0, fy0, fx1, fy1 = max(0, x0), max(0, y0), min(W, x0 + tw), min(H, y0 + th)
    if fx1 <= fx0 or fy1 <= fy0:
        return f
    sub = rgba[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0]
    gsub = glow[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0, None]
    region = f[fy0:fy1, fx0:fx1]
    # glow rouge/violet derrière le titre
    mix = math.sin(t * 5) * 0.5 + 0.5
    gcol = np.array([lerp(255, 160, mix), 25, lerp(50, 255, mix)], np.float32)
    if FINAL:
        gcol = np.array([255, lerp(40, 120, mix), 0], np.float32)
    region += gsub * gcol * gl * 0.9 * op
    alpha = sub[..., 3:4] / 255 * op
    region[:] = region * (1 - alpha) + sub[..., :3] * alpha
    return f


# --------------------------------------------------------- particules
rng = np.random.default_rng(42)


def make_burst(n, t0, speed, life):
    ang = rng.uniform(0, 2 * math.pi, n)
    sp = rng.uniform(0.25, 1.0, n) ** 0.6 * speed
    return dict(
        t0=t0, x=W / 2 + rng.normal(0, 120, n), y=H / 2 + 50 + rng.normal(0, 40, n),
        vx=np.cos(ang) * sp * 1.4, vy=np.sin(ang) * sp - 150,
        life=rng.uniform(0.4, 1.0, n) * life, size=rng.uniform(2, 7, n),
        col=rng.choice(np.array([[255, 60, 20], [255, 140, 30], [255, 200, 60], [255, 240, 200], [200, 20, 0]]
                                if FINAL else
                                [[255, 60, 50], [255, 140, 60], [170, 70, 255], [255, 240, 240], [220, 30, 255]],
                                np.float32), n),
    )


BURSTS = [make_burst(320, 2.0, 1700, 1.6), make_burst(140, 4.2, 1200, 0.9)]
N_AMB = 190 if FINAL else 70
AMB = dict(x=rng.uniform(0, W, N_AMB), y=rng.uniform(0, H, N_AMB),
           vy=rng.uniform(-320, -90, N_AMB) if FINAL else rng.uniform(-90, -25, N_AMB),
           sway=rng.uniform(0, 6.28, N_AMB), size=rng.uniform(1.5, 5.5 if FINAL else 4.5, N_AMB),
           col=rng.choice(np.array([[255, 90, 10], [255, 160, 40], [255, 40, 0]] if FINAL else
                                   [[255, 70, 40], [190, 80, 255], [255, 120, 70]], np.float32), N_AMB))

# éclairs (thème final) : instants et graines
BOLTS = [(1.0, 1), (1.47, 2), (2.0, 3), (2.0, 4), (4.2, 5)] if FINAL else []


def draw_bolt(dr, seed, k):
    r = np.random.default_rng(seed)
    x, y = r.uniform(W * 0.15, W * 0.85), -20.0
    pts = [(x, y)]
    while y < H * r.uniform(0.55, 0.9):
        x += r.normal(0, 55)
        y += r.uniform(40, 90)
        pts.append((x, y))
    col = (int(255 * k), int(200 * k), int(140 * k))
    dr.line(pts, fill=col, width=max(1, int(9 * k)))
    for _ in range(3):  # ramifications
        i = r.integers(1, len(pts) - 1)
        bx, by = pts[i]
        br = [(bx, by)]
        for _ in range(r.integers(2, 5)):
            bx += r.normal(0, 60)
            by += r.uniform(30, 70)
            br.append((bx, by))
        dr.line(br, fill=col, width=max(1, int(4 * k)))


def particles_layer(t):
    layer = Image.new("RGB", (W, H), (0, 0, 0))
    dr = ImageDraw.Draw(layer)
    # braises ambiantes
    for i in range(N_AMB):
        x = (AMB["x"][i] + 30 * math.sin(t * 1.5 + AMB["sway"][i])) % W
        y = (AMB["y"][i] + AMB["vy"][i] * t) % H
        s = AMB["size"][i]
        c = tuple(int(v * (0.5 + 0.5 * math.sin(t * 6 + i))) for v in AMB["col"][i])
        dr.ellipse((x - s, y - s, x + s, y + s), fill=c)
    # explosions d'impact
    for b in BURSTS:
        d = t - b["t0"]
        if d < 0:
            continue
        drag = (1 - np.exp(-d * 3.0)) / 3.0
        px = b["x"] + b["vx"] * drag
        py = b["y"] + b["vy"] * drag + 260 * d * d
        k = np.clip(1 - d / b["life"], 0, 1)
        for i in np.nonzero(k > 0)[0]:
            s = b["size"][i] * (0.4 + k[i])
            c = tuple(int(v * k[i] ** 0.7) for v in b["col"][i])
            vx = b["vx"][i] * math.exp(-d * 3) * 0.012
            vy = (b["vy"][i] * math.exp(-d * 3) + 520 * d) * 0.012
            dr.line((px[i] - vx, py[i] - vy, px[i], py[i]), fill=c, width=max(1, int(s)))
            dr.ellipse((px[i] - s / 2, py[i] - s / 2, px[i] + s / 2, py[i] + s / 2), fill=c)
    # ondes de choc
    for t0, strength in ((2.0, 1.0), (2.06, 0.6), (4.2, 0.7)):
        d = t - t0
        if 0 <= d < 0.55:
            r = 80 + 1900 * (1 - math.exp(-d * 5))
            k = (1 - d / 0.55) ** 1.5 * strength
            wdt = int(6 + 30 * k)
            col = (int(255 * k), int(150 * k), int(20 * k)) if FINAL else (int(255 * k), int(70 * k), int(230 * k))
            dr.ellipse((W / 2 - r, H / 2 + 50 - r * 0.42, W / 2 + r, H / 2 + 50 + r * 0.42), outline=col, width=wdt)
    for t0, seed in BOLTS:
        d = t - t0
        if 0 <= d < 0.16:
            k = (1 - d / 0.16) * (0.6 + 0.4 * (int(d * 60) % 2))  # scintillement
            draw_bolt(dr, seed, k)
    glow = layer.filter(ImageFilter.GaussianBlur(9))
    return np.asarray(layer).astype(np.float32) + np.asarray(glow).astype(np.float32) * 1.6


# ----------------------------------------------------------- flashs
def flash(t):
    """Couleur additive + niveau de blanc."""
    col = np.zeros(3, np.float32)
    for t0, c, dur, a in [
        (0.0, (255, 255, 255), 0.12, 0.6),
        (1.0, (255, 20, 30), 0.18, 0.85),
        (1.08, (255, 110, 0) if FINAL else (160, 40, 255), 0.18, 0.6),
        (1.47, (255, 120, 10) if FINAL else (170, 40, 255), 0.15, 0.7),
        (1.86, (255, 20, 40), 0.12, 0.6),
        (2.0, (255, 245, 255), 0.22, 1.25),
        (2.05, (255, 90, 0) if FINAL else (150, 30, 255), 0.35, 0.55),
        (4.2, (255, 30, 60), 0.25, 0.6),
    ]:
        d = t - t0
        if 0 <= d < dur:
            col += np.array(c, np.float32) * a * (1 - d / dur) ** 2
    white = 0.0
    if t >= 4.72:
        white = clamp01((t - 4.72) / 0.22) ** 1.6
    if t < 0.08:
        white = 1 - t / 0.08  # ouverture depuis le blanc
    return col, white


# ----------------------------------------------------------- glitch
GLITCH = [(1.00, 0.10), (1.24, 0.05), (1.47, 0.12), (1.66, 0.04), (1.86, 0.10), (2.02, 0.06), (4.62, 0.08)]


def glitch_level(t):
    for t0, d in GLITCH:
        if t0 <= t < t0 + d:
            return 1.0
    if 1.0 <= t < 2.0:
        return 0.18
    return 0.0


def apply_glitch(img, t, fi):
    g = glitch_level(t)
    if g <= 0:
        return img
    r = np.random.default_rng(1000 + fi // 2)
    out = img.copy()
    sh = int(r.uniform(6, 26) * g) + 2
    out[..., 0] = np.roll(img[..., 0], sh, axis=1)
    out[..., 2] = np.roll(img[..., 2], -sh, axis=1)
    nb = int(3 + 14 * g)
    for _ in range(nb):
        y0 = r.integers(0, H - 10)
        h = int(r.integers(4, 90) * (0.4 + g))
        off = int(r.normal(0, 140 * g))
        out[y0:y0 + h] = np.roll(out[y0:y0 + h], off, axis=1)
        if r.random() < 0.3 * g:
            out[y0:y0 + h] = out[y0:y0 + h] * np.array([1.4, 0.6, 0.2] if FINAL else [1.2, 0.4, 1.3], np.float32)
    if g >= 1:
        for _ in range(6):
            bw, bh = r.integers(40, 260), r.integers(10, 70)
            x, y = r.integers(0, W - bw), r.integers(0, H - bh)
            sx, sy = r.integers(0, W - bw), r.integers(0, H - bh)
            out[y:y + bh, x:x + bw] = out[sy:sy + bh, sx:sx + bw]
        out[::3] *= 0.75  # scanlines
    return out


# ----------------------------------------------------------- rendu
def render_frame(fi):
    t = fi / FPS
    base = wobble_webs(SRC, t)
    base = add_eye_glow(base, t)
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))

    # flou de mouvement : plusieurs échantillons caméra si elle bouge vite
    c0, c1 = camera(t), camera(max(0, t - 1 / 120))
    speed = abs(c0[2] - c1[2]) / c0[2] + math.hypot(c0[0] - c1[0], c0[1] - c1[1]) / c0[2]
    n = 1 if speed < 0.003 else min(7, 2 + int(speed * 400))
    acc = np.zeros((H, W, 3), np.float32)
    for k in range(n):
        tk = t - (k / max(1, n - 1)) * (1 / 120) if n > 1 else t
        cx, cy, vw = camera(max(0, tk))
        acc += np.asarray(render_view(img, cx, cy, vw, tk)).astype(np.float32)
    f = acc / n

    f = grade(f, t)
    if t >= 2.0:  # fond assombri pour la lisibilité, monstre toujours visible
        k = clamp01((t - 2.0) / 0.15)
        f = f * (1 - 0.32 * k * np.clip(1.2 - CENTER_DIST * 1.1, 0.3, 1)[..., None])
    f = composite_title(f, t)
    f = f + particles_layer(t)
    col, white = flash(t)
    f = f + col
    f = apply_glitch(f, t, fi)
    f = f * (1 - white) + 255 * white
    return np.clip(f, 0, 255).astype(np.uint8)


if __name__ == "__main__":
    only = [int(a) for a in sys.argv[1:]]
    if only:  # aperçus PNG
        for fi in only:
            Image.fromarray(render_frame(fi)).save(f"preview_{fi:03d}.png")
        sys.exit()
    from multiprocessing import Pool
    out = sys.stdout.buffer
    with Pool() as pool:
        for fi, frame in enumerate(pool.imap(render_frame, range(NF), chunksize=2)):
            out.write(frame.tobytes())
            if fi % 30 == 0:
                print(f"frame {fi}/{NF}", file=sys.stderr)
