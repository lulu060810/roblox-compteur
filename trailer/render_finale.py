#!/usr/bin/env python3
"""Rend la séquence finale du trailer MINE TO GET RICH (21,5 s -> 30 s).

  21,5 -> 23,0 s : fond du jeu flouté et assombri, particules bleues qui convergent
  23,0 s         : impact (flash cyan, onde de choc, tremblement de caméra)
  23,0 -> 30,0 s : logo officiel en zoom 3D, cristaux, pièces d'or, reflets

Le logo n'est JAMAIS redessiné : le PNG fourni est seulement mis à l'échelle,
déplacé et traversé par un reflet lumineux temporaire.

Usage :
  python3 render_finale.py --logo assets/logo.png --background assets/background.png \
      --out build/finale.mp4 [--preview]
"""
import argparse
import math
import random
import subprocess
import sys

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

START = 21.5      # timecode global du début de la séquence
IMPACT = 1.5      # impact à 23,0 s (temps local)
DURATION = 8.5    # fin à 30,0 s

CYAN = (60, 220, 255)
CYAN_LIGHT = (180, 245, 255)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out_back(p, s=1.6):
    p -= 1
    return p * p * ((s + 1) * p + s) + 1


def ease_out_cubic(p):
    return 1 - (1 - p) ** 3


def lerp(a, b, p):
    return a + (b - a) * p


def solid(size, color, k):
    return Image.new("RGB", size, tuple(int(c * k) for c in color))


