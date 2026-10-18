"""Montage complet : cadrage dynamique, motion design, sous-titres mot par mot, mixage.

Usage : python3 build.py <source.mov> <dossier_travail> <sortie.mp4> [--preview N]
Dépendances : ffmpeg, numpy, pillow. Les sons/musique sont générés par synth_audio.py.
"""
import sys, os, json, math, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from edl import CLIPS, FPS

SRC, WORK, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
PREVIEW = None
if "--preview" in sys.argv:
    PREVIEW = [float(x) for x in sys.argv[sys.argv.index("--preview") + 1].split(",")]
os.makedirs(WORK, exist_ok=True)
HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1080, 1920
SR = 48000

FONT_DIR = "/usr/share/fonts/opentype/inter"
F_BLACK = f"{FONT_DIR}/Inter-Black.otf"
F_XBOLD = f"{FONT_DIR}/Inter-ExtraBold.otf"
F_SEMI = f"{FONT_DIR}/Inter-SemiBold.otf"
YELLOW = (255, 214, 10)
WHITE = (255, 255, 255)
RED = (255, 72, 60)
BLUE = (90, 170, 255)

# Étalonnage : exposition / contraste doux, peau naturelle, ombres légèrement froides,
# hautes lumières légèrement chaudes, netteté subtile, vignettage discret.
GRADE = ("eq=contrast=1.06:brightness=0.012:saturation=1.08:gamma=1.03,"
         "curves=master='0/0.02 0.25/0.225 0.5/0.5 0.75/0.785 1/0.975':blue='0/0.03 0.5/0.49 1/0.96',"
         "colorbalance=rs=-0.02:bs=0.035:rm=0.012:rh=0.03:bh=-0.03,"
         "unsharp=5:5:0.35:5:5:0,vignette=angle=PI/5:mode=forward")


# ------------------------------------------------------------------ easing
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out_cubic(x):
    x = clamp(x); return 1 - (1 - x) ** 3


def ease_in_out(x):
    x = clamp(x); return x * x * (3 - 2 * x)


def ease_out_back(x, s=1.7):
    x = clamp(x); x -= 1; return 1 + x * x * ((s + 1) * x + s)


def ease_in_cubic(x):
    x = clamp(x); return x ** 3


# ------------------------------------------------------------------ timeline
def letters(w):
    return max(1, sum(c.isalnum() for c in w))


def time_words(clip):
    """Calcule (début, fin) source de chaque mot à partir des ancres + interpolation."""
    s0, s1 = clip["src"]
    ws = clip["words"]
    t = [a for _, a, _ in ws]
    if t[0] is None:
        t[0] = s0 + 0.05
    idx = [i for i, v in enumerate(t) if v is not None]
    # fin virtuelle
    tend = s1 - 0.04
    for k, i in enumerate(idx):
        j = idx[k + 1] if k + 1 < len(idx) else None
        tb = t[j] if j is not None else tend
        jj = j if j is not None else len(ws)
        span = list(range(i, jj))
        wts = [letters(ws[m][0]) + 2 for m in span]
        tot = sum(wts); acc = 0
        for m, wt in zip(span, wts):
            if t[m] is None:
                t[m] = t[i] + (tb - t[i]) * acc / tot
            acc += wt
    out = []
    for i, (txt, _, fl) in enumerate(ws):
        st = t[i]
        en = t[i + 1] if i + 1 < len(ws) else tend
        out.append(dict(text=txt, s=st, e=max(en, st + 0.08), key="K" in fl, brk="B" in fl))
    return out


timeline = []
cur = 0
for c in CLIPS:
    n = int(round((c["src"][1] - c["src"][0]) * FPS))
    c = dict(c, n=n, f0=cur, t0=cur / FPS, words_t=time_words(c))
    timeline.append(c)
    cur += n
TOTAL_FRAMES = cur
TOTAL = cur / FPS
CL = {c["id"]: c for c in timeline}


def o(cid, src_t):
    """Temps source d'un clip -> temps de sortie."""
    c = CL[cid]
    return c["t0"] + (src_t - c["src"][0])


def wt(cid, text, nth=0):
    """Temps de sortie du n-ième mot commençant par `text` dans un clip."""
    k = 0
    for w in CL[cid]["words_t"]:
        if w["text"].lower().startswith(text.lower()):
            if k == nth:
                return o(cid, w["s"])
            k += 1
    raise KeyError(text)


