#!/usr/bin/env python3
"""
Teaser Noël UNITED GAMES — rendu procédural 1080x1920 (9:16), 30 fps, 18 s, sans audio.

Usage :
    python3 render_teaser.py                  # rend la vidéo complète -> out/united_games_teaser_noel.mp4
    python3 render_teaser.py --preview 1.0 4.5 # rend seulement des images PNG aux temps donnés

Dépendances : Python 3, Pillow, numpy, ffmpeg.
Assets : assets/reference.png (décor de Noël), assets/logo.png (logo blanc sur fond noir).
"""
import math
import os
import subprocess
import sys
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
OUT = os.path.join(HERE, "out")

W, H = 1080, 1920
FPS = 30
DUR = 18.0
NFRAMES = int(DUR * FPS)

FONT_BLACK = "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf"
FONT_XBOLD = "/usr/share/fonts/opentype/inter/InterDisplay-ExtraBold.otf"
FONT_SEMI = "/usr/share/fonts/opentype/inter/InterDisplay-SemiBold.otf"
FONT_MED_IT = "/usr/share/fonts/opentype/inter/Inter-SemiBoldItalic.otf"
FONT_EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"

RED = (226, 30, 45)
WHITE = (255, 255, 255)
GOLD_TOP = (255, 241, 196)
GOLD_BOT = (214, 160, 62)

# --------------------------------------------------------------------------- utils


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def lerp(a, b, u):
    return a + (b - a) * u


def smooth(u):
    u = clamp(u)
    return u * u * (3 - 2 * u)


def ease_out_cubic(u):
    u = clamp(u)
    return 1 - (1 - u) ** 3


def ease_in_out(u):
    u = clamp(u)
    return 0.5 - 0.5 * math.cos(math.pi * u)


def ease_out_back(u, k=1.70158):
    u = clamp(u)
    u -= 1
    return 1 + (k + 1) * u ** 3 + k * u ** 2


def seg(t, a, b):
    """0 avant a, 1 après b, linéaire entre les deux."""
    return clamp((t - a) / (b - a))


def noise(w, h, gw, gh, rng):
    small = (rng.random((gh, gw)) * 255).astype(np.uint8)
    return np.asarray(Image.fromarray(small).resize((w, h), Image.BICUBIC), dtype=np.float32) / 255.0


def fbm(w, h, rng, base=4, octaves=5, aspect=1.0):
    acc = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        g = base * (2 ** o)
        acc += amp * noise(w, h, max(2, int(g * aspect)), max(2, int(g * h / w)), rng)
        tot += amp
        amp *= 0.5
    return acc / tot


