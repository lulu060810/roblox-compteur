"""Prépare les assets : carte Roblox détourée, piste audio 20 s + SFX, enveloppe audio pour l'animation."""
import json, wave
import numpy as np
from PIL import Image, ImageDraw
import music as sfx

U = "/root/.claude/uploads/f4a76015-ff4d-5f01-aa1e-05642026cf44/"
# --- carte : détourage du fond blanc par remplissage depuis les coins
im = Image.open(U + "889558c8-image.webp").convert("RGB")
mask = im.copy()
for p in [(0, 0), (im.width - 1, 0), (0, im.height - 1), (im.width - 1, im.height - 1), (im.width // 2, 0), (im.width // 2, im.height - 1)]:
    ImageDraw.floodfill(mask, p, (255, 0, 255), thresh=40)
a = np.array(mask)
alpha = np.where((a[..., 0] == 255) & (a[..., 1] == 0) & (a[..., 2] == 255), 0, 255).astype(np.uint8)
rgba = np.dstack([np.array(im), alpha])
out = Image.fromarray(rgba, "RGBA")
out = out.crop(out.getbbox())
out.save("assets/roblox_card.png")
print("carte", out.size)

# --- audio
SR = 44100
START, DUR = 35.04, 20.0
w = wave.open("src/track_full.wav")
w.setpos(int(START * SR))
x = np.frombuffer(w.readframes(int(DUR * SR)), np.int16).reshape(-1, 2).astype(np.float64) / 32768
N = len(x)
fx = np.zeros(N)
B = 60 / 137.9
for sig, t, g in [(sfx.ding(), 0.0, 0.55), (sfx.whoosh(0.45), 2.65, 0.35), (sfx.whoosh(0.45), 6.55, 0.35),
                  (sfx.shimmer(), 10.87, 0.8), (sfx.whoosh(0.45), 12.65, 0.35), (sfx.whoosh(0.3), 14.1, 0.25),
                  (sfx.whoosh(0.3), 15.4, 0.25), (sfx.whoosh(1.6), 15.8, 0.55), (sfx.impact(), 17.40, 0.55)]:
    sfx.add(fx, sig, t, g)
for k, t in enumerate([7.2, 8.27, 9.57]):
    sfx.add(fx, sfx.ding(), t, 0.25)
mix = x + fx[:, None] * 0.9
fade = np.ones(N); k = int(0.45 * SR); fade[-k:] = np.linspace(1, 0, k) ** 1.5
mix *= fade[:, None]
mix = np.tanh(mix * 1.05) / np.tanh(1.05) * 0.97
with wave.open("build_audio.wav", "wb") as o:
    o.setnchannels(2); o.setsampwidth(2); o.setframerate(SR)
    o.writeframes((np.clip(mix, -1, 1) * 32767).astype(np.int16).tobytes())

# --- enveloppe audio par image (60 fps) : graves (kick/808) et aigus
FPS = 60
mono = x.mean(1)
hop = SR // FPS
lowv, highv = [], []
win = 2048
for f in range(int(DUR * FPS)):
    s = f * hop
    seg = mono[s:s + win]
    if len(seg) < win: seg = np.pad(seg, (0, win - len(seg)))
    sp = np.abs(np.fft.rfft(seg * np.hanning(win)))
    fr = np.fft.rfftfreq(win, 1 / SR)
    lowv.append(sp[fr < 120].sum()); highv.append(sp[fr > 5000].sum())
def norm(v, rel):
    v = np.array(v); v = v / (np.percentile(v, 98) + 1e-9)
    out, acc = [], 0
    for e in v:
        acc = e if e > acc else acc * rel
        out.append(round(float(min(acc, 1.2)), 3))
    return out
json.dump({"fps": FPS, "low": norm(lowv, 0.82), "high": norm(highv, 0.8)}, open("assets/audio.json", "w"))
print("audio ok")