def cstart(cid):
    return CL[cid]["t0"]


def cend(cid):
    c = CL[cid]
    return c["t0"] + c["n"] / FPS


# ------------------------------------------------------------------ sous-titres (groupes)
CAP_SIZE = 82
CAP_Y = 1395
cap_font = ImageFont.truetype(F_BLACK, CAP_SIZE)

groups = []
for c in timeline:
    g = []
    for w in c["words_t"]:
        g.append(w)
        if w["brk"] or len(g) >= 4:
            groups.append((c, g)); g = []
    if g:
        groups.append((c, g))

captions = []  # dicts : t0, t1, words=[(sprite_key, x, y, t_on, key)]
for gi, (c, g) in enumerate(groups):
    t0 = o(c["id"], g[0]["s"]) - 0.03
    t1 = o(c["id"], g[-1]["e"])
    captions.append(dict(c=c, g=g, t0=t0, t1=t1))
for i, cap in enumerate(captions):
    # tenir le groupe jusqu'au suivant (si proche), sans dépasser la fin du clip
    nxt = captions[i + 1]["t0"] if i + 1 < len(captions) else TOTAL
    same_clip = i + 1 < len(captions) and captions[i + 1]["c"]["id"] == cap["c"]["id"]
    hold = min(nxt, cap["t1"] + 0.45)
    cap["t1"] = hold if same_clip else min(hold, cend(cap["c"]["id"]))
    if cap["t1"] <= cap["t0"]:
        cap["t1"] = cap["t0"] + 0.2

SPRITES = {}


def text_sprite(text, font_path, size, fill, stroke=0, stroke_fill=(0, 0, 0), shadow=True, tracking=0):
    key = (text, font_path, size, fill, stroke, shadow, tracking)
    if key in SPRITES:
        return SPRITES[key]
    f = ImageFont.truetype(font_path, size)
    pad = stroke + 24
    if tracking:
        widths = [f.getlength(ch) + tracking for ch in text]
        tw = int(sum(widths) - tracking)
    else:
        tw = int(f.getlength(text))
    asc, desc = f.getmetrics()
    th = asc + desc
    im = Image.new("RGBA", (tw + 2 * pad, th + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    def draw_on(dd, fillc, sw):
        if tracking:
            x = pad
            for ch, wdt in zip(text, widths):
                dd.text((x, pad), ch, font=f, fill=fillc, stroke_width=sw, stroke_fill=stroke_fill)
                x += wdt
        else:
            dd.text((pad, pad), text, font=f, fill=fillc, stroke_width=sw, stroke_fill=stroke_fill)

    if shadow:
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        draw_on(ImageDraw.Draw(sh), (0, 0, 0, 150), stroke + 2)
        sh = sh.filter(ImageFilter.GaussianBlur(9))
        sh2 = Image.new("RGBA", im.size, (0, 0, 0, 0)); sh2.alpha_composite(sh, (0, 7))
        im.alpha_composite(sh2)
    draw_on(d, fill + (255,), stroke)
    SPRITES[key] = (im, pad)
    return SPRITES[key]


def layout_caption(cap):
    words = [w["text"].upper() for w in cap["g"]]
    space = cap_font.getlength(" ")
    widths = [cap_font.getlength(t) for t in words]
    total = sum(widths) + space * (len(words) - 1)
    lines = [list(range(len(words)))]
    if total > 940 and len(words) > 1:
        # coupe en 2 lignes équilibrées
        best = None
        for k in range(1, len(words)):
            a = sum(widths[:k]) + space * (k - 1); b = sum(widths[k:]) + space * (len(words) - k - 1)
            if best is None or max(a, b) < best[0]:
                best = (max(a, b), k)
        k = best[1]; lines = [list(range(k)), list(range(k, len(words)))]
    pos = []
    lh = CAP_SIZE * 1.12
    y0 = CAP_Y - (len(lines) - 1) * lh / 2
    for li, line in enumerate(lines):
        lw = sum(widths[i] for i in line) + space * (len(line) - 1)
        x = W / 2 - lw / 2
        for i in line:
            pos.append((i, x + widths[i] / 2, y0 + li * lh))
            x += widths[i] + space
    pos.sort()
    cap["layout"] = [(words[i], cx, cy) for i, cx, cy in pos]


for cap in captions:
    layout_caption(cap)


# ------------------------------------------------------------------ dessin
def paste(layer, sprite, cx, cy, scale=1.0, alpha=1.0, blur=0.0, anchor="c"):
    im, pad = sprite
    if alpha <= 0.01 or scale <= 0.01:
        return
    if abs(scale - 1) > 0.005:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BICUBIC)
    if blur > 0.3:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    if alpha < 0.999:
        a = im.getchannel("A").point(lambda v: int(v * alpha))
        im = im.copy(); im.putalpha(a)
    if anchor == "c":
        x, y = int(cx - im.width / 2), int(cy - im.height / 2)
    else:  # gauche
        x, y = int(cx - pad * scale), int(cy - im.height / 2)
    layer.alpha_composite(im, (max(0, x), max(0, y)), (max(0, -x), max(0, -y)))


def rounded_panel(w, h, r, fill, outline=None, width=0):
    key = ("panel", w, h, r, fill, outline, width)
    if key in SPRITES:
        return SPRITES[key]
    pad = 30
    im = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 8, pad + w, pad + h + 8), r, fill=(0, 0, 0, 90))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(12)))
    ImageDraw.Draw(im).rounded_rectangle((pad, pad, pad + w, pad + h), r, fill=fill, outline=outline, width=width)
    SPRITES[key] = (im, pad)
    return SPRITES[key]


