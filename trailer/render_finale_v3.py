#!/usr/bin/env python3
"""Séquence finale du trailer v3 : suspension, BOOM, logo détouré, « DISPONIBLE PROCHAINEMENT ».

Temps locaux (secondes depuis le début de la séquence), passés par build_trailer_v3.sh
pour tomber exactement sur les temps de la musique :
  0 -> --impact   fond flouté qui s'assombrit, particules bleues qui convergent
  --impact        BOOM : flash cyan, onde de choc, tremblement, logo en zoom 3D avec rebond
  --text          le logo remonte, le texte apparaît dessous avec un rebond
  --fade -> fin   fondu au noir

Le logo détouré (assets/logo_detoure.png) est seulement mis à l'échelle et déplacé :
pixels, couleurs, personnage, diamants, pioches et typographie restent ceux de l'original.
"""
import argparse
import math
import random
import subprocess
import sys

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

CYAN = (60, 220, 255)
CYAN_LIGHT = (180, 245, 255)
TEXT = "DISPONIBLE PROCHAINEMENT"
FONT = "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf"


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def lerp(a, b, p):
    return a + (b - a) * p


def ease_out_back(p, s=1.7):
    p -= 1
    return p * p * ((s + 1) * p + s) + 1


def ease_out_cubic(p):
    return 1 - (1 - p) ** 3


def ease_in_out(p):
    return p * p * (3 - 2 * p)


def solid(size, color, k):
    return Image.new("RGB", size, tuple(int(c * k) for c in color))


