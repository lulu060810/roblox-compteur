#!/usr/bin/env python3
"""Trailer MINE TO GET RICH v4 : refrain de « Nightcall » + textes animés.

30 s, 1920x1080, 60 i/s, H.264 + AAC stéréo. La musique est uniquement le 1er refrain
(59,4 s -> 89,4 s du fichier assets/nightcall.mp3, ~97 BPM, 1 temps = 0,6186 s).
Chaque coupe et chaque texte tombent sur un temps ; le BOOM du logo tombe sur le
temps 40, en milieu de la 3e phrase du refrain.

  python3 build_trailer_v4.py            -> build/MINE_TO_GET_RICH_trailer_v4_1080p.mp4
  python3 build_trailer_v4.py --preview  -> 640x360 30 i/s

Réutilise les plans, la séquence logo et le mixage de build_trailer_v3.py.
"""
import argparse
import os
import subprocess

from PIL import Image, ImageFilter

import build_trailer_v3 as v3
from render_finale_v3 import render_text

A, B, AERIAL, ARENA = v3.A, v3.B, v3.AERIAL, v3.ARENA
ILE = "assets/footage/ile.mp4"   # arrivée par l'océan sur l'île (rendu 1280x720, 24 i/s)

SHOTS = [
    # Phrase 1 — on découvre le monde
    ("s01", None, 10, "clip", dict(src=ILE, a=0.0, b=6.0, studio=False, smooth=True, fadein=True)),
    ("s04", 10, 12, "clip", dict(src=B, a=1.6, b=4.0, flash=True)),
    ("s05", 12, 14, "clip", dict(src=A, a=0.0, b=1.5, zoom=True, flash=True)),
    ("s06", 14, 16, "still", dict(img=AERIAL, motion="zoom_center", flash=True)),
    # Phrase 2 — le montage accélère (2 temps par plan)
    ("s07", 16, 18, "clip", dict(src=B, a=7.6, b=10.0, punch=True)),
    ("s08", 18, 20, "still", dict(img=AERIAL, motion="pan_roofs", punch=True)),
    ("s09", 20, 22, "clip", dict(src=A, a=5.0, b=7.4, punch=True)),
    ("s10", 22, 24, "still", dict(img=AERIAL, motion="zoom_fast", punch=True)),
    ("s11", 24, 26, "clip", dict(src=B, a=8.4, b=10.6, punch=True, blur=True)),
    ("s12", 26, 28, "still", dict(img=ARENA, motion="pan_fast", punch=True)),
    ("s13", 28, 30, "still", dict(img=AERIAL, motion="rotate", punch=True)),
    ("s14", 30, 32, "clip", dict(src=B, a=0.5, b=4.0, punch=True, blur=True)),
    # Phrase 3 — un plan par temps, puis la caméra s'éloigne
    ("s15", 32, 33, "clip", dict(src=B, a=10.0, b=11.0, punch=True)),
    ("s16", 33, 34, "clip", dict(src=A, a=0.3, b=1.0, punch=True)),
    ("s17", 34, 35, "still", dict(img=AERIAL, motion="zoom_fast", punch=True)),
    ("s18", 35, 36, "clip", dict(src=B, a=2.0, b=4.0, punch=True, blur=True)),
    # la caméra quitte l'arène et révèle l'île entière dans l'océan
    ("s19", 36, 39, "clip", dict(src=ILE, a=4.0, b=10.0, reverse=True, studio=False, smooth=True, darken=True)),
]

# (texte, temps d'apparition, temps de disparition, taille relative à la hauteur)
TEXTES = [
    ("UNE ÎLE À EXPLORER", 4, 8, 0.10),
    ("CREUSE", 10, 12.5, 0.16),
    ("TROUVE DES MINERAIS RARES", 12.5, 16, 0.085),
    ("DEVIENS RICHE", 18, 22, 0.13),
    ("ES-TU PRÊT ?", 28, 32, 0.13),
]


