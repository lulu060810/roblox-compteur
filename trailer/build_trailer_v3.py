#!/usr/bin/env python3
"""Trailer MINE TO GET RICH v3 : 30 s, 1920x1080, 60 i/s, H.264 + AAC stéréo.

Toutes les coupes tombent sur la grille des temps du morceau choisi :
temps k = PREMIER_TEMPS + k * TEMPS (voir MUSIQUES).

  python3 build_trailer_v3.py                        -> « Upside Down » (assets/musique.mp3)
  python3 build_trailer_v3.py --musique nightcall    -> « Nightcall » (assets/nightcall.mp3)
  ajouter --preview pour un rendu 640x360 30 i/s rapide

Pour une autre musique : mesurer son tempo et ses temps forts, ajouter une entrée
dans MUSIQUES et REPERES ; le montage se recale automatiquement.
"""
import argparse
import os
import subprocess
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
A = "assets/footage/aerien.mov"        # gros plan minerais puis la caméra s'élève au-dessus de la carte
B = "assets/footage/sol.mov"           # travelling au ras du sol vers l'arène
AERIAL = "assets/vue_aerienne.png"     # arène vue du dessus
ARENA = "assets/arene.png"             # falaises bleues, arbres, nuages orangés
LOGO = "assets/logo_detoure.png"       # logo officiel détouré (pixels d'origine)
FOND = "assets/fond_final.png"         # vraie carte, floutée sous le logo
DUREE = 30.0

# Grille de chaque musique : TEMPS = durée d'un temps, PREMIER_TEMPS = instant (dans la vidéo)
# du temps n°0, DEBUT = position dans le morceau qui correspond à 0 s de vidéo.
MUSIQUES = {
    "upside": dict(fichier="assets/musique.mp3", temps=0.5572, premier=0.432, debut=0.0, gain=0.9),
    # Nightcall : ~97 BPM, phrases de 16 temps ; le BOOM (temps 40) tombe sur un début de phrase.
    "nightcall": dict(fichier="assets/nightcall.mp3", temps=0.6186, premier=0.30, debut=24.464, gain=0.72),
}
MUSIQUE, TEMPS, PREMIER_TEMPS, DEBUT, GAIN = None, None, None, None, None


def beat(k):
    return PREMIER_TEMPS + k * TEMPS


# (nom, début en temps, fin en temps, type, paramètres)
# Le 1er plan commence à 0 s (écran noir très court puis ouverture sur le 1er temps).
SHOTS_UPSIDE = [
    # SCÈNE 1 — introduction : falaises, arbres cubiques, nuages orangés, puis la carte vue du ciel
    ("s01", None, 4, "still", dict(img=ARENA, motion="push", fadein=True)),
    ("s02", 4, 6, "clip", dict(src=B, a=0.0, b=1.6)),
    ("s03", 6, 10, "clip", dict(src=A, a=4.4, b=7.4, reverse=True)),
    # SCÈNE 2 — découverte de la carte
    ("s04", 10, 14, "clip", dict(src=B, a=1.6, b=5.6, flash=True)),
    ("s05", 14, 18, "still", dict(img=AERIAL, motion="zoom_center", flash=True)),
    ("s06", 18, 20, "clip", dict(src=B, a=7.6, b=10.0, flash=True)),
    ("s07", 20, 22, "still", dict(img=AERIAL, motion="pan_roofs", flash=True)),
    ("s08", 22, 24, "clip", dict(src=A, a=0.0, b=1.5, zoom=True, flash=True)),
    # SCÈNE 3 — montage dynamique, une coupe tous les 2 temps
    ("s09", 24, 26, "clip", dict(src=A, a=5.0, b=7.4, punch=True)),
    ("s10", 26, 28, "still", dict(img=AERIAL, motion="zoom_fast", punch=True)),
    ("s11", 28, 30, "clip", dict(src=B, a=8.4, b=10.6, punch=True, blur=True)),
    ("s12", 30, 32, "still", dict(img=ARENA, motion="pan_fast", punch=True)),
    ("s13", 32, 34, "still", dict(img=AERIAL, motion="rotate", punch=True)),
    ("s14", 34, 36, "clip", dict(src=B, a=0.5, b=4.0, punch=True, blur=True)),
    ("s15", 36, 38, "clip", dict(src=B, a=10.0, b=11.8, punch=True)),
    # SCÈNE 4 — la caméra s'éloigne et révèle toute la carte
    ("s16", 38, 41, "clip", dict(src=A, a=3.4, b=7.4, blur=True, darken=True)),
]
# Nightcall est plus lent (temps plus longs) : même découpage, 2 temps de moins en scène 2.
SHOTS_NIGHTCALL = SHOTS_UPSIDE[:4] + [
    ("s05", 14, 16, "still", dict(img=AERIAL, motion="zoom_center", flash=True)),
    ("s06", 16, 18, "clip", dict(src=B, a=7.6, b=10.0, flash=True)),
    ("s07", 18, 20, "still", dict(img=AERIAL, motion="pan_roofs", flash=True)),
    ("s08", 20, 22, "clip", dict(src=A, a=0.0, b=1.5, zoom=True, flash=True)),
] + [(n, b0 - 2, b1 - 2, k, o) for n, b0, b1, k, o in SHOTS_UPSIDE[8:]]

