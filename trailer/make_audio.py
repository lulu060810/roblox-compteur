#!/usr/bin/env python3
"""Génère la bande-son temporaire du trailer (30 s, 120 BPM, 48 kHz stéréo).

  0  -> 5    vent + nappe grave qui monte
  5  -> 11   la musique démarre (accords La m - Fa - Do - Sol, kick)
  11 -> 19   montée : kick, clap, charleston, arpège, coup sourd sur chaque plan
  19 -> 21,5 riser, puis coupure brutale à 21,5 s
  21,5 -> 23 souffle inversé qui aspire vers l'impact
  23         impact (sub drop + déflagration) puis accord final, scintillements, pièces

Les coupes du montage (build_trailer.sh) tombent sur les temps : 1 temps = 0,5 s.
Remplaçable par une vraie musique sous licence : voir README.md.
"""
import sys
import wave

import numpy as np

SR = 48000
DUR = 30.0
N = int(SR * DUR)
t = np.arange(N) / SR
rng = np.random.default_rng(3)

CUTS = [5.0, 11.0, 12.5, 14.0, 15.5, 17.0, 19.0]
CUT_MUSIC = 21.5
IMPACT = 23.0


def env(times, values):
    return np.interp(t, times, values)


def at(sig, start):
    out = np.zeros(N)
    i = int(start * SR)
    n = min(len(sig), N - i)
    out[i:i + n] = sig[:n]
    return out


def lp_fast(x, cutoff, passes=2):
    # Moyenne glissante répétée : passe-bas rapide sans scipy.
    k = max(1, int(SR / cutoff / 2))
    ker = np.ones(k) / k
    for _ in range(passes):
        x = np.convolve(x, ker, mode="same")
    return x


def saw(f, tt):
    return 2 * ((f * tt) % 1.0) - 1


def note(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def kick(dur=0.45, punch=1.0):
    tt = np.arange(int(SR * dur)) / SR
    f = 45 + 110 * np.exp(-tt * 28)
    return punch * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 7)


def clap(dur=0.25):
    tt = np.arange(int(SR * dur)) / SR
    n = rng.standard_normal(len(tt))
    n = n - lp_fast(n, 900)
    return n * np.exp(-tt * 22) * 0.5


def hat(dur=0.06):
    tt = np.arange(int(SR * dur)) / SR
    n = rng.standard_normal(len(tt))
    return (n - lp_fast(n, 6000, 1)) * np.exp(-tt * 70) * 0.18


def boom(dur=1.6, gain=1.0):
    tt = np.arange(int(SR * dur)) / SR
    f = 32 + 70 * np.exp(-tt * 9)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 2.6)
    n = lp_fast(rng.standard_normal(len(tt)), 1500) * np.exp(-tt * 10) * 3
    return gain * (sub + n)


def whoosh(dur=0.6):
    tt = np.arange(int(SR * dur)) / SR
    n = rng.standard_normal(len(tt))
    shape = np.sin(np.pi * tt / dur) ** 2
    return (n - lp_fast(n, 400)) * shape * 0.12


def reverb(x, mix=0.3):
    out = x.copy()
    for d, g in [(0.037, 0.5), (0.053, 0.45), (0.079, 0.4), (0.113, 0.35), (0.161, 0.3), (0.229, 0.25)]:
        k = int(d * SR)
        y = np.zeros_like(x)
        y[k:] = x[:-k] * g
        for _ in range(4):
            y[k:] += y[:-k] * g * 0.6
        out += y * mix
    return out


L = np.zeros(N)
R = np.zeros(N)

# --- Vent (0 -> 6 s) ----------------------------------------------------------
wn = rng.standard_normal(N)
wind = lp_fast(wn, 500) * 6 * (0.6 + 0.4 * np.sin(2 * np.pi * 0.35 * t + 1))
wind *= env([0, 1.2, 4.0, 6.5, 7], [0, 0.35, 0.35, 0.05, 0])
L += wind
R += np.roll(wind, 900)

# --- Nappe + accords (2 -> 21,5 s) --------------------------------------------
# La m - Fa - Do - Sol, une mesure (2 s) par accord.
chords = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]
roots = [45, 41, 48, 43]
pad = np.zeros(N)
bass = np.zeros(N)
for bar in range(15):
    s, e = bar * 2.0, bar * 2.0 + 2.0
    m = (t >= s) & (t < e)
    tt = t[m]
    for k, n_ in enumerate(chords[bar % 4]):
        for det in (-0.12, 0.12):
            pad[m] += saw(note(n_ + 12) * 2 ** (det / 12), tt) / 6
    bass[m] = np.sin(2 * np.pi * note(roots[bar % 4] - 12) * tt)