def ease_out_back(p, s=2.0):
    p -= 1
    return p * p * ((s + 1) * p + s) + 1


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def render_text_track(path, W, H, fps, duree):
    """Piste de textes transparente (PNG dans MOV) superposée aux plans du jeu."""
    items = []
    for txt, b0, b1, sc in TEXTES:
        img, halo = render_text(H, txt, sc)
        a = img.getchannel("A")
        shadow = Image.new("RGBA", img.size, (0, 10, 30, 0))
        shadow.putalpha(a.filter(ImageFilter.GaussianBlur(H * 0.012)).point(lambda v: int(v * 0.75)))
        halo_rgba = Image.merge("RGBA", (*halo.split(), halo.convert("L").point(lambda v: min(255, v * 2))))
        base = Image.alpha_composite(Image.alpha_composite(shadow, halo_rgba), img)
        items.append((base, v3.beat(b0), v3.beat(b1)))

    n = int(round(duree * fps))
    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
         "-r", str(fps), "-i", "-", "-c:v", "png", path], stdin=subprocess.PIPE)
    empty = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for i in range(n):
        t = i / fps
        frame = empty
        for base, t0, t1 in items:
            if not t0 <= t < t1:
                continue
            p_in = clamp((t - t0) / 0.28)
            p_out = clamp((t - (t1 - 0.16)) / 0.16)
            sc = max(0.05, ease_out_back(p_in)) * (1 + 0.05 * (t - t0) / (t1 - t0)) * (1 + 0.35 * p_out)
            alpha = clamp((t - t0) / 0.06) * (1 - p_out)
            w, h = max(2, int(base.width * sc)), max(2, int(base.height * sc))
            im = base.resize((w, h), Image.BILINEAR)
            if alpha < 1:
                im.putalpha(im.getchannel("A").point(lambda v, k=alpha: int(v * k)))
            frame = frame.copy()
            frame.alpha_composite(im, (int(W / 2 - w / 2), int(H * 0.5 - h / 2)))
        enc.stdin.write(frame.tobytes())
    enc.stdin.close()
    if enc.wait():
        raise SystemExit("échec de la piste de textes")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true")
    a = ap.parse_args()

    v3.choisir("nightcall")
    v3.PREMIER_TEMPS = 0.0          # le refrain démarre pile sur la 1re image
    v3.DEBUT = 59.42                # début du 1er refrain dans le fichier
    v3.SHOTS = SHOTS
    v3.FINALE_START, v3.BOOM, v3.TEXTE, v3.FONDU = 39, 40, 44, 46
    v3.FINALE_OPTIONS = ["--slam"]   # arrivée du logo améliorée
    v3.WHOOSH = list(range(16, 32, 2)) + [32, 33, 34, 35, 36]

    b = v3.Builder(a.preview, "v4")
    b.out = os.path.join("build", "MINE_TO_GET_RICH_trailer_v4_%s.mp4" % ("preview" if a.preview else "1080p"))
    tmp = os.path.join(v3.HERE, b.tmp)
    print("1/4 Plans")
    b.video()
    print("2/4 Textes")
    t_fin = v3.beat(v3.FINALE_START)
    n_mont = b.frames(t_fin)
    render_text_track(os.path.join(tmp, "textes.mov"), b.W, b.H, b.FPS, n_mont / b.FPS)
    with open(os.path.join(tmp, "montage.txt"), "w") as fh:
        fh.writelines(f"file '{name}.mp4'\n" for name, *_ in SHOTS)
    v3.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{b.tmp}/montage.txt",
            "-i", f"{b.tmp}/textes.mov", "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto,format=yuv420p",
            "-frames:v", str(n_mont)] + b.enc(f"{b.tmp}/montage_textes.mp4", n_mont)[2:])
    with open(os.path.join(tmp, "list.txt"), "w") as fh:
        fh.write("file 'montage_textes.mp4'\nfile 'final.mp4'\n")
    print("3/4 Audio")
    b.audio()
    print("4/4 Assemblage")
    b.mux()


if __name__ == "__main__":
    main()