def anim_in_out(t, t_in, t_out, d_in=0.32, d_out=0.22):
    """Retourne (progression entrée 0..1, alpha) pour un élément visible entre t_in et t_out."""
    if t < t_in or t > t_out:
        return 0, 0
    p = ease_out_cubic((t - t_in) / d_in)
    q = 1 - ease_in_cubic((t - (t_out - d_out)) / d_out) if t > t_out - d_out else 1
    return p, min(p * 1.4, 1) * q


def draw_captions(layer, t):
    for cap in captions:
        if not (cap["t0"] <= t < cap["t1"]):
            continue
        out_a = 1 - ease_in_cubic((t - (cap["t1"] - 0.07)) / 0.07) if t > cap["t1"] - 0.07 else 1
        for (txt, cx, cy), w in zip(cap["layout"], cap["g"]):
            ton = o(cap["c"]["id"], w["s"]) - 0.02
            if t < ton:
                continue
            dt = t - ton
            sc = 0.55 + 0.45 * ease_out_back(dt / 0.16, 2.6)
            a = clamp(dt / 0.06) * out_a
            active = o(cap["c"]["id"], w["s"]) <= t < o(cap["c"]["id"], w["e"])
            col = YELLOW if w["key"] else WHITE
            sp = text_sprite(txt, F_BLACK, CAP_SIZE, col, stroke=7)
            sc *= 1.06 if (active and w["key"]) else 1.0
            paste(layer, sp, cx, cy - 18 * (1 - ease_out_cubic(dt / 0.16)), sc, a,
                  blur=2.5 * (1 - clamp(dt / 0.08)))


def chapter_tag(layer, t, num, label, t_in, t_out):
    p, a = anim_in_out(t, t_in, t_out)
    if a <= 0:
        return
    sp_num = text_sprite(num, F_BLACK, 34, YELLOW, shadow=False)
    sp_lab = text_sprite(label, F_XBOLD, 34, WHITE, shadow=False, tracking=2)
    wlab = sp_lab[0].width - 2 * sp_lab[1]
    wnum = sp_num[0].width - 2 * sp_num[1]
    pw = wnum + wlab + 26 + 52
    panel = rounded_panel(int(pw), 64, 32, (12, 12, 14, 175))
    x = 56 - 60 * (1 - p); y = 236
    paste(layer, panel, x + pw / 2, y, 1, a, blur=4 * (1 - p))
    paste(layer, sp_num, x + 26, y, 1, a, anchor="l")
    paste(layer, sp_lab, x + 26 + wnum + 16, y, 1, a, anchor="l")