pad = lp_fast(pad, 1800)
pad *= env([0, 2.0, 5.0, 11.0, 19.0, CUT_MUSIC - 0.02, CUT_MUSIC], [0, 0.0, 0.25, 0.4, 0.6, 0.6, 0])
bass *= env([0, 4.5, 5.0, 11.0, CUT_MUSIC - 0.02, CUT_MUSIC], [0, 0, 0.35, 0.5, 0.55, 0])
L += pad + bass
R += np.roll(pad, 300) + bass

# Arpège (11 -> 21,5 s), doubles-croches.
arp = np.zeros(N)
step = 0.125
for i in range(int((CUT_MUSIC - 11.0) / step)):
    st = 11.0 + i * step
    ch = chords[int(st // 2) % 4]
    f = note(ch[i % 3] + 24)
    tt = np.arange(int(SR * step)) / SR
    arp += at(np.sign(np.sin(2 * np.pi * f * tt)) * np.exp(-tt * 18) * 0.06, st)
arp = lp_fast(arp, 4000, 1)
L += arp * 0.8
R += np.roll(arp, 2400)

# --- Percussions --------------------------------------------------------------
drums = np.zeros(N)
b = 7.0
while b < CUT_MUSIC - 0.01:
    drums += at(kick(punch=0.9 if b < 11 else 1.0), b)
    if b >= 11.0 and int(round((b - 11.0) / 0.5)) % 2 == 1:
        drums += at(clap(), b)
    if b >= 11.0:
        drums += at(hat(), b + 0.25)
    if b >= 17.0:
        drums += at(kick(0.3, 0.7), b + 0.25)  # double kick pour la fin de montée
    b += 0.5
L += drums
R += drums

# Coups sourds + whoosh à chaque coupe.
for c in CUTS:
    hit = boom(1.2, 0.5 if c > 5 else 0.35)
    L += at(hit, c)
    R += at(hit, c)
    w = whoosh()
    L += at(w, c - 0.3)
    R += at(np.roll(w, 600), c - 0.3)

# Riser 17 -> 21,5 s.
rs = rng.standard_normal(N)
rs = (rs - lp_fast(rs, 300)) * env([0, 17, CUT_MUSIC - 0.02, CUT_MUSIC], [0, 0, 0.22, 0])
L += rs
R += np.roll(rs, 1200)

# --- Suspense : silence puis souffle inversé (21,5 -> 23 s) --------------------
sw = rng.standard_normal(N)
sw = lp_fast(sw, 2500) * 2 * env([0, CUT_MUSIC + 0.2, IMPACT - 0.02, IMPACT], [0, 0, 0.5, 0]) ** 2
L += sw
R += np.roll(sw, 500)

# --- Impact + accord final (23 -> 30 s) ----------------------------------------
imp = boom(4.0, 1.4)
L += at(imp, IMPACT)
R += at(imp, IMPACT)
fin = np.zeros(N)
m = t >= IMPACT
tt = t[m] - IMPACT
for n_ in [45, 57, 60, 64, 69]:
    for det in (-0.1, 0.1):
        fin[m] += saw(note(n_) * 2 ** (det / 12), tt) / 8
fin = lp_fast(fin, 2200) * env([0, IMPACT, IMPACT + 0.05, 27.5, DUR], [0, 0, 0.8, 0.45, 0])
fin = reverb(fin, 0.25)
L += fin
R += np.roll(fin, 400)

# Scintillements (cristaux) et tintements (pièces).
for i, st in enumerate(np.arange(IMPACT + 0.2, 29.0, 0.37)):
    f = note([88, 91, 95, 93, 100][i % 5])
    tt = np.arange(int(SR * 0.8)) / SR
    s = np.sin(2 * np.pi * f * tt) * np.exp(-tt * 6) * 0.05
    (L if i % 2 else R)[:] += at(s, st)
for st in [IMPACT + 0.35, IMPACT + 0.55, IMPACT + 0.8]:
    tt = np.arange(int(SR * 0.5)) / SR
    s = (np.sin(2 * np.pi * 3200 * tt) + 0.6 * np.sin(2 * np.pi * 4700 * tt)) * np.exp(-tt * 12) * 0.06
    L += at(s, st)
    R += at(s, st + 0.01)

# --- Mastering simple ------------------------------------------------------------
mix = np.stack([L, R], axis=1)
mix = np.tanh(mix * 1.1)  # limiteur doux
mix /= np.max(np.abs(mix)) / 0.89
mix[:int(0.01 * SR)] *= np.linspace(0, 1, int(0.01 * SR))[:, None]
pcm = (mix * 32767).astype("<i2")
with wave.open(sys.argv[1] if len(sys.argv) > 1 else "build/soundtrack.wav", "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