# suspension d'un temps (FINALE_START -> BOOM), texte, début du fondu ; whoosh de la scène 3
REPERES = {
    "upside": dict(shots=SHOTS_UPSIDE, finale=41, boom=42, texte=46, fondu=50, whoosh=range(24, 40, 2)),
    "nightcall": dict(shots=SHOTS_NIGHTCALL, finale=39, boom=40, texte=44, fondu=46, whoosh=range(22, 38, 2)),
}
SHOTS = FINALE_START = BOOM = TEXTE = FONDU = WHOOSH = None
FINALE_OPTIONS = []   # options en plus pour render_finale_v3.py (ex. ["--slam"])


def choisir(nom):
    global MUSIQUE, TEMPS, PREMIER_TEMPS, DEBUT, GAIN, SHOTS, FINALE_START, BOOM, TEXTE, FONDU, WHOOSH
    m, r = MUSIQUES[nom], REPERES[nom]
    MUSIQUE, TEMPS, PREMIER_TEMPS, DEBUT, GAIN = m["fichier"], m["temps"], m["premier"], m["debut"], m["gain"]
    SHOTS, FINALE_START, BOOM, TEXTE, FONDU, WHOOSH = (
        r["shots"], r["finale"], r["boom"], r["texte"], r["fondu"], r["whoosh"])


def run(cmd):
    subprocess.run(cmd, check=True, cwd=HERE)


