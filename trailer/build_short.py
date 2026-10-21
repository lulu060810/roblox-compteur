#!/usr/bin/env python3
"""Short MINE TO GET RICH (YouTube Shorts / TikTok / Reels) : 9:16, 1080x1920, 60 i/s, ~25 s.

Même style que le trailer v4 : rushes du jeu, refrain de « Nightcall », zooms d'impact,
éclats lumineux, textes 3D blanc/cyan, logo détouré avec BOOM. Ça commence par un
moment fort (gros plan des minerais + accroche) et finit sur l'appel à l'action :
« 🚨 NOUVELLE VIDÉO DISPONIBLE ! 🚨 » / « ▶️ VA VOIR LA VIDÉO COMPLÈTE SUR MA CHAÎNE ! ».

  python3 build_short.py            -> build/MINE_TO_GET_RICH_short_1080x1920.mp4
  python3 build_short.py --preview  -> 360x640 30 i/s
"""
import argparse
import math
import os
import subprocess
import types

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

import build_trailer_v3 as v3
import render_finale_v3 as rf

A, B, AERIAL, ARENA = v3.A, v3.B, v3.AERIAL, v3.ARENA
FONT = rf.FONT
EMOJI_FONT = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"

FIN = 40                       # durée totale = 40 temps (~24,7 s)
FINALE_START, BOOM = 23, 24    # suspension d'un temps puis BOOM
CTA1, CTA2 = 27, 29            # « NOUVELLE VIDÉO DISPONIBLE » puis « VA VOIR LA VIDÉO COMPLÈTE »

# (nom, début, fin en temps, type, paramètres). x = position horizontale du cadrage vertical (0-1).
SHOTS = [
    # ACCROCHE — moment fort dès la 1re image
    ("h1", 0, 2, "clip", dict(src=A, a=0.0, b=1.3, x=0.55, punch=True, zoom=True)),
    ("h2", 2, 4, "clip", dict(src=A, a=5.0, b=7.4, x=0.5, punch=True)),
    # DÉCOUVERTE
    ("m1", 4, 6, "clip", dict(src=B, a=0.0, b=2.2, x=0.6, flash=True)),
    ("m2", 6, 8, "card", dict(img=AERIAL, flash=True)),
    ("m3", 8, 10, "clip", dict(src=B, a=7.6, b=10.0, x=0.45, flash=True)),
    ("m4", 10, 12, "clip", dict(src=A, a=0.2, b=1.6, x=0.35, punch=True, zoom=True)),
    ("m5", 12, 14, "card", dict(img=ARENA, flash=True)),
    ("m6", 14, 16, "clip", dict(src=B, a=8.4, b=10.6, x=0.5, punch=True, blur=True)),
    # ACCÉLÉRATION — un plan par temps
    ("f1", 16, 17, "clip", dict(src=A, a=5.0, b=6.2, x=0.5, punch=True)),
    ("f2", 17, 18, "card", dict(img=AERIAL, punch=True)),
    ("f3", 18, 19, "clip", dict(src=B, a=0.5, b=2.5, x=0.5, punch=True, blur=True)),
    ("f4", 19, 20, "clip", dict(src=B, a=10.0, b=11.0, x=0.4, punch=True)),
    ("f5", 20, 23, "clip", dict(src=A, a=3.4, b=7.4, x=0.5, blur=True, darken=True)),
]

# Sous-titres dynamiques (lignes, début, fin en temps).
CAPTIONS = [
    (["TU CREUSES..."], 0, 2),
    (["...ET TU DEVIENS", "RICHE 💰"], 2, 4),
    (["EXPLORE LA MINE ⛏️"], 4, 7),
    (["TROUVE DES", "MINERAIS RARES 💎"], 10, 13),
    (["ES-TU PRÊT ? 🔥"], 19, 23),
]