def title_card(layer, t, t_in, t_out):
    for k, (txt, font, size, col, dy, trk) in enumerate([
            ("BOÎTE MANUELLE", F_BLACK, 104, WHITE, 300, 0),
            ("EXPLIQUÉE SIMPLEMENT", F_XBOLD, 40, WHITE, 410, 6)]):
        p, a = anim_in_out(t, t_in + 0.09 * k, t_out, 0.38, 0.25)
        if a <= 0:
            continue
        sp = text_sprite(txt, font, size, col, stroke=0, tracking=trk)
        paste(layer, sp, W / 2, dy + 46 * (1 - p), 1, a, blur=5 * (1 - p))
    # barre jaune qui se déploie
    p, a = anim_in_out(t, t_in + 0.18, t_out, 0.45, 0.25)
    if a > 0:
        bw = int(560 * ease_out_cubic(p))
        if bw > 4:
            d = ImageDraw.Draw(layer)
            col = YELLOW + (int(255 * a),)
            d.rounded_rectangle((W / 2 - bw / 2, 362, W / 2 + bw / 2, 374), 6, fill=col)


def compare_cards(layer, t, t_left, t_right, t_out):
    for k, (tin, x, lab, val, col) in enumerate([
            (t_left, 285, "MANUELLE", "C'EST TOI", YELLOW),
            (t_right, 795, "AUTO", "TOUTE SEULE", WHITE)]):
        p, a = anim_in_out(t, tin, t_out, 0.34, 0.22)
        if a <= 0:
            continue
        sc = 0.8 + 0.2 * ease_out_back(clamp((t - tin) / 0.34), 2.2)
        y = 380 + 30 * (1 - p)
        paste(layer, rounded_panel(400, 168, 30, (12, 12, 14, 180),
                                   outline=(col + (200,)) if k == 0 else (255, 255, 255, 60), width=3),
              x, y, sc, a, blur=3 * (1 - p))
        paste(layer, text_sprite(lab, F_XBOLD, 32, (200, 200, 205), shadow=False, tracking=5),
              x, y - 36 * sc, sc, a)
        paste(layer, text_sprite(val, F_BLACK, 58, col, shadow=False), x, y + 22 * sc, sc, a)
    # « VS » au centre
    p, a = anim_in_out(t, t_right + 0.05, t_out, 0.3, 0.22)
    if a > 0:
        paste(layer, text_sprite("VS", F_BLACK, 40, WHITE, stroke=4), 540, 380, 0.6 + 0.4 * ease_out_back(p), a)


def gearbox(layer, t, t_in, t_move, t_five, t_out):
    p, a = anim_in_out(t, t_in, t_out, 0.35, 0.22)
    if a <= 0:
        return
    cx, cy = 540, 375 + 30 * (1 - p)
    paste(layer, rounded_panel(420, 250, 34, (12, 12, 14, 180)), cx, cy, 1, a, blur=3 * (1 - p))
    d = ImageDraw.Draw(layer)
    al = int(220 * a)
    xs = [cx - 120, cx, cx + 120]; yt, yb = cy - 78, cy + 78
    line = (255, 255, 255, int(150 * a))
    d.rounded_rectangle((xs[0] - 4, cy - 4, xs[2] + 4, cy + 4), 4, fill=line)
    for x in xs:
        d.rounded_rectangle((x - 4, yt, x + 4, yb), 4, fill=line)
    gears = {1: (xs[0], yt), 2: (xs[0], yb), 3: (xs[1], yt), 4: (xs[1], yb), 5: (xs[2], yt), 6: (xs[2], yb)}
    lit = t >= t_five
    for g, (x, y) in gears.items():
        is5 = g == 5 and lit
        s5 = ease_out_back(clamp((t - t_five) / 0.25), 3) if is5 else 1
        r = 27 * (1.15 * s5 if is5 else 1)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(YELLOW + (al,)) if is5 else (40, 40, 44, al),
                  outline=(255, 255, 255, int(120 * a)), width=2)
        sp = text_sprite(str(g), F_BLACK, 30, (15, 15, 15) if is5 else WHITE, shadow=False)
        paste(layer, sp, x, y + 1, 1, a)
    # pommeau : du point mort vers la 5e
    m = ease_in_out((t - t_move) / 0.45)
    if m <= 0.5:
        kx, ky = cx + (xs[2] - cx) * (m / 0.5), cy
    else:
        kx, ky = xs[2], cy + (yt - cy) * ((m - 0.5) / 0.5)
    if not lit:
        d.ellipse((kx - 13, ky - 13, kx + 13, ky + 13), fill=YELLOW + (al,))


