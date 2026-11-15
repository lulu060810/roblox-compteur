"""Calques de texte (RGBA) pour chaque image — typographie sobre façon bande-annonce.
usage: python3 text.py outdir
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS, DUR = 1080, 1920, 30, 18.0
FD = '/usr/share/fonts/opentype/inter/'
out = sys.argv[1]
os.makedirs(out, exist_ok=True)
MAXW = 820  # zone sûre TikTok : x ≈ 130..950


def font(name, size):
    return ImageFont.truetype(FD + name, size)


def spaced_width(text, f, track):
    return sum(f.getlength(c) for c in text) + track * (len(text) - 1)


def draw_spaced(d, text, f, track, cx, cy, fill):
    w = spaced_width(text, f, track)
    x = cx - w / 2
    asc, desc = f.getmetrics()
    for c in text:
        d.text((x, cy - (asc - desc * 0.3) / 2), c, font=f, fill=fill)
        x += f.getlength(c) + track


def fit(text, fname, size, track_em):
    while True:
        f = font(fname, size)
        if spaced_width(text, f, size * track_em) <= MAXW or size < 20:
            return f, size * track_em
        size -= 2


def smooth(x):
    x = min(1, max(0, x))
    return x * x * (3 - 2 * x)


# (lignes, début, fin, centre y, coupure nette à la fin ?)
CAPTIONS = [
    (["VOUS PENSIEZ QU’ON", "AVAIT ABANDONNÉ ?"], 1.45, 3.95, 1180, False),
    (["ON N’A PAS DIT", "NOTRE DERNIER MOT."], 5.0, 9.0, 1200, False),
    (["QUELQUE CHOSE", "SE PRÉPARE…"], 11.0, 14.0, 1330, True),
]


def caption_layer(lines, t, t0, t1, cy, hardcut):
    a_in = smooth((t - t0) / 0.6)
    a_out = 1.0 if hardcut else 1 - smooth((t - (t1 - 0.4)) / 0.4)
    a = a_in * a_out
    if a <= 0.001:
        return None
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    glow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    dg = ImageDraw.Draw(glow)
    prog = (t - t0) / (t1 - t0)
    track_em = 0.13 + 0.05 * prog          # léger élargissement continu
    lh = 82
    y0 = cy - (len(lines) - 1) * lh / 2 + (1 - a_in) * 14
    for i, ln in enumerate(lines):
        f, tr = fit(ln, 'InterDisplay-SemiBold.otf', 62, track_em)
        draw_spaced(d, ln, f, tr, W / 2, y0 + i * lh, (244, 242, 240, 255))
        draw_spaced(dg, ln, f, tr, W / 2, y0 + i * lh, (0, 0, 0, 255))
    blur = (1 - a_in) * 7
    if blur > 0.3:
        layer = layer.filter(ImageFilter.GaussianBlur(blur))
    shadow = glow.filter(ImageFilter.GaussianBlur(14))
    base = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    sh = np.array(shadow); sh[..., 3] = (sh[..., 3] * 0.75).astype(np.uint8)
    base = Image.alpha_composite(base, Image.fromarray(sh))
    base = Image.alpha_composite(base, layer)
    arr = np.array(base).astype(np.float32)
    arr[..., 3] *= a
    return Image.fromarray(arr.astype(np.uint8))


def end_layer(t):
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    fade_out = 1 - smooth((t - 16.9) / 0.9)
    # UNITED GAMES
    a1 = smooth((t - 14.25) / 0.7) * fade_out
    if a1 > 0:
        track = 0.42 - 0.12 * smooth((t - 14.25) / 2.5)
        f, tr = fit("UNITED GAMES", 'InterDisplay-Bold.otf', 84, track)
        tmp = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        draw_spaced(ImageDraw.Draw(tmp), "UNITED GAMES", f, tr, W / 2, 900, (255, 255, 255, 255))
        b = (1 - smooth((t - 14.25) / 0.5)) * 10
        if b > 0.3:
            tmp = tmp.filter(ImageFilter.GaussianBlur(b))
        arr = np.array(tmp).astype(np.float32); arr[..., 3] *= a1
        layer = Image.alpha_composite(layer, Image.fromarray(arr.astype(np.uint8)))
    # filet
    lw = smooth((t - 14.7) / 0.8) * 240
    if lw > 1:
        d = ImageDraw.Draw(layer)
        d.rectangle([W / 2 - lw / 2, 968, W / 2 + lw / 2, 969], fill=(255, 255, 255, int(120 * fade_out)))
    # slogan
    a2 = smooth((t - 15.05) / 0.8) * fade_out
    if a2 > 0:
        f, tr = fit("LE CALME AVANT LA TEMPÊTE.", 'InterDisplay-Light.otf', 36, 0.2)
        tmp = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        draw_spaced(ImageDraw.Draw(tmp), "LE CALME AVANT LA TEMPÊTE.", f, tr, W / 2, 1036 - (1 - a2) * 8, (225, 225, 228, 255))
        arr = np.array(tmp).astype(np.float32); arr[..., 3] *= a2
        layer = Image.alpha_composite(layer, Image.fromarray(arr.astype(np.uint8)))
    return layer


empty = Image.new('RGBA', (W, H), (0, 0, 0, 0))
for fi in range(int(DUR * FPS)):
    t = fi / FPS
    img = empty
    for lines, t0, t1, cy, hc in CAPTIONS:
        if t0 <= t < t1:
            l = caption_layer(lines, t, t0, t1, cy, hc)
            if l is not None:
                img = Image.alpha_composite(img, l)
    if t >= 14.0:
        img = Image.alpha_composite(img, end_layer(t))
    img.save(os.path.join(out, f'o_{fi:04d}.png'), compress_level=1)
print('done')