class Builder:
    def __init__(self, preview, nom):
        self.W, self.H, self.FPS = (640, 360, 30) if preview else (1920, 1080, 60)
        self.preset, self.crf = ("veryfast", "22") if preview else ("slow", "16")
        self.tmp = os.path.join("build", "tmp_v3_" + nom)
        suffixe = "" if nom == "upside" else "_" + nom
        self.out = os.path.join("build", "MINE_TO_GET_RICH_trailer_v3%s_%s.mp4" % (suffixe, "preview" if preview else "1080p"))
        os.makedirs(os.path.join(HERE, self.tmp), exist_ok=True)

    def frames(self, t):
        return int(round(t * self.FPS))

    def enc(self, path, nframes):
        return ["-frames:v", str(nframes), "-an", "-c:v", "libx264", "-preset", self.preset,
                "-crf", self.crf, "-pix_fmt", "yuv420p", "-r", str(self.FPS), path]

    def look(self, o):
        W, H = self.W, self.H
        f = []
        if o.get("punch"):  # petit zoom d'impact sur la coupe, qui retombe en 0,2 s
            f.append(f"scale=w='{W}*(1+0.10*max(0\\,1-t/0.2))':h=-2:eval=frame,crop={W}:{H}")
        f.append("eq=contrast=1.07:saturation=1.25:gamma=0.98")
        f.append("unsharp=5:5:0.5")
        f.append("vignette=PI/5")
        if o.get("flash") or o.get("punch"):
            f.append("fade=t=in:st=0:d=0.12:color=0xD6FAFF")
        return f

    def clip(self, name, dur, n, o):
        W, H = self.W, self.H
        speed = (o["b"] - o["a"]) / dur
        pre = ["reverse"] if o.get("reverse") else []
        if o.get("studio", True):  # rush Roblox Studio : on recadre le ViewCube
            pre.append("crop=iw*0.92:ih*0.92:0:ih*0.08")
        if o.get("smooth"):  # rush à 24 i/s : images intermédiaires calculées pour un mouvement fluide
            pre += [f"setpts=(PTS-STARTPTS)/{speed}",
                    f"minterpolate=fps={self.FPS}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"]
            speed = 1
        f = pre + [f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos", f"crop={W}:{H}",
                   "setsar=1", f"setpts=(PTS-STARTPTS)/{speed}", f"fps={self.FPS}",
                   "tpad=stop_mode=clone:stop_duration=1"]
        if o.get("blur"):
            f.append("tmix=frames=3:weights='1 2 1'")  # léger flou de vitesse
        if o.get("zoom"):
            f.append(f"scale=w='{W}*(1+0.10*t/{dur})':h=-2:eval=frame,crop={W}:{H}")
        f += self.look(o)
        if o.get("fadein"):
            f.append("fade=t=in:st=0:d=0.5")
        if o.get("darken"):
            f.append(f"fade=t=out:st={dur - 0.35}:d=0.35")
        run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(o["a"]), "-to", str(o["b"]), "-i", o["src"],
             "-vf", ",".join(f)] + self.enc(f"{self.tmp}/{name}.mp4", n))

    def still(self, name, dur, n, o):
        W, H = self.W, self.H
        big = int(H * 1.6)
        m = o["motion"]
        if m == "push":        # lente avancée + glissement latéral
            mo = f"scale=w='iw*(1.0+0.12*t/{dur})':h=-2:eval=frame,crop={W}:{H}:'(iw-{W})*(0.35+0.3*t/{dur})':'(ih-{H})*0.45'"
        elif m == "zoom_center":
            mo = f"scale=w='iw*(0.85+0.25*t/{dur})':h=-2:eval=frame,crop={W}:{H}"
        elif m == "pan_roofs":
            mo = f"scale=w='iw*1.1':h=-2,crop={W}:{H}:'(iw-{W})*(0.1+0.8*t/{dur})':'(ih-{H})*0.8'"
        elif m == "zoom_fast":
            mo = f"scale=w='iw*(0.8+0.6*pow(t/{dur}\\,0.6))':h=-2:eval=frame,crop={W}:{H}"
        elif m == "pan_fast":
            mo = f"crop='iw*0.75':'ih*0.75':'iw*0.25*t/{dur}':'ih*0.12',scale={W}:-2:flags=bicubic,crop={W}:{H}"
        elif m == "rotate":
            mo = f"scale=w='iw*1.0':h=-2,rotate=a='-0.25+0.35*t/{dur}':ow=iw:oh=ih,crop={W}:{H}"
        f = [f"scale=-2:{big}:flags=lanczos", mo, "setsar=1"] + self.look(o)
        if o.get("fadein"):
            f.append(f"fade=t=in:st={max(0.0, PREMIER_TEMPS - 0.12):.3f}:d=0.6")
        run(["ffmpeg", "-loglevel", "error", "-y", "-loop", "1", "-framerate", str(self.FPS), "-i", o["img"],
             "-vf", ",".join(f)] + self.enc(f"{self.tmp}/{name}.mp4", n))

    def video(self):
        names = []
        for name, b0, b1, kind, o in SHOTS:
            t0 = 0.0 if b0 is None else beat(b0)
            t1 = beat(b1)
            n = self.frames(t1) - self.frames(t0)
            print(f"  {name}  {t0:6.2f} -> {t1:6.2f} s  ({kind})", flush=True)
            getattr(self, kind)(name, t1 - t0, n, o)
            names.append(name)
        t0 = beat(FINALE_START)
        n = self.frames(DUREE) - self.frames(t0)
        print(f"  final  {t0:6.2f} -> {DUREE:6.2f} s  (logo)", flush=True)
        run(["python3", "render_finale_v3.py", "--logo", LOGO, "--background", FOND,
             "--out", f"{self.tmp}/final.mp4", "--size", f"{self.W}x{self.H}", "--fps", str(self.FPS),
             "--crf", self.crf, "--preset", self.preset,
             "--impact", f"{beat(BOOM) - t0:.4f}", "--text", f"{beat(TEXTE) - t0:.4f}",
             "--fade", f"{beat(FONDU) - t0:.4f}", "--duration", f"{n / self.FPS:.4f}"] + FINALE_OPTIONS)
        names.append("final")
        with open(os.path.join(HERE, self.tmp, "list.txt"), "w") as fh:
            fh.writelines(f"file '{x}.mp4'\n" for x in names)

    # ------------------------------------------------------------------ audio
    def audio(self):
        sr = 48000
        path = os.path.join(HERE, self.tmp, "music.f32")
        run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(DEBUT), "-i", MUSIQUE, "-t", str(DUREE), "-ac", "2", "-ar", str(sr),
             "-f", "f32le", path])
        mus = np.fromfile(path, np.float32).reshape(-1, 2).astype(np.float64)
        N = int(DUREE * sr)
        mus = np.pad(mus, ((0, max(0, N - len(mus))), (0, 0)))[:N]
        t = np.arange(N) / sr
        rng = np.random.default_rng(5)

        def at(sig, start, out):
            i = int(start * sr)
            n = min(len(sig), N - i)
            out[i:i + n] += sig[:n, None] if sig.ndim == 1 else sig[:n]

        def lp(x, cutoff, passes=2):
            k = max(1, int(sr / cutoff / 2))
            for _ in range(passes):
                x = np.convolve(x, np.ones(k) / k, mode="same")
            return x

        # Musique : suspension d'un temps avant le BOOM, puis fondu final avec l'image.
        s0, s1 = beat(FINALE_START), beat(BOOM)
        g = np.interp(t, [0, s0, s0 + 0.06, s1 - 0.01, s1, beat(FONDU), DUREE], [1, 1, 0.06, 0.06, 1, 1, 0])
        mus *= (g ** 1.5)[:, None]

        fx = np.zeros((N, 2))
        # Souffle inversé pendant la suspension, aspiré vers le BOOM.
        d = s1 - s0
        tt = np.arange(int(d * sr)) / sr
        sw = lp(rng.standard_normal(len(tt)), 3000) * 2.5 * (tt / d) ** 3
        at(np.stack([sw, np.roll(sw, 300)], 1) * 0.5, s0, fx)
        # BOOM : sub qui chute + déflagration filtrée.
        tt = np.arange(int(2.5 * sr)) / sr
        f = 30 + 80 * np.exp(-tt * 9)
        boom = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-tt * 2.2)
        boom += lp(rng.standard_normal(len(tt)), 1800) * np.exp(-tt * 8) * 3
        at(boom * 0.45, s1, fx)
        # Scintillements des cristaux et tintements des pièces après l'impact.
        for i, st in enumerate(np.arange(s1 + 0.15, s1 + 2.0, TEMPS / 2)):
            tt = np.arange(int(0.6 * sr)) / sr
            fr = 440 * 2 ** (([88, 91, 95, 93][i % 4] - 69) / 12)
            ch = np.sin(2 * np.pi * fr * tt) * np.exp(-tt * 7) * 0.05
            at(np.stack([ch * (i % 2), ch * (1 - i % 2)], 1) + ch[:, None] * 0.3, st, fx)
        for st in (s1 + 0.3, s1 + 0.45, s1 + 0.7):
            tt = np.arange(int(0.4 * sr)) / sr
            c = (np.sin(2 * np.pi * 3200 * tt) + 0.6 * np.sin(2 * np.pi * 4700 * tt)) * np.exp(-tt * 13) * 0.05
            at(c, st, fx)
        # Apparition du texte : petit « whoosh » + carillon.
        tt = np.arange(int(0.5 * sr)) / sr
        wn = rng.standard_normal(len(tt))
        wh = (wn - lp(wn, 500)) * np.sin(np.pi * tt / 0.5) ** 2 * 0.10
        at(wh, beat(TEXTE) - 0.35, fx)
        tt = np.arange(int(1.2 * sr)) / sr
        chime = sum(np.sin(2 * np.pi * 440 * 2 ** ((m - 69) / 12) * tt) for m in (84, 88, 91, 96)) * np.exp(-tt * 4) * 0.035
        at(chime, beat(TEXTE), fx)
        # Whoosh discrets sur les coupes de la scène 3.
        for k in WHOOSH:
            tt = np.arange(int(0.35 * sr)) / sr
            wn = rng.standard_normal(len(tt))
            wh = (wn - lp(wn, 700)) * np.sin(np.pi * tt / 0.35) ** 2 * 0.045
            at(np.stack([wh, np.roll(wh, 400)], 1), beat(k) - 0.22, fx)

        mix = mus * GAIN + fx
        # Limiteur doux : ne touche que les crêtes au-dessus de 0,9.
        over = np.abs(mix) > 0.9
        mix[over] = np.sign(mix[over]) * (0.9 + 0.09 * np.tanh((np.abs(mix[over]) - 0.9) / 0.09))
        pcm = (np.clip(mix, -1, 1) * 32767).astype("<i2")
        with wave.open(os.path.join(HERE, self.tmp, "audio.wav"), "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(pcm.tobytes())

    def mux(self):
        run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{self.tmp}/list.txt",
             "-i", f"{self.tmp}/audio.wav", "-map", "0:v", "-map", "1:a", "-c:v", "copy",
             "-c:a", "aac", "-b:a", "320k", "-ac", "2", "-t", str(DUREE), "-movflags", "+faststart", self.out])
        print("OK ->", self.out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--musique", choices=sorted(MUSIQUES), default="upside")
    a = ap.parse_args()
    choisir(a.musique)
    b = Builder(a.preview, a.musique)
    print("1/3 Plans")
    b.video()
    print("2/3 Audio")
    b.audio()
    print("3/3 Assemblage")
    b.mux()


if __name__ == "__main__":
    main()