def badge_conso(layer, t, t_in, t_out, label="CONSO"):
    p, a = anim_in_out(t, t_in, t_out, 0.3, 0.2)
    if a <= 0:
        return
    sc = 0.6 + 0.4 * ease_out_back(clamp((t - t_in) / 0.3), 2.5)
    sp1 = text_sprite(label, F_BLACK, 64, WHITE, shadow=False)
    sp2 = text_sprite("↑", F_BLACK, 64, RED, shadow=False)
    w1 = sp1[0].width - 2 * sp1[1]
    pw = w1 + 60 + 70
    paste(layer, rounded_panel(int(pw), 104, 52, (12, 12, 14, 185), outline=RED + (210,), width=3),
          540, 370, sc, a)
    bob = 6 * math.sin((t - t_in) * 9) * (1 - clamp((t - t_in) / 1.2))
    paste(layer, sp1, 540 - (pw / 2 - 35 - w1 / 2) * sc, 370, sc, a)
    paste(layer, sp2, 540 + (pw / 2 - 58) * sc, 366 - bob, sc, a)


def rev_gauge(layer, t, keys, t_in, t_out):
    """keys : liste (temps, position 0..1) ; 0 = sous-régime, 1 = sur-régime."""
    p, a = anim_in_out(t, t_in, t_out, 0.35, 0.22)
    if a <= 0:
        return
    cx, cy = 540, 385 + 30 * (1 - p)
    paste(layer, rounded_panel(860, 190, 34, (12, 12, 14, 180)), cx, cy, 1, a, blur=3 * (1 - p))
    d = ImageDraw.Draw(layer)
    x0, x1, by = cx - 360, cx + 360, cy + 22
    n = 36
    # position de l'aiguille
    pos, prev = 0.5, 0.5
    for tk, v in keys:
        if t >= tk:
            prev = pos; pos = v; tlast = tk
    if any(t >= tk for tk, _ in keys):
        pos = prev + (pos - prev) * ease_out_back(clamp((t - tlast) / 0.42), 1.4)
    for i in range(n):
        u = i / (n - 1)
        col = tuple(int(BLUE[k] + (WHITE[k] - BLUE[k]) * (u / 0.5)) if u < 0.5 else
                    int(WHITE[k] + (RED[k] - WHITE[k]) * ((u - 0.5) / 0.5)) for k in range(3))
        lit = abs(u - pos) < 0.5 / n * 2.2
        hh = 30 if lit else 18
        xa = x0 + u * (x1 - x0)
        d.rounded_rectangle((xa - 7, by - hh / 2, xa + 7, by + hh / 2), 4,
                            fill=col + (int((255 if lit else 120) * a),))
    nx = x0 + clamp(pos, 0, 1) * (x1 - x0)
    d.polygon([(nx - 14, by - 40), (nx + 14, by - 40), (nx, by - 20)], fill=YELLOW + (int(255 * a),))
    for lab, x, side in (("SOUS-RÉGIME", x0 + 95, 0), ("SUR-RÉGIME", x1 - 85, 1)):
        on = (pos < 0.25 and side == 0) or (pos > 0.75 and side == 1)
        col = (BLUE if side == 0 else RED) if on else (170, 170, 175)
        paste(layer, text_sprite(lab, F_BLACK, 36 if on else 32, col, shadow=False), x, cy - 46, 1, a)
    paste(layer, text_sprite("OK", F_XBOLD, 28, (170, 170, 175), shadow=False, tracking=4), cx, cy - 46, 1, a)


def sound_bars(layer, t, t_in, t_out):
    p, a = anim_in_out(t, t_in, t_out, 0.35, 0.22)
    if a <= 0:
        return
    d = ImageDraw.Draw(layer)
    cx, cy = 540, 380
    n = 13
    for i in range(n):
        u = (i - (n - 1) / 2) / ((n - 1) / 2)
        env_ = 1 - abs(u) ** 1.6
        h = (18 + 70 * env_ * (0.55 + 0.45 * math.sin(t * 11 + i * 1.3) * math.sin(t * 4.3 + i * 0.7))) * p
        x = cx + u * 230
        col = YELLOW if abs(u) < 0.2 else WHITE
        d.rounded_rectangle((x - 8, cy - h, x + 8, cy + h), 8, fill=col + (int(230 * a),))