def render_text(H, text=TEXT, scale=0.082):
    """Texte 3D : extrusion bleu profond, contour cyan épais, face blanche, halo discret."""
    TEXT = text
    size = int(H * scale)
    font = ImageFont.truetype(FONT, size)
    stroke = max(2, int(size * 0.11))
    depth = max(2, int(size * 0.10))
    pad = stroke + depth + int(size * 0.5)
    l, t, r, b = font.getbbox(TEXT, stroke_width=stroke)
    w, h = r - l + 2 * pad, b - t + 2 * pad
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ox, oy = pad - l, pad - t
    for k in range(depth, 0, -1):  # extrusion vers le bas
        c = int(lerp(20, 60, 1 - k / depth))
        d.text((ox, oy + k), TEXT, font=font, fill=(0, c + 40, c + 110, 255),
               stroke_width=stroke, stroke_fill=(0, c + 40, c + 110, 255))
    d.text((ox, oy), TEXT, font=font, fill=(255, 255, 255, 255),
           stroke_width=stroke, stroke_fill=(0, 190, 255, 255))
    # léger dégradé sur la face pour le volume
    face = Image.new("L", (w, h), 0)
    ImageDraw.Draw(face).text((ox, oy), TEXT, font=font, fill=255)
    shade = Image.linear_gradient("L").resize((w, h)).point(lambda v: int(max(0, v - 150) * 0.5))
    tint = Image.new("RGBA", (w, h), (170, 225, 255, 255))
    tint.putalpha(ImageChops.multiply(face, shade))
    img = Image.alpha_composite(img, tint)
    glow = img.getchannel("A").filter(ImageFilter.GaussianBlur(size * 0.25))
    halo = Image.merge("RGB", [glow.point(lambda v, c=c: v * c // 255) for c in CYAN])
    return img, halo


class Finale:
    def __init__(self, a, W, H, fps, seed=11):
        self.W, self.H, self.fps = W, H, fps
        self.impact, self.text_t, self.fade_t, self.dur = a.impact, a.text, a.fade, a.duration
        r = self.rng = random.Random(seed)

        self.logo = Image.open(a.logo).convert("RGBA")
        # Taille du logo seul (avant le texte) puis avec le texte dessous.
        self.fit_big = 0.78 * H / self.logo.height
        self.fit_small = 0.66 * H / self.logo.height
        self.y_big, self.y_small = 0.50, 0.385
        lw, lh = (round(v * self.fit_big) for v in self.logo.size)
        base = self.logo.resize((lw, lh), Image.LANCZOS)
        self.gpad = int(H * 0.06)  # marge pour que le halo ne soit pas coupé net
        alpha = Image.new("L", (lw + 2 * self.gpad, lh + 2 * self.gpad))
        alpha.paste(base.getchannel("A"), (self.gpad, self.gpad))
        glow = alpha.filter(ImageFilter.GaussianBlur(H * 0.02))
        self.glow_base = Image.merge("RGB", [glow.point(lambda v, c=c: v * c // 255) for c in CYAN])
        self._cache = {}

        self.text, self.text_halo = render_text(H)
        self.text_y = 0.855

        self.over = 1.06
        bg = Image.open(a.background).convert("RGB")
        bw, bh = int(W * self.over), int(H * self.over)
        s = max(bw / bg.width, bh / bg.height)
        bg = bg.resize((math.ceil(bg.width * s), math.ceil(bg.height * s)), Image.LANCZOS)
        left, top = (bg.width - bw) // 2, (bg.height - bh) // 2
        self.bg = bg.crop((left, top, left + bw, top + bh)).filter(ImageFilter.GaussianBlur(H * 0.007))

        vw, vh = W // 8, H // 8
        vig = Image.new("L", (vw, vh))
        vig.putdata([int(255 * clamp(1.15 - 0.85 * (((x - vw / 2) / (vw / 2)) ** 2 + ((y - vh / 2) / (vh / 2)) ** 2) ** 0.5 * 0.75))
                     for y in range(vh) for x in range(vw)])
        self.vignette = Image.merge("RGB", [vig.resize((W, H), Image.BILINEAR)] * 3)

        self.particles = [dict(a=r.uniform(0, 2 * math.pi), r0=r.uniform(0.45, 1.0) * W,
                               d=r.uniform(0.0, 0.25) * self.impact, size=r.uniform(0.6, 1.8),
                               swirl=r.uniform(0.5, 1.2)) for _ in range(380)]
        self.sparks = [dict(a=r.uniform(0, 2 * math.pi), v=r.uniform(0.25, 0.9) * W,
                            size=r.uniform(0.6, 1.6)) for _ in range(160)]
        self.dust = [dict(x=r.random(), y=r.random(), v=r.uniform(0.01, 0.04),
                          ph=r.uniform(0, 6.28), size=r.uniform(0.5, 1.2)) for _ in range(90)]
        self.text_sparkles = [dict(x=r.uniform(0.17, 0.83), y=self.text_y + r.uniform(-0.07, 0.07),
                                   ph=r.uniform(0, 6.28), f=r.uniform(1.5, 3.5), s=r.uniform(0.6, 1.3))
                              for _ in range(26)]
        # Cristaux et pièces sur les côtés, hors du logo et du texte.
        self.crystals = [dict(x=x, y=y, s=s, rot=rot, ph=r.uniform(0, 6.28), d=r.uniform(0, 0.25))
                         for x, y, s, rot in [(0.10, 0.20, 1.3, -18), (0.90, 0.17, 1.1, 20),
                                              (0.06, 0.50, 0.95, -8), (0.94, 0.53, 1.3, 12),
                                              (0.22, 0.38, 0.75, 10), (0.78, 0.34, 0.8, -12),
                                              (0.19, 0.66, 0.85, -25), (0.81, 0.68, 0.9, 28)]]
        self.coins = [dict(x=x, y=y, s=s, ph=r.uniform(0, 6.28), d=r.uniform(0.05, 0.35))
                      for x, y, s in [(0.25, 0.55, 1.0), (0.75, 0.57, 1.1), (0.06, 0.82, 0.9),
                                      (0.94, 0.84, 0.85), (0.05, 0.10, 0.8), (0.95, 0.38, 0.8)]]

    # ---------------------------------------------------------------- logo
    def logo_at(self, fit):
        w, h = (max(2, round(v * fit)) for v in self.logo.size)
        if (w, h) not in self._cache:
            if len(self._cache) > 4:
                self._cache.clear()
            pad = round(self.gpad * w / self.glow_base.width * self.glow_base.width / (self.glow_base.width - 2 * self.gpad))
            self._cache[(w, h)] = (self.logo.resize((w, h), Image.LANCZOS),
                                   self.glow_base.resize((w + 2 * pad, h + 2 * pad), Image.BILINEAR), pad)
        return self._cache[(w, h)]

    def logo_layout(self, T):
        """(échelle, centre y) du logo, ou None avant l'impact."""
        p = (T - self.impact) / 0.5
        if p <= 0:
            return None
        k = lerp(0.1, 1.0, ease_out_back(p, 2.0)) if p < 1 else 1.0
        # léger rebond secondaire après la stabilisation
        k *= 1 + 0.025 * math.exp(-4 * max(0, T - self.impact - 0.5)) * math.sin(14 * max(0, T - self.impact - 0.5))
        q = ease_in_out(clamp((T - self.text_t + 0.05) / 0.35))
        fit = lerp(self.fit_big, self.fit_small, q) * k
        return fit, lerp(self.y_big, self.y_small, q)

    def shine(self, logo, T):
        for t0, dur in ((self.impact + 0.6, 0.65), (self.text_t + 0.7, 0.75)):
            p = (T - t0) / dur
            if 0 <= p <= 1:
                w, h = logo.size
                u = (np.arange(w)[None, :] + 0.45 * np.arange(h)[:, None]) / (w + 0.45 * h)
                band = np.exp(-((u - lerp(-0.2, 1.2, ease_out_cubic(p))) / 0.05) ** 2) * 0.55
                alpha = np.asarray(logo.getchannel("A"), dtype=np.float32) / 255
                mask = Image.fromarray((band * alpha * 255).astype(np.uint8), "L")
                out = logo.copy()
                out.paste((255, 255, 255, 255), (0, 0), mask)
                out.putalpha(logo.getchannel("A"))
                return out
        return logo

    # ------------------------------------------------------------ éléments
    def draw_crystal(self, d, glow, cx, cy, size, rot, twinkle, hs):
        w, h = size * 0.42, size
        pts = [(0, -h), (w, -h * 0.35), (w * 0.8, h * 0.6), (0, h), (-w * 0.8, h * 0.6), (-w, -h * 0.35)]
        c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        P = [(cx + x * c - y * s, cy + x * s + y * c) for x, y in pts]
        C = (cx, cy)
        d.polygon([P[0], P[1], P[2], P[3], C], fill=(25, 140, 225, 255))
        d.polygon([P[0], P[5], P[4], P[3], C], fill=(95, 225, 255, 255))
        d.polygon([P[0], P[1], C, P[5]], fill=(185, 248, 255, 255))
        d.line(P + [P[0]], fill=(220, 252, 255, 255), width=max(1, int(size * 0.04)))
        glow.polygon([(x * hs, y * hs) for x, y in P], fill=tuple(int(v * 0.55) for v in CYAN))
        if twinkle > 0:
            self.star(glow, P[0][0] * hs, P[0][1] * hs, size * hs * 0.9 * twinkle, twinkle)

    def star(self, g, x, y, L, k):
        col = tuple(int(255 * k) for _ in range(3))
        wdt = max(1, int(L * 0.06))
        g.line([(x - L, y), (x + L, y)], fill=col, width=wdt)
        g.line([(x, y - L), (x, y + L)], fill=col, width=wdt)

    def draw_coin(self, d, glow, cx, cy, R, phase, hs):
        sx = abs(math.cos(phase))
        rx = max(R * 0.07, R * sx)
        thick = R * 0.16 * math.sin(phase)
        d.ellipse([cx - rx + thick, cy - R, cx + rx + thick, cy + R], fill=(150, 95, 15, 255))
        d.ellipse([cx - rx, cy - R, cx + rx, cy + R], fill=(255, 196, 40, 255))
        ir = 0.74
        d.ellipse([cx - rx * ir, cy - R * ir, cx + rx * ir, cy + R * ir],
                  outline=(215, 145, 20, 255), width=max(1, int(R * 0.08)))
        hx = cx - rx * 0.35
        d.ellipse([hx - rx * 0.18, cy - R * 0.62, hx + rx * 0.18, cy - R * 0.2], fill=(255, 242, 170, 230))
        glow.ellipse([(cx - rx) * hs, (cy - R) * hs, (cx + rx) * hs, (cy + R) * hs], fill=(120, 85, 10))

    @staticmethod
    def add_at(frame, layer, x, y):
        W, H = frame.size
        if x >= 0 and y >= 0 and x + layer.width <= W and y + layer.height <= H:
            box = (x, y, x + layer.width, y + layer.height)
            frame.paste(ImageChops.add(frame.crop(box), layer), box[:2])
            return frame
        canvas = Image.new("RGB", (W, H))
        canvas.paste(layer, (x, y))
        return ImageChops.add(frame, canvas)

    # ----------------------------------------------------------------- frame
    def frame(self, T):
        W, H = self.W, self.H
        hs = 0.5
        hw, hh = int(W * hs), int(H * hs)
        cx, cy = W / 2, H / 2
        I = self.impact
        ti = T - I

        drift = T / self.dur
        ox = int((self.bg.width - W) * (0.25 + 0.5 * drift))
        oy = int((self.bg.height - H) * 0.5)
        k = 0.40 * clamp(T / 0.15) if T < I else lerp(0.40, 0.70, ease_out_cubic(clamp(ti / 1.0)))
        frame = self.bg.crop((ox, oy, ox + W, oy + H)).point(lambda v, k=k: int(v * k))

        fx = Image.new("RGB", (hw, hh))
        g = ImageDraw.Draw(fx)
        hcx, hcy = cx * hs, cy * hs

        if T < I + 0.03:
            for p in self.particles:
                q = clamp((T - p["d"]) / (I - p["d"]))
                if q <= 0:
                    continue
                e = q ** 2.2
                rr = p["r0"] * (1 - e) * hs
                a = p["a"] + p["swirl"] * e
                x, y = hcx + rr * math.cos(a), hcy + rr * math.sin(a) * 0.62
                br = clamp(q / 0.15) * (0.55 + 0.45 * e)
                s = p["size"] * H * 0.0022 * hs * (1 + e)
                col = tuple(int(c * br) for c in (CYAN if p["size"] < 1.4 else CYAN_LIGHT))
                g.ellipse([x - s, y - s, x + s, y + s], fill=col)
            core = clamp((T - I * 0.55) / (I * 0.45))
            if core > 0:
                cr = H * 0.055 * hs * core ** 2
                g.ellipse([hcx - cr, hcy - cr, hcx + cr, hcy + cr], fill=CYAN_LIGHT)

        if 0 <= ti < 0.7:
            p = ease_out_cubic(ti / 0.7)
            rr = W * 0.75 * p * hs
            col = tuple(int(c * (1 - p)) for c in CYAN_LIGHT)
            g.ellipse([hcx - rr, hcy - rr * 0.6, hcx + rr, hcy + rr * 0.6], outline=col,
                      width=max(1, int(H * 0.012 * hs * (1 - p) + 1)))
        if 0 <= ti < 1.4:
            p = ti / 1.4
            for s_ in self.sparks:
                dist = s_["v"] * ease_out_cubic(p) * hs
                x = hcx + dist * math.cos(s_["a"])
                y = hcy + dist * math.sin(s_["a"]) * 0.65
                s = s_["size"] * H * 0.002 * hs
                col = tuple(int(c * (1 - p)) for c in CYAN_LIGHT)
                g.ellipse([x - s, y - s, x + s, y + s], fill=col)
        if ti > 0:
            fade = clamp(ti / 1.0)
            for dd in self.dust:
                x = (dd["x"] + 0.004 * math.sin(T + dd["ph"])) * hw
                y = ((dd["y"] - dd["v"] * T) % 1.0) * hh
                tw = 0.5 + 0.5 * math.sin(T * 2.3 + dd["ph"])
                s = dd["size"] * H * 0.0018 * hs
                col = tuple(int(c * fade * tw * 0.8) for c in CYAN_LIGHT)
                g.ellipse([x - s, y - s, x + s, y + s], fill=col)

        # Petites particules lumineuses autour du texte.
        tt = T - self.text_t
        if tt > 0:
            for sp in self.text_sparkles:
                k2 = clamp(tt / 0.4) * max(0.0, math.sin(T * sp["f"] + sp["ph"])) ** 3
                if k2 > 0.02:
                    self.star(g, sp["x"] * hw, sp["y"] * hh, H * 0.012 * hs * sp["s"] * (0.5 + k2), k2)

        items = None
        if ti > 0:
            items = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(items)
            for c in self.crystals:
                p = clamp((ti - c["d"]) / 0.45)
                if p <= 0:
                    continue
                sc = ease_out_back(p)
                x = c["x"] * W
                y = c["y"] * H + H * 0.01 * math.sin(T * 1.3 + c["ph"])
                tw = max(0.0, math.sin(T * 2.1 + c["ph"])) ** 6
                self.draw_crystal(d, g, x, y, H * 0.06 * c["s"] * sc,
                                  c["rot"] + 4 * math.sin(T + c["ph"]), tw, hs)
            for c in self.coins:
                p = clamp((ti - c["d"]) / 0.45)
                if p <= 0:
                    continue
                sc = ease_out_back(p)
                x = c["x"] * W
                y = c["y"] * H + H * 0.012 * math.sin(T * 1.1 + c["ph"])
                self.draw_coin(d, g, x, y, H * 0.05 * c["s"] * sc, T * 2.4 + c["ph"], hs)

        glow = fx.filter(ImageFilter.GaussianBlur(H * 0.006 * hs))
        fx = ImageChops.add(ImageChops.add(fx, glow), glow)
        frame = ImageChops.add(frame, fx.resize((W, H), Image.BILINEAR))
        if items is not None:
            frame = Image.alpha_composite(frame.convert("RGBA"), items).convert("RGB")
        frame = ImageChops.multiply(frame, self.vignette)

        lay = self.logo_layout(T)
        if lay is not None:
            fit, ly_c = lay
            logo, lglow, pad = self.logo_at(fit)
            lx, ly = int(cx - logo.width / 2), int(ly_c * H - logo.height / 2)
            intensity = 0.6 + 0.9 * math.exp(-3 * max(0, ti)) + 0.08 * math.sin(T * 2.0)
            frame = self.add_at(frame, lglow.point(lambda v, i=intensity: min(255, int(v * i))), lx - pad, ly - pad)
            logo = self.shine(logo, T)
            frame.paste(logo, (lx, ly), logo)

        if tt > 0:
            p = clamp(tt / 0.45)
            sc = max(0.05, ease_out_back(p, 2.2))
            txt = self.text.resize((max(2, int(self.text.width * sc)), max(2, int(self.text.height * sc))), Image.LANCZOS)
            halo = self.text_halo.resize(txt.size, Image.BILINEAR)
            hk = 0.55 + 0.6 * math.exp(-4 * tt) + 0.1 * math.sin(T * 3)
            tx, ty = int(cx - txt.width / 2), int(self.text_y * H - txt.height / 2)
            frame = self.add_at(frame, halo.point(lambda v, k=hk: min(255, int(v * k))), tx, ty)
            a = txt.getchannel("A").point(lambda v, k=clamp(tt / 0.12): int(v * k))
            frame.paste(txt, (tx, ty), a)
            if tt < 0.3:  # petit éclat lumineux à l'apparition du texte
                frame = ImageChops.add(frame, solid((W, H), (120, 220, 255), 0.35 * math.exp(-tt * 12)))

        if 0 <= ti < 0.5:
            frame = ImageChops.add(frame, solid((W, H), (190, 245, 255), math.exp(-ti * 9)))

        if 0 <= ti < 0.6:
            amp = min(W, H) * 0.012 * math.exp(-ti * 6)
            dx, dy = amp * math.sin(ti * 95), amp * math.cos(ti * 71)
            z = 1.04
            bw, bh = W / z, H / z
            x0, y0 = (W - bw) / 2 + dx, (H - bh) / 2 + dy
            frame = frame.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + bw, y0 + bh))

        if T > self.fade_t:
            k = 1 - clamp((T - self.fade_t) / (self.dur - self.fade_t))
            frame = frame.point(lambda v, k=k: int(v * k * k))
        return frame


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logo", required=True)
    ap.add_argument("--background", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--impact", type=float, required=True)
    ap.add_argument("--text", type=float, required=True)
    ap.add_argument("--fade", type=float, required=True)
    ap.add_argument("--duration", type=float, required=True)
    ap.add_argument("--size", default="1920x1080")
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--crf", default="16")
    ap.add_argument("--preset", default="slow")
    a = ap.parse_args()

    W, H = (int(v) for v in a.size.split("x"))
    fin = Finale(a, W, H, a.fps)
    n = int(round(a.duration * a.fps))
    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(a.fps), "-i", "-",
         "-c:v", "libx264", "-preset", a.preset, "-crf", a.crf, "-pix_fmt", "yuv420p", a.out],
        stdin=subprocess.PIPE)
    for i in range(n):
        enc.stdin.write(fin.frame(i / a.fps).tobytes())
    enc.stdin.close()
    sys.exit(enc.wait())


if __name__ == "__main__":
    main()