def soft_sprite(radius, color, falloff=2.0, core=0.0):
    """Disque lumineux radial (RGBA)."""
    s = int(radius * 2 + 2)
    y, x = np.mgrid[0:s, 0:s].astype(np.float32)
    d = np.sqrt((x - s / 2) ** 2 + (y - s / 2) ** 2) / max(radius, 0.5)
    a = np.clip(1 - d, 0, 1) ** falloff
    if core > 0:
        a = np.maximum(a, np.clip((core - d) / core, 0, 1))
    arr = np.zeros((s, s, 4), np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = color
    arr[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def star_sprite(size, color=(255, 246, 220)):
    """Petite étoile scintillante à 4 branches."""
    s = size * 2 + 1
    y, x = np.mgrid[0:s, 0:s].astype(np.float32)
    dx, dy = np.abs(x - size) / size, np.abs(y - size) / size
    a = np.clip(1 - dx, 0, 1) ** 6 * np.clip(1 - dy * 12, 0, 1)
    a = np.maximum(a, np.clip(1 - dy, 0, 1) ** 6 * np.clip(1 - dx * 12, 0, 1))
    r = np.sqrt(dx ** 2 + dy ** 2)
    a = np.maximum(a, np.clip(1 - r * 3.2, 0, 1) ** 2)
    arr = np.zeros((s, s, 4), np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = color
    arr[..., 3] = (np.clip(a, 0, 1) * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def paste_alpha(dst, src, cx, cy, alpha=1.0):
    """Alpha-composite src centré en (cx, cy) avec opacité globale."""
    if alpha <= 0.003:
        return
    if alpha < 0.999:
        a = src.getchannel("A").point(lambda v: int(v * alpha))
        src = src.copy()
        src.putalpha(a)
    x0, y0 = int(round(cx - src.width / 2)), int(round(cy - src.height / 2))
    # recadrage pour rester dans l'image
    sx0, sy0 = max(0, -x0), max(0, -y0)
    sx1, sy1 = min(src.width, dst.width - x0), min(src.height, dst.height - y0)
    if sx1 <= sx0 or sy1 <= sy0:
        return
    if (sx0, sy0, sx1, sy1) != (0, 0, src.width, src.height):
        src = src.crop((sx0, sy0, sx1, sy1))
    dst.alpha_composite(src, (x0 + sx0, y0 + sy0))


def transform(img, scale=1.0, angle=0.0, blur=0.0):
    if blur > 0.3:
        pad = int(blur * 2.5)
        big = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
        big.paste(img, (pad, pad))
        img = big.filter(ImageFilter.GaussianBlur(blur))
    if abs(scale - 1) > 0.002:
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.BILINEAR)
    if abs(angle) > 0.05:
        img = img.rotate(angle, resample=Image.BICUBIC, expand=True)
    return img


# --------------------------------------------------------------------------- texte


_emoji_font = None


def emoji_img(ch, size):
    global _emoji_font
    if _emoji_font is None:
        _emoji_font = ImageFont.truetype(FONT_EMOJI, 109)
    im = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((10, 10), ch, font=_emoji_font, embedded_color=True)
    im = im.crop(im.getbbox())
    k = size / im.height
    return im.resize((int(im.width * k), int(size)), Image.LANCZOS)


def text_line(text, font_path, size, fill=WHITE, stroke=0, stroke_fill=WHITE, tracking=0.0, emoji=None, gradient=None):
    """Ligne de texte RGBA. fill = couleur ; gradient = (haut, bas) pour un dégradé vertical."""
    font = ImageFont.truetype(font_path, size)
    asc, desc = font.getmetrics()
    widths = [font.getlength(c) + tracking * size for c in text]
    tw = int(sum(widths) - (tracking * size if text else 0))
    em = emoji_img(emoji, size * 0.95) if emoji else None
    gap = int(size * 0.28) if em else 0
    pad = stroke + 4
    lw = tw + (em.width + gap if em else 0) + pad * 2
    lh = asc + desc + pad * 2
    mask = Image.new("L", (lw, lh), 0)
    smask = Image.new("L", (lw, lh), 0)
    d, ds = ImageDraw.Draw(mask), ImageDraw.Draw(smask)
    x = pad
    for c, cw in zip(text, widths):
        if stroke:
            ds.text((x, pad), c, font=font, fill=255, stroke_width=stroke, stroke_fill=255)
        d.text((x, pad), c, font=font, fill=255)
        x += cw
    out = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
    if stroke:
        out.paste(Image.new("RGBA", (lw, lh), stroke_fill + (255,)), (0, 0), smask)
    if gradient:
        top, bot = gradient
        g = np.linspace(0, 1, lh, dtype=np.float32)[:, None, None]
        col = (np.array(top, np.float32) * (1 - g) + np.array(bot, np.float32) * g)
        col = np.repeat(col, lw, axis=1).astype(np.uint8)
        layer = Image.fromarray(np.dstack([col, np.full((lh, lw), 255, np.uint8)]), "RGBA")
    else:
        layer = Image.new("RGBA", (lw, lh), tuple(fill) + (255,))
    out.paste(layer, (0, 0), mask)
    if em:
        out.alpha_composite(em, (pad + tw + gap, pad + int((asc - em.height) * 0.55 + size * 0.05)))
    return out


def text_block(lines, spacing=0.08, shadow=0.75, glow=None, glow_radius=22):
    """Empile des lignes centrées, ajoute ombre portée et halo."""
    gap = int(max(l.height for l in lines) * spacing)
    bw = max(l.width for l in lines)
    bh = sum(l.height for l in lines) + gap * (len(lines) - 1)
    m = 70
    blk = Image.new("RGBA", (bw + m * 2, bh + m * 2), (0, 0, 0, 0))
    y = m
    for l in lines:
        blk.alpha_composite(l, ((blk.width - l.width) // 2, y))
        y += l.height + gap
    a = blk.getchannel("A")
    out = Image.new("RGBA", blk.size, (0, 0, 0, 0))
    if shadow:
        sh = a.filter(ImageFilter.GaussianBlur(14)).point(lambda v: int(v * shadow))
        sl = Image.new("RGBA", blk.size, (0, 0, 0, 255))
        sl.putalpha(sh)
        out.alpha_composite(sl, (0, 8))
    if glow:
        gl = a.filter(ImageFilter.GaussianBlur(glow_radius)).point(lambda v: int(min(255, v * 0.9)))
        g = Image.new("RGBA", blk.size, glow + (255,))
        g.putalpha(gl)
        out.alpha_composite(g)
    out.alpha_composite(blk)
    return out


# --------------------------------------------------------------------------- bonnet procédural


def draw_hat(scale=4):
    """Bonnet de Noël dessiné (rouge + fourrure blanche + pompon). Renvoie RGBA ~ 400x330."""
    S = scale
    w, h = 400 * S, 330 * S
    rng = np.random.default_rng(7)

    def bez(p0, p1, p2, p3, n=60):
        ts = np.linspace(0, 1, n)
        return [((1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t ** 2 * p2[0] + t ** 3 * p3[0],
                 (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t ** 2 * p2[1] + t ** 3 * p3[1]) for t in ts]

    P = lambda x, y: (x * S, y * S)
    outline = []
    outline += bez(P(40, 245), P(40, 140), P(120, 40), P(225, 38))      # côté gauche -> sommet
    outline += bez(P(225, 38), P(320, 36), P(360, 120), P(352, 228))    # sommet -> pointe tombante
    outline += bez(P(352, 228), P(335, 215), P(305, 225), P(290, 255))  # dessous de la pointe
    body = Image.new("L", (w, h), 0)
    ImageDraw.Draw(body).polygon(outline, fill=255)

    # ombrage du tissu rouge
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    u = (xx / w * 0.55 + yy / h * 0.45)
    shade = 1.15 - 0.75 * u
    crease = np.exp(-(((xx - 235 * S) * 0.9 + (yy - 120 * S) * 0.45) / (26 * S)) ** 2) * 0.35
    shade -= crease
    tex = noise(w, h, 60, 50, rng) * 0.08
    shade = np.clip(shade + tex, 0.25, 1.3)
    base = np.array([196, 22, 36], np.float32)
    red = np.clip(base[None, None, :] * shade[..., None], 0, 255).astype(np.uint8)
    hat = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    hat.paste(Image.fromarray(red, "RGB"), (0, 0), body.filter(ImageFilter.GaussianBlur(S * 0.8)))
    # ombre interne près du bord fourrure
    inner = Image.new("L", (w, h), 0)
    ImageDraw.Draw(inner).ellipse([30 * S, 200 * S, 300 * S, 300 * S], fill=150)
    inner = Image.composite(inner.filter(ImageFilter.GaussianBlur(14 * S)), Image.new("L", (w, h), 0), body)
    dark = Image.new("RGBA", (w, h), (40, 0, 5, 255))
    dark.putalpha(inner)
    hat.alpha_composite(dark)

    def fur(mask_draw_fn, n, rmin, rmax):
        m = Image.new("L", (w, h), 0)
        mask_draw_fn(ImageDraw.Draw(m))
        ma = np.asarray(m) > 0
        ys, xs = np.nonzero(ma)
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        for _ in range(n):
            i = rng.integers(len(xs))
            r = rng.uniform(rmin, rmax) * S
            v = int(rng.uniform(200, 255))
            yfac = (ys[i] - ys.min()) / max(1, ys.max() - ys.min())
            v = int(v * (1 - 0.22 * yfac))
            d.ellipse([xs[i] - r, ys[i] - r, xs[i] + r, ys[i] + r], fill=(v, v, min(255, v + 6), 255))
        layer = layer.filter(ImageFilter.GaussianBlur(S * 1.4))
        return layer

    brim = fur(lambda d: d.rounded_rectangle([18 * S, 228 * S, 300 * S, 292 * S], radius=32 * S, fill=255), 6500, 3, 7)
    brim = brim.rotate(-4, resample=Image.BICUBIC, center=(160 * S, 260 * S))
    hat.alpha_composite(brim)
    pom = fur(lambda d: d.ellipse([318 * S, 205 * S, 392 * S, 279 * S], fill=255), 2200, 3, 6.5)
    hat.alpha_composite(pom)
    hat = hat.resize((w // S, h // S), Image.LANCZOS)
    return hat


# --------------------------------------------------------------------------- préparation des assets


def build_background():
    ref = Image.open(os.path.join(ASSETS, "reference.png")).convert("RGB")
    a = np.asarray(ref, np.float32)
    # suppression du logo flou de la référence (on composite le vrai logo net à la place)
    m = Image.new("L", ref.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([285, 115, 975, 800], radius=160, fill=255)
    m = np.asarray(m.filter(ImageFilter.GaussianBlur(45)), np.float32) / 255.0
    # remplissage par diffusion (basse résolution, flottant) puis léger grain
    k = 6
    sh, sw = ref.height // k, ref.width // k
    small = np.asarray(ref.resize((sw, sh), Image.BOX), np.float32)
    hole = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).resize((sw, sh), Image.BILINEAR), np.float32) > 20
    f = small.copy()
    f[hole] = small[~hole].mean(axis=0)
    for _ in range(1500):
        avg = (np.roll(f, 1, 0) + np.roll(f, -1, 0) + np.roll(f, 1, 1) + np.roll(f, -1, 1)) / 4
        f[hole] = avg[hole]
    fill = np.stack([np.asarray(Image.fromarray(f[..., c]).resize(ref.size, Image.BICUBIC), np.float32) for c in range(3)], -1)
    fill += (np.random.default_rng(3).random(fill.shape[:2], dtype=np.float32)[..., None] - 0.5) * 3
    a = a * (1 - m[..., None]) + fill * m[..., None]
    ref = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

    S = 1500
    big = ref.resize((S, S), Image.LANCZOS)
    ox, oy = (W - S) // 2, 200
    bg = Image.new("RGB", (W, H), (0, 0, 0))
    # extension haut / bas par miroir flouté
    top = Image.new("RGB", (S, oy + 90))
    top.paste(big.crop((0, 0, S, oy)).transpose(Image.FLIP_TOP_BOTTOM), (0, 0))
    top.paste(big.crop((0, 0, S, 90)), (0, oy))
    top = top.filter(ImageFilter.GaussianBlur(18))
    bh_ = H - oy - S
    bot = Image.new("RGB", (S, bh_ + 60))
    bot.paste(big.crop((0, S - 60, S, S)), (0, 0))
    bot.paste(big.crop((0, S - bh_, S, S)).transpose(Image.FLIP_TOP_BOTTOM), (0, 60))
    bot = bot.filter(ImageFilter.GaussianBlur(10))
    bg.paste(top, (ox, 0))
    bg.paste(bot, (ox, oy + S - 60))
    fm = np.ones((S, S), np.float32)
    ramp = np.linspace(0, 1, 90, dtype=np.float32) ** 1.5
    fm[:90] = ramp[:, None]
    fm[-60:] = np.minimum(fm[-60:], ramp[::-1][-60:, None] * 0 + np.linspace(1, 0, 60, dtype=np.float32)[:, None] ** 0.7)
    bg.paste(big, (ox, oy), Image.fromarray((fm * 255).astype(np.uint8)))
    # raccords doux + vignette
    arr = np.asarray(bg, np.float32)
    yy = np.arange(H, dtype=np.float32)[:, None]
    xx = np.arange(W, dtype=np.float32)[None, :]
    topfade = np.clip(yy / (oy + 90), 0, 1) ** 1.3 * 0.8 + 0.2
    arr *= np.where(yy < oy + 90, topfade, 1.0)[..., None]
    vig = 1 - 0.55 * (((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H * 0.48) / (H * 0.62)) ** 2)
    arr *= np.clip(vig, 0.25, 1)[..., None]
    bg = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    lights = [(183, 14), (243, 68), (357, 57), (466, 12), (104, 180), (27, 214)]
    lights = [(x * S / 1254 + ox, y * S / 1254 + oy) for x, y in lights]
    return bg, lights


class Assets:
    pass


A = Assets()


def prepare():
    rng = np.random.default_rng(2024)
    A.bg, A.tree_lights = build_background()

    # ---- logo (blanc sur noir -> alpha)
    logo = Image.open(os.path.join(ASSETS, "logo.png")).convert("L")
    box = (215, 243, 1045, 1051)
    logo = logo.crop(box)
    A.logo_scale = 640 / (995 - 265)
    lw, lh = int(logo.width * A.logo_scale), int(logo.height * A.logo_scale)
    logo = logo.resize((lw, lh), Image.LANCZOS)
    logo = logo.point(lambda v: 0 if v < 18 else min(255, int((v - 18) * 255 / 220)))
    P = 170
    A.logo_alpha = Image.new("L", (lw + 2 * P, lh + 2 * P), 0)
    A.logo_alpha.paste(logo, (P, P))
    # bonnet, placé sur le haut du G (coordonnées du logo original -> couche)
    hat = draw_hat()
    hk = 0.92 * A.logo_scale * 1254 / 1254
    hat = hat.resize((int(hat.width * hk * 1.15), int(hat.height * hk * 1.15)), Image.LANCZOS)
    hat = hat.rotate(8, resample=Image.BICUBIC, expand=True)
    A.hat_layer = Image.new("RGBA", A.logo_alpha.size, (0, 0, 0, 0))
    brim_x = (700 - box[0]) * A.logo_scale + P
    brim_y = (330 - box[1]) * A.logo_scale + P
    A.hat_layer.alpha_composite(hat, (int(brim_x - hat.width * 0.40), int(brim_y - hat.height * 0.80)))
    A.hat_layer = A.hat_layer.crop(A.hat_layer.getbbox())
    hb = A.hat_layer.size
    A.hat_offset = (int(brim_x - hat.width * 0.40) + 0, int(brim_y - hat.height * 0.80))  # approx
    # centre du bonnet relatif au centre de la couche logo
    hx0, hy0 = int(brim_x - hat.width * 0.40), int(brim_y - hat.height * 0.80)
    bb = Image.new("RGBA", A.logo_alpha.size, (0, 0, 0, 0))
    bb.alpha_composite(hat, (hx0, hy0))
    bx = bb.getbbox()
    A.hat_rel = ((bx[0] + bx[2]) / 2 - A.logo_alpha.width / 2, (bx[1] + bx[3]) / 2 - A.logo_alpha.height / 2)
    A.logo_center = (W / 2, 840)

    # ---- sprites
    A.glow_warm = {r: soft_sprite(r, (255, 196, 110), 1.8) for r in (10, 18, 30, 46, 70)}
    A.bulb = soft_sprite(7, (255, 236, 190), 1.0, core=0.45)
    A.star = {s: star_sprite(s) for s in (10, 16, 24, 34)}
    A.snow = {}
    for r in range(2, 16):
        blur_fall = 1.2 + max(0, r - 7) * 0.35
        A.snow[r] = soft_sprite(r, (245, 248, 255), blur_fall, core=0.55 if r < 8 else 0)

    # ---- particules de neige
    n = 300
    A.flakes = np.column_stack([
        rng.uniform(-40, W + 40, n),        # x0
        rng.uniform(0, H + 60, n),          # y0
        rng.uniform(0, 1, n) ** 1.6,        # profondeur (0 = loin)
        rng.uniform(0, 2 * math.pi, n),     # phase
        rng.uniform(0.3, 1.2, n),           # fréquence d'oscillation
        rng.uniform(0.55, 1.0, n),          # opacité
    ])

    # ---- bokeh doré
    A.bokeh = [(rng.uniform(0, W), rng.uniform(200, 1500), rng.choice([30, 46, 70]), rng.uniform(0, 6.28), rng.uniform(0.15, 0.35)) for _ in range(12)]

    # ---- scintillements
    A.twinkles = [(rng.uniform(60, W - 60), rng.uniform(250, 1650), int(rng.choice([10, 16, 24])), rng.uniform(0, 6.28), rng.uniform(1.5, 3.5)) for _ in range(26)]

    # ---- guirlande en haut (chaînette)
    pts = []
    for i in range(15):
        u = i / 14
        x = lerp(-30, W + 30, u)
        y = 105 + 120 * (1 - (2 * u - 1) ** 2) + 10 * math.sin(i * 1.7)
        pts.append((x, y))
    A.garland = pts

    # ---- brume
    fog = fbm(W * 2 // 4, H // 4, rng, base=3, octaves=4)
    fog = np.clip((fog - 0.35) * 1.8, 0, 1)
    fog_img = Image.fromarray((fog * 255).astype(np.uint8)).resize((W * 2, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(30))
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    fa = np.asarray(fog_img, np.float32) * (0.35 + 0.65 * yy)
    A.fog = Image.fromarray(np.dstack([np.full((H, W * 2), 225, np.uint8), np.full((H, W * 2), 232, np.uint8),
                                       np.full((H, W * 2), 245, np.uint8), (fa * 0.55).astype(np.uint8)]), "RGBA")

    # ---- dégradé sombre bas (lisibilité texte final)
    g = np.clip((np.linspace(0, 1, H) - 0.48) / 0.42, 0, 1) ** 1.2
    A.scrim = Image.fromarray(np.dstack([np.zeros((H, W, 3), np.uint8), np.repeat((g[:, None] * 200).astype(np.uint8), W, 1)]), "RGBA")

    prepare_ice(rng)
    prepare_texts()


# --------------------------------------------------------------------------- glace


IM = 30  # marge pour les secousses
IW, IH = W + 2 * IM, H + 2 * IM
IMPACT = (IW / 2, IH * 0.46)


def prepare_ice(rng):
    w, h = IW, IH
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cloud = fbm(w, h, rng, base=3, octaves=6)
    streak = noise(w, h, 90, 6, rng) * 0.6 + noise(w, h, 200, 10, rng) * 0.4
    fine = fbm(w, h, rng, base=40, octaves=3)
    edge = np.minimum(np.minimum(xx, w - xx), np.minimum(yy, h - yy)) / (w * 0.5)
    frost = np.clip((fine - 0.52) * 5 + (0.22 - edge) * 3.0, 0, 1) ** 1.4

    deep = np.array([12, 48, 92], np.float32)
    mid = np.array([70, 150, 205], np.float32)
    light = np.array([205, 236, 252], np.float32)
    u = np.clip(cloud * 1.35 - 0.3 + (1 - yy / h) * 0.12, 0, 1)[..., None]
    col = np.where(u < 0.5, deep + (mid - deep) * (u / 0.5), mid + (light - mid) * ((u - 0.5) / 0.5))
    # lumières chaudes déformées derrière la glace
    behind = np.asarray(A.bg.resize((w, h)).filter(ImageFilter.GaussianBlur(28)), np.float32)
    col = col * 0.85 + behind * np.array([0.6, 0.75, 1.0]) * 0.45
    col += (streak[..., None] - 0.5) * 12
    col = col * (1 - frost[..., None] * 0.75) + np.array([235, 247, 255]) * frost[..., None] * 0.75
    # reflet spéculaire diagonal
    band = np.exp(-(((xx * 0.6 + yy * 0.8) - h * 0.55) / (h * 0.09)) ** 2) * 0.35
    band += np.exp(-(((xx * 0.6 + yy * 0.8) - h * 0.32) / (h * 0.025)) ** 2) * 0.25
    col += band[..., None] * 255
    ice = Image.fromarray(np.clip(col, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(ice, "RGBA")
    for _ in range(700):  # bulles d'air
        x, y, r = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(0.8, 3.6)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(240, 250, 255, int(rng.uniform(60, 180))))
    A.ice = ice.filter(ImageFilter.GaussianBlur(0.6))

    # ---- fissures : Voronoï déformé (bords irréguliers) + fissures radiales
    px, py = IMPACT
    seeds = []
    for r_max, n in ((220, 16), (520, 26), (900, 22), (1400, 18)):
        for _ in range(n):
            ang, rr = rng.uniform(0, 2 * math.pi), rng.uniform(r_max * 0.35, r_max)
            seeds.append((px + math.cos(ang) * rr, py + math.sin(ang) * rr * 1.25))
    seeds = np.array(seeds, np.float32)
    hw, hh = w // 2, h // 2
    gy, gx = np.mgrid[0:hh, 0:hw].astype(np.float32) * 2
    gx = gx + (noise(hw, hh, 18, 30, rng) - 0.5) * 70
    gy = gy + (noise(hw, hh, 18, 30, rng) - 0.5) * 70
    best = np.full((hh, hw), 1e12, np.float32)
    lab = np.zeros((hh, hw), np.int32)
    for i, (sx, sy) in enumerate(seeds):
        dd = (gx - sx) ** 2 + (gy - sy) ** 2
        msk = dd < best
        best[msk] = dd[msk]
        lab[msk] = i
    labels = np.asarray(Image.fromarray(lab.astype(np.uint8)).resize((w, h), Image.NEAREST), np.int32)
    bnd = np.zeros((h, w), bool)
    bnd[:, 1:] |= labels[:, 1:] != labels[:, :-1]
    bnd[1:, :] |= labels[1:, :] != labels[:-1, :]
    crack = Image.fromarray((bnd * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))
    cd = ImageDraw.Draw(crack)
    for k in range(14):  # fissures radiales en zigzag
        ang = k / 14 * 2 * math.pi + rng.uniform(-0.15, 0.15)
        x, y = px, py
        width = 5
        for step in range(60):
            ang += rng.uniform(-0.35, 0.35)
            L = rng.uniform(18, 40)
            nx, ny = x + math.cos(ang) * L, y + math.sin(ang) * L
            cd.line([(x, y), (nx, ny)], fill=255, width=max(1, int(width)))
            if rng.random() < 0.12:  # ramification
                ba = ang + rng.choice([-1, 1]) * rng.uniform(0.5, 1.0)
                bx, by = nx, ny
                for _ in range(int(rng.integers(3, 9))):
                    ba += rng.uniform(-0.4, 0.4)
                    ex, ey = bx + math.cos(ba) * 20, by + math.sin(ba) * 20
                    cd.line([(bx, by), (ex, ey)], fill=200, width=2)
                    bx, by = ex, ey
            x, y = nx, ny
            width = max(1.5, width * 0.97)
            if not (-50 < x < w + 50 and -50 < y < h + 50):
                break
    A.crack = np.asarray(crack, np.float32) / 255.0
    dist = np.sqrt((xx - px) ** 2 + ((yy - py) / 1.15) ** 2) + (noise(w, h, 30, 50, rng) - 0.5) * 120
    A.ice_dist = dist

    # glace finale avec toutes les fissures (utilisée pour les éclats)
    A.ice_cracked = composite_cracks(A.ice, A.crack)

    # ---- éclats
    shards = []
    ice_rgba = A.ice_cracked.convert("RGBA")
    for i in range(len(seeds)):
        m = labels == i
        if not m.any():
            continue
        ys, xs = np.nonzero(m)
        x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        piece = ice_rgba.crop((x0, y0, x1, y1))
        alpha = Image.fromarray((m[y0:y1, x0:x1] * 255).astype(np.uint8))
        # liseré lumineux sur le bord de l'éclat
        edge_l = Image.fromarray((m[y0:y1, x0:x1] * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(5))
        edge_a = np.asarray(alpha, np.int16) - np.asarray(edge_l, np.int16)
        pa = np.asarray(piece).copy()
        e = (edge_a > 0)
        pa[e, :3] = np.clip(pa[e, :3].astype(np.int16) + 90, 0, 255).astype(np.uint8)
        piece = Image.fromarray(pa, "RGBA")
        piece.putalpha(alpha)
        cx, cy = xs.mean(), ys.mean()
        shards.append(dict(img=piece, cx=cx, cy=cy, rot=rng.uniform(-110, 110), spd=rng.uniform(0.8, 1.3),
                           dist=math.hypot(cx - px, cy - py)))
    A.shards = sorted(shards, key=lambda s: -s["dist"])  # les plus proches du centre devant
    A.debris = [(rng.uniform(0, 2 * math.pi), rng.uniform(300, 1700), rng.uniform(1.5, 5), rng.uniform(0, 0.15)) for _ in range(160)]


def composite_cracks(ice, crack_arr):
    c = Image.fromarray((np.clip(crack_arr, 0, 1) * 255).astype(np.uint8))
    glow = np.asarray(c.filter(ImageFilter.GaussianBlur(7)), np.float32) / 255.0
    shadow = np.asarray(c.filter(ImageFilter.GaussianBlur(2)).transform(c.size, Image.AFFINE, (1, 0, -3, 0, 1, -3)), np.float32) / 255.0
    a = np.asarray(ice, np.float32)
    a *= (1 - shadow[..., None] * 0.45)
    a += glow[..., None] * np.array([150, 210, 255]) * 1.4
    a = a * (1 - crack_arr[..., None]) + np.array([248, 253, 255]) * crack_arr[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def crack_radius(t):
    # propagation en trois "coups"
    r = 0.0
    r += 380 * ease_out_cubic(seg(t, 0.12, 0.45))
    r += 380 * ease_out_cubic(seg(t, 0.75, 1.05))
    r += 700 * ease_out_cubic(seg(t, 1.2, 1.85))
    return r


def shake(t):
    s = 0.0
    for t0, amp in ((0.12, 14), (0.75, 18), (1.2, 22), (1.95, 30)):
        if t >= t0:
            k = t - t0
            s += amp * math.exp(-k * 14)
    return s * math.sin(t * 95), s * math.cos(t * 83)


def render_ice(t):
    R = crack_radius(t)
    vis = A.crack * np.clip((R - A.ice_dist) / 40.0, 0, 1)
    img = composite_cracks(A.ice, vis)
    # éclat lumineux au point d'impact
    flash = 0.0
    for t0 in (0.12, 0.75, 1.2):
        if t >= t0:
            flash += math.exp(-(t - t0) * 9)
    img = img.convert("RGBA")
    if flash > 0.02:
        paste_alpha(img, A.glow_warm[70].resize((420, 420)), IMPACT[0], IMPACT[1], min(1, flash * 0.9))
        paste_alpha(img, A.star[34].resize((260, 260)), IMPACT[0], IMPACT[1], min(1, flash))
    dx, dy = shake(t)
    return img.crop((IM + dx, IM + dy, IM + dx + W, IM + dy + H))


def render_shatter(frame, t):
    tt = t - 1.95
    px, py = IMPACT[0] - IM, IMPACT[1] - IM
    for s in A.shards:
        delay = s["dist"] / 4000.0
        u = max(0.0, tt - delay) * s["spd"]
        if u <= 0:
            paste_alpha(frame, s["img"], s["cx"] - IM, s["cy"] - IM)
            continue
        closeness = 1 - min(1, s["dist"] / 1300)
        scale = 1 + (1.2 + 2.8 * closeness) * u ** 1.4
        dirx, diry = s["cx"] - IM - px, s["cy"] - IM - py
        cx = px + dirx * (1 + 2.2 * u + 1.5 * u * u)
        cy = py + diry * (1 + 2.2 * u + 1.5 * u * u) + 500 * u * u
        alpha = 1 - smooth((u - 0.25) / 0.55)
        if alpha <= 0.01:
            continue
        img = transform(s["img"], scale=scale, angle=s["rot"] * u)
        paste_alpha(frame, img, cx, cy, alpha)
    # poussière de glace
    d = ImageDraw.Draw(frame)
    for ang, spd, r, dl in A.debris:
        u = tt - dl
        if u <= 0 or u > 1.0:
            continue
        x = px + math.cos(ang) * spd * u
        y = py + math.sin(ang) * spd * u + 300 * u * u
        rr = r * (1 + 2 * u)
        a = int(230 * (1 - u))
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(225, 243, 255, a))
    # flash blanc-bleu
    fl = math.exp(-max(0, tt) * 7) * 0.85
    if fl > 0.01:
        frame.alpha_composite(Image.new("RGBA", (W, H), (230, 245, 255, int(255 * fl))))


# --------------------------------------------------------------------------- textes


def prepare_texts():
    T = {}
    T["plein"] = text_block([
        text_line("PLEIN DE", FONT_BLACK, 112, WHITE, tracking=0.02),
        text_line("CADEAUX", FONT_BLACK, 168, RED, stroke=5, stroke_fill=WHITE, tracking=0.01),
        text_line("POUR VOUS !", FONT_BLACK, 112, WHITE, tracking=0.02, emoji="🎁"),
    ], spacing=0.02, glow=(255, 70, 80), glow_radius=26)
    T["plein_lines"] = None
    T["normalement"] = text_block([text_line("Normalement… ce n’est pas sûr !", FONT_MED_IT, 50, (245, 245, 245), emoji="👀")], shadow=0.95)
    T["prepare"] = text_block([text_line("Quelque chose se prépare…", FONT_SEMI, 70, WHITE, tracking=0.03)], shadow=0.9, glow=(255, 214, 150), glow_radius=20)
    T["prets"] = text_block([text_line("Êtes-vous prêts ?", FONT_XBOLD, 96, WHITE, tracking=0.02, emoji="👀")], shadow=0.9, glow=(255, 214, 150), glow_radius=22)
    T["noel1"] = text_block([text_line("NOËL ARRIVE", FONT_BLACK, 136, gradient=(GOLD_TOP, GOLD_BOT), tracking=0.03)], shadow=0.9, glow=(255, 190, 90), glow_radius=30)
    T["noel2"] = text_block([text_line("CHEZ UNITED GAMES", FONT_BLACK, 74, WHITE, tracking=0.05, emoji="🎄")], shadow=0.9, glow=(255, 60, 70), glow_radius=20)
    T["restez"] = text_block([text_line("Restez connectés…", FONT_SEMI, 52, (250, 245, 235), tracking=0.04, emoji="🎁")], shadow=0.95)
    # lignes séparées du titre scène 2 pour l'animation décalée
    T["p1"] = text_block([text_line("PLEIN DE", FONT_BLACK, 112, WHITE, tracking=0.02)], glow=(255, 70, 80), glow_radius=24)
    T["p2"] = text_block([text_line("CADEAUX", FONT_BLACK, 168, RED, stroke=5, stroke_fill=WHITE, tracking=0.01)], glow=(255, 60, 70), glow_radius=30)
    T["p3"] = text_block([text_line("POUR VOUS !", FONT_BLACK, 112, WHITE, tracking=0.02, emoji="🎁")], glow=(255, 70, 80), glow_radius=24)
    A.T = T


def draw_texts(frame, t):
    T = A.T
    # ---- Scène 2 : PLEIN DE / CADEAUX / POUR VOUS !
    if 3.0 <= t < 7.1:
        out = seg(t, 6.55, 7.0)
        ys = (560, 720, 885)
        for i, key in enumerate(("p1", "p2", "p3")):
            t0 = 3.25 + i * 0.16
            u = seg(t, t0, t0 + 0.45)
            if u <= 0:
                continue
            sc = lerp(1.9, 1.0, ease_out_back(u, 2.2)) * (1 + 0.012 * math.sin((t - t0) * 2.2))
            if key == "p2" and t > 4.0:  # petit "battement" sur CADEAUX
                sc *= 1 + 0.035 * math.exp(-(t - 4.0) * 5) * math.sin((t - 4.0) * 25)
            sc *= 1 + 0.12 * out
            alpha = smooth(u * 2.2) * (1 - out)
            img = transform(T[key], scale=sc, blur=8 * (1 - smooth(u * 1.6)) + 14 * out)
            paste_alpha(frame, img, W / 2, ys[i] - 40 * out, alpha)
        u = seg(t, 4.35, 4.85)
        if u > 0:
            ang = 2.5 * math.sin((t - 4.35) * 3.0) * (1 - out)
            img = transform(T["normalement"], scale=lerp(0.8, 1.0, ease_out_back(u)), angle=ang)
            paste_alpha(frame, img, W / 2, lerp(1290, 1250, ease_out_cubic(u)), smooth(u) * (1 - out))
    # ---- Scène 3
    for key, a, b, y in (("prepare", 7.35, 9.65, 1330), ("prets", 9.85, 11.85, 1330)):
        if a <= t < b:
            u_in = seg(t, a, a + 0.7)
            u_out = seg(t, b - 0.55, b)
            blur = 16 * (1 - ease_out_cubic(u_in)) + 12 * u_out
            sc = lerp(1.12, 1.0, ease_out_cubic(u_in)) * lerp(1.0, 1.04, seg(t, a, b))
            img = transform(T[key], scale=sc, blur=blur)
            paste_alpha(frame, img, W / 2, y - 30 * u_out, smooth(u_in) * (1 - smooth(u_out)))
    # ---- Scène 4
    if t >= 13.9:
        fade = 1 - seg(t, 17.0, 17.85)
        u = seg(t, 13.9, 14.55)
        img = transform(T["noel1"], scale=lerp(1.35, 1.0, ease_out_cubic(u)), blur=10 * (1 - ease_out_cubic(u)))
        paste_alpha(frame, img, W / 2, 1215, smooth(u * 1.5) * fade)
        u2 = seg(t, 14.25, 14.85)
        img = transform(T["noel2"], scale=lerp(0.85, 1.0, ease_out_back(u2)), blur=6 * (1 - ease_out_cubic(u2)))
        paste_alpha(frame, img, W / 2, lerp(1370, 1338, ease_out_cubic(u2)), smooth(u2 * 1.4) * fade)
        u3 = seg(t, 15.3, 16.0)
        if u3 > 0:
            img = transform(T["restez"], blur=6 * (1 - ease_out_cubic(u3)))
            paste_alpha(frame, img, W / 2, lerp(1480, 1455, ease_out_cubic(u3)), smooth(u3) * fade)


# --------------------------------------------------------------------------- scène


def camera(t):
    """zoom + point visé pour l'arrière-plan."""
    lx, ly = A.logo_center
    if t < 3.0:
        z = lerp(1.12, 1.03, ease_out_cubic(seg(t, 1.95, 3.0)))
        return z, (W / 2, H / 2)
    if t < 7.0:
        return lerp(1.03, 1.06, seg(t, 3, 7)), (W / 2, lerp(H / 2, 900, seg(t, 3, 7)))
    if t < 12.0:
        u = ease_in_out(seg(t, 7, 12))
        return lerp(1.06, 1.28, u), (W / 2, lerp(900, ly, u))
    u = ease_in_out(seg(t, 12.0, 15.0))
    return lerp(1.28, 1.0, u), (W / 2, lerp(ly, H / 2, u))


def logo_state(t):
    """(flou, échelle, centre y, opacité, halo)"""
    blur = 30.0
    if t >= 12.0:
        blur = lerp(30, 1.2, ease_in_out(seg(t, 12.0, 13.8)))
    if t < 7.0:
        sc = lerp(1.0, 1.04, seg(t, 2, 7))
        y = 840
    elif t < 12.0:
        sc = lerp(1.04, 1.32, ease_in_out(seg(t, 7, 12)))
        y = lerp(840, 860, seg(t, 7, 12))
    else:
        u = ease_in_out(seg(t, 12.0, 14.2))
        sc, y = lerp(1.32, 0.82, u), lerp(860, 700, u)
    op = 0.78 if t < 12 else lerp(0.78, 1.0, seg(t, 12, 13.6))
    halo = 0.35 + 0.15 * math.sin(t * 2.0) + (0.25 * seg(t, 13.0, 14.0))
    return blur, sc, y, op, halo


def draw_logo(frame, t):
    blur, sc, y, op, halo = logo_state(t)
    a = A.logo_alpha
    if blur > 0.4:
        a = a.filter(ImageFilter.GaussianBlur(blur))
    # halo chaud
    g = A.logo_alpha.filter(ImageFilter.GaussianBlur(max(28, blur * 1.6)))
    glow = Image.new("RGBA", a.size, (255, 222, 170, 255))
    glow.putalpha(g.point(lambda v: int(v * halo)))
    logo = Image.new("RGBA", a.size, (250, 250, 252, 255))
    logo.putalpha(a)
    glow.alpha_composite(logo)
    glow = transform(glow, scale=sc)
    paste_alpha(frame, glow, W / 2, y, op)
    # bonnet
    if t >= 13.1:
        u = seg(t, 13.1, 13.75)
        drop = (1 - ease_out_back(u, 2.4)) * -260
        hat = transform(A.hat_layer, scale=sc, angle=lerp(-25, 0, ease_out_back(u, 2.0)), blur=max(0.0, blur * 0.5))
        hx, hy = A.hat_rel
        paste_alpha(frame, hat, W / 2 + hx * sc, y + hy * sc + drop, smooth(u * 2.5))
        # gerbe d'étincelles à l'atterrissage
        k = t - 13.6
        if 0 < k < 1.0:
            rng = np.random.default_rng(5)
            for i in range(28):
                ang = rng.uniform(0, 2 * math.pi)
                sp = rng.uniform(120, 420)
                sx = W / 2 + hx * sc + math.cos(ang) * sp * k
                sy = y + hy * sc + math.sin(ang) * sp * k + 120 * k * k
                st = A.star[int(rng.choice([10, 16, 24]))]
                paste_alpha(frame, st, sx, sy, (1 - k) * 0.95)


def draw_garland(bg, t, power):
    d = ImageDraw.Draw(bg, "RGBA")
    d.line(A.garland, fill=(20, 26, 18, 255), width=4, joint="curve")
    n = len(A.garland)
    for i, (x, y) in enumerate(A.garland[1:-1], 1):
        on = 1.0
        if 12.0 <= t:  # allumage en cascade
            on = 0.45 + 0.55 * smooth((t - 12.0 - i * 0.06) / 0.25)
        tw = 0.75 + 0.25 * math.sin(t * 3.1 + i * 1.9)
        p = power * on * tw
        paste_alpha(bg, A.glow_warm[46], x, y + 14, clamp(p * 0.75))
        paste_alpha(bg, A.bulb, x, y + 14, clamp(0.5 + p * 0.5))
    for i, (x, y) in enumerate(A.tree_lights):
        tw = 0.7 + 0.3 * math.sin(t * 2.3 + i * 2.7)
        paste_alpha(bg, A.glow_warm[30], x, y, clamp(power * tw * 0.8))


def scene_power(t):
    """intensité lumineuse : scène 3 plus sombre, scène 4 plus lumineuse."""
    p = 0.65
    p -= 0.12 * smooth(seg(t, 7.0, 8.0)) * (1 - seg(t, 11.8, 12.4))
    p += 0.55 * smooth(seg(t, 12.0, 13.5))
    return p


def render_scene(t):
    power = scene_power(t)
    bg = A.bg.copy().convert("RGBA")
    # bokeh
    for i, (x, y, r, ph, a) in enumerate(A.bokeh):
        paste_alpha(bg, A.glow_warm[r], x + 20 * math.sin(t * 0.3 + ph), y - 12 * t, a * (0.7 + 0.3 * math.sin(t + ph)) * power)
    draw_garland(bg, t, power)
    # assombrissement global scène 3
    dark = 0.28 * smooth(seg(t, 7.0, 8.2)) * (1 - smooth(seg(t, 11.8, 12.8)))
    if dark > 0:
        bg.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 8, int(255 * dark))))
    # caméra
    z, (cx, cy) = camera(t)
    bw, bh = W / z, H / z
    x0 = clamp(cx - bw / 2, 0, W - bw)
    y0 = clamp(cy - bh / 2, 0, H - bh)
    frame = bg.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + bw, y0 + bh))
    draw_logo(frame, t)
    # brume
    fog_a = 0.35 + 0.55 * smooth(seg(t, 7.0, 8.5)) * (1 - seg(t, 12.0, 14.0)) * 1.0
    off = int((t * 28) % W)
    fog = A.fog.crop((off, 0, off + W, H))
    paste_alpha(frame, fog, W / 2, H / 2, fog_a * 0.6)
    # scintillements
    for x, y, s, ph, f in A.twinkles:
        a = max(0.0, math.sin(t * f + ph)) ** 3 * (0.5 + 0.5 * power)
        paste_alpha(frame, A.star[s], x, y, a)
    # neige
    n_active = int(170 + 130 * smooth(seg(t, 12.0, 13.5)))
    wind = 25 * math.sin(t * 0.4)
    for i in range(n_active):
        x0f, y0f, z_, ph, fr, op = A.flakes[i]
        r = int(2 + z_ * 13)
        v = 55 + z_ * 260 + 60 * smooth(seg(t, 12, 13.5))
        y = (y0f + v * t) % (H + 60) - 30
        x = x0f + 30 * math.sin(t * fr + ph) + wind * z_
        paste_alpha(frame, A.snow[r], x, y, op * (0.55 + 0.45 * (1 - z_ * 0.5)))
    # scrim pour le texte final
    s = smooth(seg(t, 13.6, 14.4))
    if s > 0:
        paste_alpha(frame, A.scrim, W / 2, H / 2, s)
    return frame


def render_frame(t):
    if t < 1.95:
        frame = render_ice(t)
    else:
        frame = render_scene(t)
        draw_texts(frame, t)
        if t < 3.2:
            render_shatter(frame, t)
    # fondu au noir final
    fb = seg(t, 17.0, 17.9)
    if fb > 0:
        frame.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * smooth(fb)))))
    return frame.convert("RGB")


def _render_idx(i):
    return render_frame(i / FPS).tobytes()


def main():
    os.makedirs(OUT, exist_ok=True)
    prepare()
    if len(sys.argv) > 2 and sys.argv[1] == "--preview":
        for ts in sys.argv[2:]:
            t = float(ts)
            render_frame(t).save(os.path.join(OUT, f"preview_{t:05.2f}.png"))
            print("preview", t)
        return
    out = os.path.join(OUT, "united_games_teaser_noel.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
           "-profile:v", "high", "-movflags", "+faststart", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(os.cpu_count()) as pool:
        for i, buf in enumerate(pool.imap(_render_idx, range(NFRAMES), chunksize=2)):
            proc.stdin.write(buf)
            if i % 30 == 0:
                print(f"frame {i}/{NFRAMES}", flush=True)
    proc.stdin.close()
    proc.wait()
    print("OK ->", out)


if __name__ == "__main__":
    main()