# ------------------------------------------------------------------ graphismes planifiés
T1 = cstart("c1")
GFX = []
GFX.append(lambda L, t: title_card(L, t, T1 + 0.05, T1 + 2.55))
GFX.append(lambda L, t: chapter_tag(L, t, "01", "L'EMBRAYAGE", T1 + 2.7, cend("c1") - 0.05))
GFX.append(lambda L, t: chapter_tag(L, t, "02", "MANUELLE VS AUTO", cstart("c2") + 0.1, cend("c2") - 0.05))
GFX.append(lambda L, t: compare_cards(L, t, wt("c2", "toi"), wt("c2", "boîte"), cend("c2") - 0.05))
GFX.append(lambda L, t: chapter_tag(L, t, "03", "LES VITESSES", cstart("c7") + 0.1, cend("c7") - 0.05))
GFX.append(lambda L, t: gearbox(L, t, cstart("c7") + 0.08, wt("c7", "vitesse"), wt("c7", "5"), cend("c7") - 0.02))
GFX.append(lambda L, t: badge_conso(L, t, wt("c8", "consomme"), cend("c8") - 0.02, "+ D'ESSENCE"))
GFX.append(lambda L, t: chapter_tag(L, t, "04", "LE RÉGIME MOTEUR", cstart("c9") + 0.1, cend("c9") - 0.05))
GFX.append(lambda L, t: rev_gauge(L, t, [(wt("c9", "sur-régime"), 0.94), (wt("c9", "sous-régime"), 0.06),
                                         (wt("c9", "sur-régime", 1), 0.97), (wt("c9", "sous-régime", 1), 0.03)],
                                  cstart("c9") + 0.15, cend("c9") - 0.02))
GFX.append(lambda L, t: badge_conso(L, t, wt("c10", "trop"), cend("c10") - 0.02, "CONSO"))
GFX.append(lambda L, t: chapter_tag(L, t, "05", "À L'OREILLE", cstart("c11") + 0.1, cend("c11") - 0.05))
GFX.append(lambda L, t: sound_bars(L, t, wt("c11", "l'oreille"), cend("c11") - 0.02))


# ------------------------------------------------------------------ caméra virtuelle
def zoom_at(c, tl):
    """Zoom du clip c à l'instant local tl (s)."""
    z = c["zoom"] * (1 + c["push"] * tl)
    for pt, amt in c["punch"]:
        z *= 1 + amt * ease_in_out((tl - (pt - c["src"][0]) + 0.05) / 0.24)
    return z


TRANS_IN = {"c1": ("smash", 5), "c2": ("whip", 4), "c7": ("whip", 4), "q2": ("whip", 4),
            "c9": ("whip", 4), "c11": ("whip", 4)}
IMPACT_SHAKE = []  # rempli plus bas (temps de sortie)


def render_frame(img, c, fi):
    tl = fi / FPS
    t = c["t0"] + tl
    z = zoom_at(c, tl)
    samples = [z]
    kind = TRANS_IN.get(c["id"])
    if kind and fi < kind[1]:
        u = fi / kind[1]
        amp = 0.32 if kind[0] == "smash" else 0.10
        z0 = z * (1 + amp * (1 - ease_out_cubic(u)))
        z1 = z * (1 + amp * (1 - ease_out_cubic(u + 1 / kind[1])))
        samples = list(np.linspace(z0, z1, 4))  # flou de mouvement par sur-échantillonnage
    # sortie du hook : zoom accéléré avant le smash cut
    if c["id"] == "hook" and fi >= c["n"] - 4:
        u = (fi - (c["n"] - 4)) / 4
        samples = list(np.linspace(z * (1 + 0.25 * u ** 2), z * (1 + 0.25 * (u + 0.25) ** 2), 4))
    sx = sy = 0.0
    for ts, amp in IMPACT_SHAKE:
        if 0 <= t - ts < 0.22:
            k = 1 - (t - ts) / 0.22
            sx += amp * k * math.sin((t - ts) * 95); sy += amp * k * math.cos((t - ts) * 77)
    acc = None
    for zz in samples:
        cw, ch = W / zz, H / zz
        x0 = clamp(c["cx"] - cw / 2 + sx, 0, W - cw); y0 = clamp(c["cy"] - ch * 0.47 + sy, 0, H - ch)
        fr = img.transform((W, H), Image.AFFINE, (1 / zz, 0, x0, 0, 1 / zz, y0), resample=Image.BICUBIC)
        a = np.asarray(fr, np.float32)
        acc = a if acc is None else acc + a
    out = Image.fromarray((acc / len(samples)).clip(0, 255).astype(np.uint8))
    # overlay graphique
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for g in GFX:
        g(layer, t)
    draw_captions(layer, t)
    # flash blanc au smash cut
    if c["id"] == "c1" and fi < 4:
        fl = Image.new("RGBA", (W, H), (255, 255, 255, int(150 * (1 - fi / 4))))
        layer = Image.alpha_composite(fl, layer)
    out = out.convert("RGBA")
    out.alpha_composite(layer)
    out = out.convert("RGB")
    # fondu au noir final
    if t > TOTAL - 0.35:
        k = clamp((TOTAL - t) / 0.35)
        out = Image.fromarray((np.asarray(out, np.float32) * k).astype(np.uint8))
    return out