# ----------------------------------------------------------------------------- textes
def text_3d(txt, size, face=(255, 255, 255), stroke_col=(0, 190, 255), deep=(0, 70, 150)):
    font = ImageFont.truetype(FONT, size)
    stroke = max(2, int(size * 0.12))
    depth = max(2, int(size * 0.11))
    pad = stroke + depth + 4
    l, t, r, b = font.getbbox(txt, stroke_width=stroke)
    img = Image.new("RGBA", (r - l + 2 * pad, b - t + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ox, oy = pad - l, pad - t
    for k in range(depth, 0, -1):
        d.text((ox, oy + k), txt, font=font, fill=deep + (255,), stroke_width=stroke, stroke_fill=deep + (255,))
    d.text((ox, oy), txt, font=font, fill=face + (255,), stroke_width=stroke, stroke_fill=stroke_col + (255,))
    return img


def emoji(ch, height):
    f = ImageFont.truetype(EMOJI_FONT, 109)
    im = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((10, 10), ch, font=f, embedded_color=True)
    im = im.crop(im.getbbox())
    return im.resize((int(im.width * height / im.height), height), Image.LANCZOS)


def is_emoji(ch):
    return ord(ch) > 0x2000 and ch not in "ÀÂÉÈÊËÎÏÔÙÛÜÇàâéèêëîïôùûüç…"


def line_image(line, size, **style):
    """Une ligne de texte 3D avec emojis en couleur intercalés."""
    parts, buf = [], ""
    i = 0
    while i < len(line):
        ch = line[i]
        if is_emoji(ch):
            if buf.strip():
                parts.append(("t", buf.strip()))
            buf = ""
            seq = ch
            while i + 1 < len(line) and (line[i + 1] in "️‍" or (seq.endswith("‍") and is_emoji(line[i + 1]))):
                i += 1
                seq += line[i]
            parts.append(("e", seq))
        else:
            buf += ch
        i += 1
    if buf.strip():
        parts.append(("t", buf.strip()))
    ims = [text_3d(p, size, **style) if k == "t" else emoji(p, int(size * 1.15)) for k, p in parts]
    gap = int(size * 0.25)
    w = sum(im.width for im in ims) + gap * (len(ims) - 1)
    h = max(im.height for im in ims)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    x = 0
    for im in ims:
        out.alpha_composite(im, (x, (h - im.height) // 2))
        x += im.width + gap
    return out


def block(lines, size, glow_col=rf.CYAN, **style):
    """Plusieurs lignes centrées + ombre portée + halo."""
    ims = [line_image(l, size, **style) for l in lines]
    w = max(im.width for im in ims)
    h = sum(im.height for im in ims) - int(size * 0.15) * (len(ims) - 1)
    pad = int(size * 0.6)
    out = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    y = pad
    for im in ims:
        out.alpha_composite(im, ((out.width - im.width) // 2, y))
        y += im.height - int(size * 0.15)
    a = out.getchannel("A")
    shadow = Image.new("RGBA", out.size, (0, 8, 25, 0))
    shadow.putalpha(a.filter(ImageFilter.GaussianBlur(size * 0.18)).point(lambda v: int(v * 0.8)))
    g = a.filter(ImageFilter.GaussianBlur(size * 0.3))
    halo = Image.new("RGBA", out.size, glow_col + (0,))
    halo.putalpha(g.point(lambda v: int(v * 0.55)))
    return Image.alpha_composite(Image.alpha_composite(shadow, halo), out)


def fit_width(im, maxw):
    if im.width <= maxw:
        return im
    return im.resize((maxw, int(im.height * maxw / im.width)), Image.LANCZOS)


def ease_out_back(p, s=2.0):
    p -= 1
    return p * p * ((s + 1) * p + s) + 1


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def pop(frame, base, t, t0, t1, cx, cy, exit_anim=True):
    """Apparition avec rebond, légère poussée, sortie en zoom + fondu."""
    if not t0 <= t < t1:
        return frame
    p_in = clamp((t - t0) / 0.28)
    p_out = clamp((t - (t1 - 0.16)) / 0.16) if exit_anim else 0.0
    sc = max(0.05, ease_out_back(p_in)) * (1 + 0.05 * (t - t0) / (t1 - t0)) * (1 + 0.35 * p_out)
    alpha = clamp((t - t0) / 0.06) * (1 - p_out)
    w, h = max(2, int(base.width * sc)), max(2, int(base.height * sc))
    im = base.resize((w, h), Image.BILINEAR)
    if alpha < 1:
        im.putalpha(im.getchannel("A").point(lambda v, k=alpha: int(v * k)))
    frame.alpha_composite(im, (int(cx - w / 2), int(cy - h / 2)))
    return frame


# ------------------------------------------------------------------- séquence finale
class ShortFinale(rf.Finale):
    """Séquence logo du trailer, recomposée à la verticale, avec l'appel à l'action."""

    def __init__(self, a, W, H, fps):
        super().__init__(a, W, H, fps)
        lw, lh = self.logo.size
        self.fit_big = min(0.94 * W / lw, 0.52 * H / lh)
        self.fit_small = min(0.80 * W / lw, 0.44 * H / lh)
        self.y_big, self.y_small = 0.45, 0.32
        gw = round(lw * self.fit_big)
        gh = round(lh * self.fit_big)
        base = self.logo.resize((gw, gh), Image.LANCZOS)
        self.gpad = int(W * 0.08)
        al = Image.new("L", (gw + 2 * self.gpad, gh + 2 * self.gpad))
        al.paste(base.getchannel("A"), (self.gpad, self.gpad))
        g = al.filter(ImageFilter.GaussianBlur(W * 0.03))
        self.glow_base = Image.merge("RGB", [g.point(lambda v, c=c: v * c // 255) for c in rf.CYAN])
        self._cache = {}
        self.text = Image.new("RGBA", (2, 2), (0, 0, 0, 0))   # le texte est dessiné par cta()
        self.text_halo = Image.new("RGB", (2, 2))
        self.text_y = 0.66
        r = self.rng
        self.text_sparkles = [dict(x=r.uniform(0.08, 0.92), y=r.uniform(0.58, 0.86), ph=r.uniform(0, 6.28),
                                   f=r.uniform(1.5, 3.5), s=r.uniform(0.6, 1.3)) for _ in range(30)]
        self.crystals = [dict(x=x, y=y, s=s, rot=rot, ph=r.uniform(0, 6.28), d=r.uniform(0, 0.25))
                         for x, y, s, rot in [(0.13, 0.05, 0.8, -18), (0.87, 0.06, 0.75, 20),
                                              (0.05, 0.30, 0.6, -8), (0.95, 0.27, 0.65, 12),
                                              (0.14, 0.93, 0.8, -25), (0.86, 0.94, 0.75, 28),
                                              (0.50, 0.96, 0.6, 5)]]
        self.coins = [dict(x=x, y=y, s=s, ph=r.uniform(0, 6.28), d=r.uniform(0.05, 0.35))
                      for x, y, s in [(0.33, 0.04, 0.7), (0.67, 0.05, 0.75), (0.05, 0.52, 0.6),
                                      (0.95, 0.49, 0.65), (0.33, 0.95, 0.7), (0.67, 0.94, 0.7)]]
        # Appel à l'action.
        size1 = int(W * 0.085)
        self.cta1 = fit_width(block(["🚨 NOUVELLE VIDÉO 🚨", "DISPONIBLE !"], size1,
                                    glow_col=(255, 80, 60), face=(255, 222, 40),
                                    stroke_col=(220, 30, 40), deep=(110, 10, 20)), int(W * 0.98))
        size2 = int(W * 0.062)
        self.cta2 = fit_width(block(["▶️ VA VOIR LA VIDÉO", "COMPLÈTE SUR MA CHAÎNE !"], size2), int(W * 0.98))
        self.cta1_t, self.cta2_t = a.cta1, a.cta2

    def frame(self, T):
        fr = super().frame(T).convert("RGBA")
        W, H = self.W, self.H
        for im, t0, y in ((self.cta1, self.cta1_t, 0.635), (self.cta2, self.cta2_t, 0.79)):
            if T >= t0:
                # pulsation légère pour attirer l'œil
                k = 1 + 0.035 * math.sin((T - t0) * 2 * math.pi / (2 * v3.TEMPS)) * clamp((T - t0 - 0.4) / 0.3)
                base = im if abs(k - 1) < 1e-3 else im.resize((int(im.width * k), int(im.height * k)), Image.BILINEAR)
                fr = pop(fr, base, T, t0, 1e9, W / 2, y * H, exit_anim=False)
        return fr.convert("RGB")


def render_finale(path, W, H, fps, preset, crf):
    t0 = v3.beat(FINALE_START)
    n = int(round(v3.beat(FIN) * fps)) - int(round(t0 * fps))
    a = types.SimpleNamespace(logo=v3.LOGO, background=v3.FOND, impact=v3.beat(BOOM) - t0,
                              text=v3.beat(CTA1) - t0, fade=1e9, duration=n / fps,
                              cta1=v3.beat(CTA1) - t0, cta2=v3.beat(CTA2) - t0)
    fin = ShortFinale(a, W, H, fps)
    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", preset, "-crf", crf, "-pix_fmt", "yuv420p", path],
        stdin=subprocess.PIPE, cwd=v3.HERE)
    for i in range(n):
        enc.stdin.write(fin.frame(i / fps).tobytes())
    enc.stdin.close()
    if enc.wait():
        raise SystemExit("échec de la séquence finale")


# --------------------------------------------------------------------------- plans
class Short:
    def __init__(self, preview):
        self.W, self.H, self.FPS = (360, 640, 30) if preview else (1080, 1920, 60)
        self.preset, self.crf = ("veryfast", "22") if preview else ("slow", "16")
        self.tmp = os.path.join("build", "tmp_short")
        self.out = os.path.join("build", "MINE_TO_GET_RICH_short_%s.mp4" % ("preview" if preview else "1080x1920"))
        os.makedirs(os.path.join(v3.HERE, self.tmp), exist_ok=True)

    def frames(self, t):
        return int(round(t * self.FPS))

    def enc(self, path, n):
        return ["-frames:v", str(n), "-an", "-c:v", "libx264", "-preset", self.preset, "-crf", self.crf,
                "-pix_fmt", "yuv420p", "-r", str(self.FPS), path]

    def look(self, o):
        W, H = self.W, self.H
        f = []
        if o.get("punch"):
            f.append(f"scale=w='{W}*(1+0.12*max(0\\,1-t/0.2))':h=-2:eval=frame,crop={W}:{H}")
        f += ["eq=contrast=1.07:saturation=1.25:gamma=0.98", "unsharp=5:5:0.7", "vignette=PI/5"]
        if o.get("flash") or o.get("punch"):
            f.append("fade=t=in:st=0:d=0.12:color=0xD6FAFF")
        return f

    def clip(self, name, dur, n, o):
        W, H = self.W, self.H
        speed = (o["b"] - o["a"]) / dur
        f = ["crop=iw*0.92:ih*0.92:0:ih*0.08",
             f"crop=ih*9/16:ih:(iw-ih*9/16)*{o.get('x', 0.5)}:0",
             f"scale={W}:{H}:flags=lanczos", "setsar=1",
             f"setpts=(PTS-STARTPTS)/{speed}", f"fps={self.FPS}", "tpad=stop_mode=clone:stop_duration=1"]
        if o.get("blur"):
            f.append("tmix=frames=3:weights='1 2 1'")
        if o.get("zoom"):
            f.append(f"scale=w='{W}*(1+0.12*t/{dur})':h=-2:eval=frame,crop={W}:{H}")
        f += self.look(o)
        if o.get("darken"):
            f.append(f"fade=t=out:st={dur - 0.35}:d=0.35")
        v3.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(o["a"]), "-to", str(o["b"]), "-i", o["src"],
                "-vf", ",".join(f)] + self.enc(f"{self.tmp}/{name}.mp4", n))

    def card(self, name, dur, n, o):
        """Capture d'écran (trop petite pour être recadrée en vertical) : image entière qui
        avance au centre, sur un fond flouté de la même image."""
        W, H = self.W, self.H
        fc = (f"[0:v]split[s1][s2];[s1]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},gblur=sigma={W // 30},"
              f"eq=brightness=-0.12:saturation=1.3[bg];"
              f"[s2]scale=w='{W}*1.18*(1+0.14*t/{dur})':h=-2:eval=frame:flags=lanczos[fg];"
              f"[bg][fg]overlay=x='(W-w)/2':y='(H-h)/2':eval=frame,setsar=1,"
              + ",".join(self.look(o)))
        v3.run(["ffmpeg", "-loglevel", "error", "-y", "-loop", "1", "-framerate", str(self.FPS), "-i", o["img"],
                "-filter_complex", fc] + self.enc(f"{self.tmp}/{name}.mp4", n))

    def captions(self, path, n):
        W, H = self.W, self.H
        items = [(fit_width(block(lines, int(W * 0.095)), int(W * 0.96)), v3.beat(b0), v3.beat(b1))
                 for lines, b0, b1 in CAPTIONS]
        enc = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
             "-r", str(self.FPS), "-i", "-", "-c:v", "png", path], stdin=subprocess.PIPE, cwd=v3.HERE)
        empty = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for i in range(n):
            t = i / self.FPS
            fr = empty.copy()
            for im, t0, t1 in items:
                fr = pop(fr, im, t, t0, t1, W / 2, H * 0.70)
            enc.stdin.write(fr.tobytes())
        enc.stdin.close()
        if enc.wait():
            raise SystemExit("échec des sous-titres")

    def build(self):
        print("1/4 Plans")
        for name, b0, b1, kind, o in SHOTS:
            t0, t1 = v3.beat(b0), v3.beat(b1)
            print(f"  {name}  {t0:5.2f} -> {t1:5.2f} s", flush=True)
            getattr(self, kind)(name, t1 - t0, self.frames(t1) - self.frames(t0), o)
        n_mont = self.frames(v3.beat(FINALE_START))
        print("2/4 Sous-titres + logo + appel à l'action")
        self.captions(f"{self.tmp}/captions.mov", n_mont)
        with open(os.path.join(v3.HERE, self.tmp, "montage.txt"), "w") as fh:
            fh.writelines(f"file '{s[0]}.mp4'\n" for s in SHOTS)
        v3.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{self.tmp}/montage.txt",
                "-i", f"{self.tmp}/captions.mov", "-filter_complex", "[0:v][1:v]overlay=0:0,format=yuv420p"]
               + self.enc(f"{self.tmp}/montage_cap.mp4", n_mont))
        render_finale(f"{self.tmp}/final.mp4", self.W, self.H, self.FPS, self.preset, self.crf)
        with open(os.path.join(v3.HERE, self.tmp, "list.txt"), "w") as fh:
            fh.write("file 'montage_cap.mp4'\nfile 'final.mp4'\n")
        print("3/4 Audio")
        b = v3.Builder.__new__(v3.Builder)
        b.tmp, b.out = self.tmp, self.out
        b.audio()
        print("4/4 Assemblage")
        b.mux()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true")
    a = ap.parse_args()
    v3.choisir("nightcall")
    v3.PREMIER_TEMPS, v3.DEBUT = 0.0, 59.42      # refrain, 1er temps sur la 1re image
    v3.DUREE = round(v3.beat(FIN), 3)
    v3.FINALE_START, v3.BOOM, v3.TEXTE = FINALE_START, BOOM, CTA1
    v3.FONDU = FIN - 0.6                          # court fondu sonore final (boucle propre)
    v3.WHOOSH = [4, 6, 8, 10, 12, 14, 16, 17, 18, 19, 20]
    Short(a.preview).build()


if __name__ == "__main__":
    main()