class Finale:
    def __init__(self, logo_path, bg_path, W, H, fps, seed=7):
        self.W, self.H, self.fps = W, H, fps
        self.rng = random.Random(seed)

        logo = Image.open(logo_path)
        if logo.mode != "RGBA":
            print("Info : logo sans transparence, affiché tel quel (image entière).", file=sys.stderr)
        self.logo = logo.convert("RGBA")
        # Le logo final occupe une grande partie de l'écran.
        fit = min(0.70 * W / self.logo.width, 0.84 * H / self.logo.height)
        self.logo_w = self.logo.width * fit
        self.logo_h = self.logo.height * fit
        if fit > 1.0:
            print(f"ATTENTION : logo agrandi x{fit:.2f}, fournissez un PNG plus grand "
                  f"(>= {int(self.logo_w)} px de large) pour une netteté 4K.", file=sys.stderr)
        base = self.logo.resize((round(self.logo_w), round(self.logo_h)), Image.LANCZOS)
        glow = base.getchannel("A").filter(ImageFilter.GaussianBlur(H * 0.025))
        self.glow_base = Image.merge("RGB", [glow.point(lambda v, c=c: v * c // 255) for c in CYAN])
        self._logo_cache = {}

        # Arrière-plan : capture du jeu, légèrement floutée, un peu plus grande pour la dérive.
        self.over = 1.06
        bg = Image.open(bg_path).convert("RGB")
        bw, bh = int(W * self.over), int(H * self.over)
        s = max(bw / bg.width, bh / bg.height)
        bg = bg.resize((math.ceil(bg.width * s), math.ceil(bg.height * s)), Image.LANCZOS)
        left, top = (bg.width - bw) // 2, (bg.height - bh) // 2
        self.bg = bg.crop((left, top, left + bw, top + bh)).filter(ImageFilter.GaussianBlur(H * 0.006))

        # Vignette pré-calculée (multiplicative).
        vw, vh = W // 8, H // 8
        vig = Image.new("L", (vw, vh))
        vig.putdata([int(255 * clamp(1.15 - 0.85 * (((x - vw / 2) / (vw / 2)) ** 2 + ((y - vh / 2) / (vh / 2)) ** 2) ** 0.5 * 0.75))
                     for y in range(vh) for x in range(vw)])
        self.vignette = Image.merge("RGB", [vig.resize((W, H), Image.BILINEAR)] * 3)

        r = self.rng
        # Particules qui convergent vers le centre (spirale légère).
        self.particles = [dict(a=r.uniform(0, 2 * math.pi), r0=r.uniform(0.55, 1.15) * W,
                               d=r.uniform(0.0, 0.7), size=r.uniform(0.6, 1.8),
                               swirl=r.uniform(0.5, 1.2)) for _ in range(420)]
        # Étincelles projetées à l'impact.
        self.sparks = [dict(a=r.uniform(0, 2 * math.pi), v=r.uniform(0.25, 0.9) * W,
                            size=r.uniform(0.6, 1.6)) for _ in range(160)]
        # Poussière lumineuse ambiante après l'impact.
        self.dust = [dict(x=r.random(), y=r.random(), v=r.uniform(0.01, 0.04),
                          ph=r.uniform(0, 6.28), size=r.uniform(0.5, 1.2)) for _ in range(90)]
        # Cristaux bleus et pièces d'or, placés autour du logo (derrière lui).
        # Cristaux bleus et pièces d'or, placés de part et d'autre du logo (derrière lui).
        self.crystals = [dict(x=x, y=y, s=s, rot=rot, ph=r.uniform(0, 6.28), d=r.uniform(0, 0.25))
                         for x, y, s, rot in [(0.12, 0.20, 1.3, -18), (0.88, 0.18, 1.1, 20),
                                              (0.06, 0.55, 0.9, -8), (0.94, 0.60, 1.3, 12),
                                              (0.17, 0.86, 1.0, -25), (0.83, 0.85, 0.95, 28),
                                              (0.24, 0.40, 0.7, 10), (0.76, 0.36, 0.75, -12)]]
        self.coins = [dict(x=x, y=y, s=s, ph=r.uniform(0, 6.28), d=r.uniform(0.05, 0.35))
                      for x, y, s in [(0.20, 0.62, 1.0), (0.80, 0.70, 1.1), (0.05, 0.85, 0.9),
                                      (0.95, 0.88, 0.85), (0.06, 0.12, 0.8), (0.94, 0.38, 0.8)]]

    # ------------------------------------------------------------------ logo
    def logo_at(self, scale):
        w = max(2, round(self.logo_w * scale))
        h = max(2, round(self.logo_h * scale))
        if (w, h) not in self._logo_cache:
            if len(self._logo_cache) > 4:
                self._logo_cache.clear()
            self._logo_cache[(w, h)] = (self.logo.resize((w, h), Image.LANCZOS),
                                        self.glow_base.resize((w, h), Image.BILINEAR))
        return self._logo_cache[(w, h)]

    def logo_scale(self, T):
        p = (T - IMPACT) / 0.55
        if p <= 0:
            return None
        if p < 1:
            # Arrive du fond (profondeur) avec un léger dépassement puis se stabilise.
            return lerp(0.12, 1.0, ease_out_back(p))
        return 1.0 + 0.035 * ease_out_cubic(clamp((T - IMPACT - 0.55) / 6.0))

    def shine(self, logo, T):
        """Reflet lumineux qui balaie les lettres (masqué par l'alpha du logo)."""
        for t0, dur in ((IMPACT + 0.75, 0.7), (IMPACT + 3.6, 0.8)):
            p = (T - t0) / dur
            if 0 <= p <= 1:
                w, h = logo.size
                # Bande diagonale : u = position le long de la diagonale, de -0.2 à 1.2.
                u = (np.arange(w)[None, :] + 0.45 * np.arange(h)[:, None]) / (w + 0.45 * h)
                c = lerp(-0.2, 1.2, ease_out_cubic(p))
                band = np.exp(-((u - c) / 0.05) ** 2) * 0.6
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
        d.polygon([P[0], P[1], P[2], P[3], C], fill=(25, 140, 225, 255))      # face sombre
        d.polygon([P[0], P[5], P[4], P[3], C], fill=(95, 225, 255, 255))      # face claire
        d.polygon([P[0], P[1], C, P[5]], fill=(185, 248, 255, 255))           # facette haute
        d.line(P + [P[0]], fill=(220, 252, 255, 255), width=max(1, int(size * 0.04)))
        g = [(x * hs, y * hs) for x, y in P]
        glow.polygon(g, fill=tuple(int(v * 0.55) for v in CYAN))
        if twinkle > 0:
            tx, ty = P[0][0] * hs, P[0][1] * hs
            L = size * hs * 0.9 * twinkle
            col = tuple(int(255 * twinkle) for _ in range(3))
            glow.line([(tx - L, ty), (tx + L, ty)], fill=col, width=max(1, int(size * hs * 0.05)))
            glow.line([(tx, ty - L), (tx, ty + L)], fill=col, width=max(1, int(size * hs * 0.05)))

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

    # ----------------------------------------------------------------- frame
    def frame(self, T):
        W, H = self.W, self.H
        hs = 0.5
        hw, hh = int(W * hs), int(H * hs)
        cx, cy = W / 2, H / 2

        # Fond : dérive lente + luminosité (sortie du noir, assombri, puis révélé).
        drift = T / DURATION
        ox = int((self.bg.width - W) * (0.25 + 0.5 * drift))
        oy = int((self.bg.height - H) * 0.5)
        if T < IMPACT:
            k = 0.42 * clamp(T / 0.35)
        else:
            k = lerp(0.42, 0.72, ease_out_cubic(clamp((T - IMPACT) / 1.2)))
        frame = self.bg.crop((ox, oy, ox + W, oy + H)).point(lambda v, k=k: int(v * k))

        fx = Image.new("RGB", (hw, hh))
        g = ImageDraw.Draw(fx)
        hcx, hcy = cx * hs, cy * hs

        # Particules convergentes.
        if T < IMPACT + 0.05:
            for p in self.particles:
                q = clamp((T - p["d"]) / (IMPACT - p["d"]))
                if q <= 0:
                    continue
                e = q ** 2.4
                rr = p["r0"] * (1 - e) * hs
                a = p["a"] + p["swirl"] * e
                x, y = hcx + rr * math.cos(a), hcy + rr * math.sin(a) * 0.62
                br = clamp(q / 0.15) * (0.55 + 0.45 * e)
                s = p["size"] * H * 0.0022 * hs * (1 + e)
                col = tuple(int(c * br) for c in (CYAN if p["size"] < 1.4 else CYAN_LIGHT))
                g.ellipse([x - s, y - s, x + s, y + s], fill=col)
            # Noyau d'énergie qui grossit juste avant l'impact.
            core = clamp((T - (IMPACT - 0.45)) / 0.45)
            if core > 0:
                cr = H * 0.06 * hs * core ** 2
                g.ellipse([hcx - cr, hcy - cr, hcx + cr, hcy + cr], fill=CYAN_LIGHT)

        # Après l'impact : onde de choc, étincelles, poussière lumineuse.
        ti = T - IMPACT
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

        # Cristaux et pièces (calque plein écran, derrière le logo).
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

        # Logo (image officielle, intacte) + halo cyan.
        scale = self.logo_scale(T)
        if scale is not None:
            logo, lglow = self.logo_at(scale)
            lx, ly = int(cx - logo.width / 2), int(cy - logo.height / 2)
            intensity = 0.55 + 0.9 * math.exp(-3 * max(0, ti)) + 0.08 * math.sin(T * 2.0)
            gl = lglow.point(lambda v, i=intensity: min(255, int(v * i)))
            if lx >= 0 and ly >= 0 and lx + logo.width <= W and ly + logo.height <= H:
                box = (lx, ly, lx + logo.width, ly + logo.height)
                frame.paste(ImageChops.add(frame.crop(box), gl), box[:2])
            else:
                canvas = Image.new("RGB", (W, H))
                canvas.paste(gl, (lx, ly))
                frame = ImageChops.add(frame, canvas)
            logo = self.shine(logo, T)
            frame.paste(logo, (lx, ly), logo)

        # Flash bleu cyan à l'impact.
        if 0 <= ti < 0.5:
            frame = ImageChops.add(frame, solid((W, H), (190, 245, 255), math.exp(-ti * 9)))

        frame = ImageChops.multiply(frame, self.vignette)

        # Tremblement de caméra à l'impact.
        if 0 <= ti < 0.6:
            amp = H * 0.012 * math.exp(-ti * 6)
            dx = amp * math.sin(ti * 95)
            dy = amp * math.cos(ti * 71)
            z = 1.04
            bw, bh = W / z, H / z
            x0 = (W - bw) / 2 + dx
            y0 = (H - bh) / 2 + dy
            frame = frame.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + bw, y0 + bh))
        return frame


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logo", required=True)
    ap.add_argument("--background", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--preview", action="store_true", help="1280x720 30 i/s pour valider vite")
    a = ap.parse_args()

    W, H, fps = (1280, 720, 30) if a.preview else (3840, 2160, 60)
    fin = Finale(a.logo, a.background, W, H, fps)
    n = int(round(DURATION * fps))
    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
         "-c:v", "libx264", "-preset", "veryfast" if a.preview else "slow",
         "-crf", "20" if a.preview else "14", "-pix_fmt", "yuv420p", a.out],
        stdin=subprocess.PIPE)
    for i in range(n):
        enc.stdin.write(fin.frame(i / fps).tobytes())
        if i % fps == 0:
            print(f"  finale {START + i / fps:5.1f} s / 30.0 s", file=sys.stderr)
    enc.stdin.close()
    sys.exit(enc.wait())


if __name__ == "__main__":
    main()