# ------------------------------------------------------------------ audio
def read_wav(path):
    with wave.open(path) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        return x.reshape(-1, w.getnchannels())


def build_audio():
    voice_full = f"{WORK}/voice_full.wav"
    # Voix : passe-haut, réduction de bruit (moteur/route), présence, compression douce
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", SRC, "-vn", "-ac", "2", "-ar", str(SR), "-af",
                    "highpass=f=85,afftdn=nr=12:nf=-38:tn=1,equalizer=f=250:t=q:w=1:g=-2,"
                    "equalizer=f=3200:t=q:w=1.2:g=2.5,equalizer=f=9000:t=h:w=1:g=1,"
                    "acompressor=threshold=-22dB:ratio=3:attack=8:release=120:makeup=3",
                    voice_full], check=True)
    vf = read_wav(voice_full)
    n_total = int(round(TOTAL * SR))
    voice = np.zeros((n_total, 2), np.float32)
    for c in timeline:
        a = int(round(c["src"][0] * SR)); n = int(round(c["n"] / FPS * SR))
        seg = vf[a:a + n].copy()
        f = int(0.012 * SR)
        seg[:f] *= np.linspace(0, 1, f)[:, None]; seg[-f:] *= np.linspace(1, 0, f)[:, None]
        b = int(round(c["t0"] * SR))
        voice[b:b + len(seg)] += seg
    # dernier clip : fondu de sortie plus long
    fo = int(0.3 * SR); voice[-fo:] *= np.linspace(1, 0, fo)[:, None]

    # Musique originale, calée pour qu'une mesure tombe pile sur le smash cut (T1)
    bpm = 100; bar = 4 * 60 / bpm
    off = (-T1) % bar
    sections = [(0, 0), (T1 + off, 1), (cstart("q2") + off, 2), (cstart("c12") + off, 3)]
    sec = ",".join(f"{a:.3f}:{b}" for a, b in sections)
    sfxdir = f"{WORK}/sfx"
    subprocess.run([sys.executable, "-I", f"{HERE}/synth_audio.py", sfxdir, f"{TOTAL + off + 1:.3f}", str(bpm), sec],
                   check=True)
    mus = read_wav(f"{sfxdir}/music.wav")[int(off * SR):][:n_total]
    mus = np.pad(mus, ((0, n_total - len(mus)), (0, 0)))
    fo = int(0.6 * SR); mus[-fo:] *= np.linspace(1, 0, fo)[:, None]

    # Ducking : enveloppe de la voix -> atténuation de la musique (sidechain maison)
    hop = 480
    v_rms = np.sqrt((voice[:, 0] ** 2)[: n_total // hop * hop].reshape(-1, hop).mean(1))
    v_db = 20 * np.log10(v_rms + 1e-6)
    active = (v_db > -38).astype(np.float32)
    g = np.zeros_like(active); state = 0
    for i, v in enumerate(active):  # attaque 30 ms / relâchement 400 ms
        coef = 0.28 if v > state else 0.025
        state += (v - state) * coef; g[i] = state
    duck_db = -9 * g
    duck = np.repeat(10 ** (duck_db / 20), hop)
    duck = np.pad(duck, (0, n_total - len(duck)), constant_values=duck[-1])
    v_level = np.sqrt((voice[active.repeat(hop)[:len(voice)] > 0] ** 2).mean()) if active.any() else 0.1
    m_level = np.sqrt((mus ** 2).mean()) + 1e-9
    mus *= (v_level / m_level) * 10 ** (-15 / 20)  # musique ~15 dB sous la voix avant ducking
    mus *= duck[:, None]

    # SFX
    sfx = {k: read_wav(f"{sfxdir}/{k}.wav") for k in ("whoosh", "impact", "riser", "pop", "tick")}
    bus = np.zeros_like(voice)

    def put(name, t, gain_db, align="start"):
        x = sfx[name] * 10 ** (gain_db / 20) * v_level / 0.25
        if align == "end":
            t -= len(x) / SR
        i = int(t * SR)
        if i < 0:
            x = x[-i:]; i = 0
        j = min(n_total, i + len(x))
        bus[i:j] += x[: j - i]

    put("riser", T1 + 0.02, -13, align="end")
    put("impact", T1, -9)
    put("whoosh", T1 - 0.12, -15)
    put("pop", T1 + 0.08, -16); put("pop", T1 + 0.2, -19)
    for cid in ("c2", "c7", "q2", "c9", "c11"):
        put("whoosh", cstart(cid) - 0.2, -17)
    put("pop", wt("c2", "toi"), -16); put("pop", wt("c2", "boîte"), -16)
    put("whoosh", wt("c7", "vitesse") - 0.05, -22)
    put("tick", wt("c7", "5"), -12); put("pop", wt("c7", "5"), -15)
    put("pop", wt("c8", "consomme"), -15); put("impact", wt("c8", "plus"), -19)
    for k, nth in (("sur-régime", 0), ("sous-régime", 0), ("sur-régime", 1), ("sous-régime", 1)):
        put("whoosh", wt("c9", k, nth) - 0.05, -21); put("tick", wt("c9", k, nth) + 0.3, -16)
    put("impact", wt("c9", "trop"), -15)
    put("pop", wt("c10", "trop"), -15); put("impact", wt("c10", "trop"), -17)
    put("pop", wt("c11", "l'oreille"), -17)
    put("whoosh", TOTAL - 0.55, -16)
    IMPACT_SHAKE.extend([(T1, 9), (wt("c9", "trop"), 5), (wt("c10", "trop"), 4)])

    mix = voice + mus + bus
    mix = np.tanh(mix * 1.0)  # sécurité
    mix_path = f"{WORK}/mix_premaster.wav"
    with wave.open(mix_path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(mix, -1, 1) * 32767).astype(np.int16).tobytes())
    master = f"{WORK}/mix_master.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mix_path, "-af",
                    "loudnorm=I=-14:TP=-1.5:LRA=9", "-ar", str(SR), master], check=True)
    return master


# ------------------------------------------------------------------ rendu
def frames_of(c):
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{c['src'][0]:.3f}", "-i", SRC, "-frames:v", str(c["n"]),
           "-vf", GRADE, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    fs = W * H * 3
    for fi in range(c["n"]):
        buf = p.stdout.read(fs)
        if len(buf) < fs:
            break
        yield fi, Image.frombuffer("RGB", (W, H), buf)
    p.stdout.close(); p.wait()


def main():
    master = build_audio()
    json.dump([dict(id=c["id"], src=c["src"], out=(c["t0"], c["t0"] + c["n"] / FPS),
                    words=[dict(text=w["text"], src_s=round(w["s"], 3), out_s=round(o(c["id"], w["s"]), 3))
                           for w in c["words_t"]]) for c in timeline],
              open(f"{WORK}/timeline.json", "w"), ensure_ascii=False, indent=1)
    if PREVIEW:
        for tp in PREVIEW:
            for c in timeline:
                if c["t0"] <= tp < c["t0"] + c["n"] / FPS:
                    fi_t = int((tp - c["t0"]) * FPS)
                    for fi, img in frames_of(dict(c, n=fi_t + 1)):
                        if fi == fi_t:
                            render_frame(img, c, fi).save(f"{WORK}/preview_{tp:05.2f}.jpg", quality=88)
        return
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-i", master, "-map", "0:v", "-map", "1:a",
         "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-profile:v", "high", "-pix_fmt", "yuv420p",
         "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
         "-c:a", "aac", "-b:a", "320k", "-ar", str(SR), "-shortest", "-movflags", "+faststart", OUT],
        stdin=subprocess.PIPE)
    done = 0
    for c in timeline:
        for fi, img in frames_of(c):
            enc.stdin.write(render_frame(img, c, fi).tobytes())
            done += 1
        print(f"{c['id']}: {done}/{TOTAL_FRAMES} images", flush=True)
    enc.stdin.close(); enc.wait()
    print("OK", OUT, f"{TOTAL:.2f}s")


if __name__ == "__main__":
    main()
