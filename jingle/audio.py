"""Sound design du jingle MANCHE 1 (5 s, 48 kHz stéréo) - tout est synthétisé."""
import os
import sys
import wave

import numpy as np
from scipy import signal

SR = 48000
DUR = 5.0
N = int(SR * DUR)
t = np.arange(N) / SR
rng = np.random.default_rng(7)
FINAL = os.environ.get("THEME") == "final"  # boss final : plus grave, tambours de guerre, cloche


def env_adsr(start, attack, hold, release, curve=3.0):
    e = np.zeros(N)
    a0, a1 = int(start * SR), int((start + attack) * SR)
    h1 = int((start + attack + hold) * SR)
    r1 = int((start + attack + hold + release) * SR)
    a1, h1, r1 = min(a1, N), min(h1, N), min(r1, N)
    if a1 > a0:
        e[a0:a1] = np.linspace(0, 1, a1 - a0) ** 2
    e[a1:h1] = 1
    if r1 > h1:
        e[h1:r1] = np.exp(-curve * np.linspace(0, 1, r1 - h1)) * (1 - np.linspace(0, 1, r1 - h1))
    return e


def sweep_filter(x, f_start, f_end, start, dur, q=1.5, block=256):
    """Passe-bande dont la fréquence centrale glisse (filtrage par blocs)."""
    out = np.zeros_like(x)
    a, b = int(start * SR), min(int((start + dur) * SR), N)
    zi = None
    for i in range(a, b, block):
        j = min(i + block, b)
        p = (i - a) / max(1, b - a)
        fc = f_start * (f_end / f_start) ** p
        bw = fc / q
        lo, hi = max(20, fc - bw / 2), min(SR / 2 - 100, fc + bw / 2)
        sos = signal.butter(2, [lo, hi], btype="band", fs=SR, output="sos")
        if zi is None:
            zi = np.zeros((sos.shape[0], 2))
        out[i:j], zi = signal.sosfilt(sos, x[i:j], zi=zi)
    return out


def phase_of(freq):
    return 2 * np.pi * np.cumsum(freq) / SR


def saw(phase):
    return 2 * ((phase / (2 * np.pi)) % 1.0) - 1


def lp(x, fc, order=4):
    return signal.sosfilt(signal.butter(order, fc, fs=SR, output="sos"), x)


def hp(x, fc, order=4):
    return signal.sosfilt(signal.butter(order, fc, btype="high", fs=SR, output="sos"), x)


def bp(x, lo, hi, order=2):
    return signal.sosfilt(signal.butter(order, [lo, hi], btype="band", fs=SR, output="sos"), x)


def reverb(x, seconds=1.6, decay=4.0, seed=3):
    r = np.random.default_rng(seed)
    n = int(seconds * SR)
    ir = r.standard_normal(n) * np.exp(-decay * np.linspace(0, 1, n) * 3)
    ir = lp(ir, 6000, 2)
    ir /= np.sqrt(np.sum(ir ** 2))
    return signal.fftconvolve(x, ir)[: len(x)]


L = np.zeros(N)
R = np.zeros(N)


def add(x, gain=1.0, pan=0.0):
    """pan -1 (gauche) .. +1 (droite), loi à puissance constante."""
    global L, R
    ang = (pan + 1) * np.pi / 4
    L += x * gain * np.cos(ang)
    R += x * gain * np.sin(ang)


def add_pan_sweep(x, gain, pan_from, pan_to):
    global L, R
    pan = np.linspace(pan_from, pan_to, N)
    ang = (pan + 1) * np.pi / 4
    L += x * gain * np.cos(ang)
    R += x * gain * np.sin(ang)


# 1. Drone inquiétant qui monte (0 -> 2 s), puis nappe grave jusqu'à 4.7 s
f = np.where(t < 2.0, 42 * (72 / 42) ** np.clip(t / 2.0, 0, 1), 41.2) * (0.75 if FINAL else 1.0)
drone = sum(saw(phase_of(f * k * (1 + d))) for k, d in [(1, 0), (1, 0.007), (2, -0.004), (1.5, 0.003)])
drone = lp(drone, 900, 4)
denv = np.where(t < 2.0, np.clip(t / 1.95, 0, 1) ** 1.6, 0)
denv += np.where(t >= 2.0, 0.45 * np.exp(-(t - 2.0) * 0.6), 0) * (t < 4.75)
denv = lp(denv, 40, 1)
add(np.tanh(drone * 1.4) * denv, 0.22)

# 2. Riser bruité qui accompagne l'avancée du monstre (0.9 -> 2.0 s)
noise = rng.standard_normal(N)
riser = sweep_filter(noise, 350, 5500, 0.9, 1.1, q=2.0)
renv = np.clip((t - 0.9) / 1.1, 0, 1) ** 2.5 * (t < 2.0)
add(riser * renv, 0.55)

# 3. Whooshes (zoom d'entrée + bond du monstre + avancée finale)
for start, dur, f0, f1, g, p0, p1 in [
    (0.0, 0.7, 2600, 260, 0.9, -0.7, 0.4),
    (0.96, 0.45, 3200, 300, 0.9, 0.6, -0.4),
    (1.72, 0.3, 600, 4200, 0.6, 0.0, 0.0),
]:
    w = sweep_filter(rng.standard_normal(N), f0, f1, start, dur, q=1.2)
    e = np.zeros(N)
    a, b = int(start * SR), min(int((start + dur) * SR), N)
    x = np.linspace(0, 1, b - a)
    e[a:b] = np.sin(np.pi * x ** 0.55) ** 2
    add_pan_sweep(w * e, g, p0, p1)

# 4. Battements de coeur sourds pendant l'ouverture
for s in (0.32, 0.52, 0.80, 0.98):
    k = int(s * SR)
    n = int(0.25 * SR)
    tt = np.arange(n) / SR
    thump = np.sin(2 * np.pi * (55 * tt + 40 * (1 - np.exp(-tt * 30)) / 30)) * np.exp(-tt * 18)
    x = np.zeros(N)
    x[k:k + n] = thump[: N - k]
    add(x, 0.55)

# 5. "Shing" lumineux quand les yeux s'allument (0.35 s)
k = int(0.35 * SR)
tt = t[k:] - 0.35
shing = sum(np.sin(2 * np.pi * fr * tt + i) for i, fr in enumerate([1760, 2217, 2637, 3520]))
shing *= np.exp(-tt * 3.5) * (1 - np.exp(-tt * 80))
x = np.zeros(N)
x[k:] = shing
add(x, 0.05, -0.15)
add(x, 0.05, 0.15)

# 6. Glitches numériques (synchro avec l'image)
GLITCHES = [(1.00, 0.10), (1.24, 0.05), (1.47, 0.12), (1.66, 0.04), (1.86, 0.10), (2.02, 0.06), (4.62, 0.08)]
for s, d in GLITCHES:
    a, b = int(s * SR), int((s + d) * SR)
    seg = rng.standard_normal(b - a)
    hold = rng.integers(6, 40)
    seg = np.repeat(seg[::hold], hold)[: b - a]  # sample & hold = bitcrush
    seg = np.sign(seg) * 0.6 + 0.4 * np.sin(2 * np.pi * rng.uniform(200, 1400) * np.arange(b - a) / SR)
    seg *= np.where(np.sin(2 * np.pi * rng.uniform(25, 60) * np.arange(b - a) / SR) > 0, 1, 0.2)
    x = np.zeros(N)
    x[a:b] = seg * np.hanning(b - a) ** 0.3
    add(hp(x, 300), 0.16, rng.uniform(-0.6, 0.6))

# 7. IMPACT grave "MANCHE 1" (2.0 s)
k = int(2.0 * SR)
tt = t[k:] - 2.0
sub_f = 32 + 95 * np.exp(-tt * 9)
sub = np.sin(phase_of(sub_f)) * np.exp(-tt * 2.2)
sub = np.tanh(sub * 2.2)
crack = hp(rng.standard_normal(len(tt)), 1500) * np.exp(-tt * 45)
boom = bp(rng.standard_normal(len(tt)), 60, 900) * np.exp(-tt * 6)
imp = np.zeros(N)
imp[k:] = sub * 1.0 + crack * 0.45 + boom * 0.9
add(imp, 0.95)
rev_send = imp * 0.6

# 8. Rire monstrueux stylisé (HA-HA-HA-HA)
def laugh_syllable(dur, f0_start, f0_end):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    f0 = np.linspace(f0_start, f0_end, n) * (1 + 0.04 * np.sin(2 * np.pi * 7 * tt))
    src = saw(phase_of(f0)) * 0.7 + saw(phase_of(f0 / 2)) * 0.5  # sous-octave = monstrueux
    src += rng.standard_normal(n) * 0.25
    out = np.zeros(n)
    for fc, bw, g in [(720, 110, 1.0), (1120, 140, 0.7), (2550, 220, 0.35), (380, 90, 0.5)]:
        out += bp(src, fc - bw / 2, fc + bw / 2) * g
    h = hp(rng.standard_normal(n), 1200) * np.exp(-tt * 60) * 0.6  # le "h" d'attaque
    e = np.minimum(1, tt / 0.025) * np.exp(-np.maximum(0, tt - 0.05) * 9)
    return np.tanh((out * 3 + h) * e * 1.8)


laugh = np.zeros(N)
for s, f0a, f0b in [(2.72, 150, 138), (2.94, 140, 126), (3.16, 128, 112), (3.40, 116, 92)]:
    k = 0.72 if FINAL else 1.0  # rire plus grave pour le boss
    syl = laugh_syllable(0.22, f0a * k, f0b * k)
    a = int(s * SR)
    laugh[a:a + len(syl)] += syl
laugh = laugh + 0.35 * np.roll(laugh, int(0.012 * SR))  # léger doublage
add(laugh, 0.30, -0.1)
add(np.roll(laugh, int(0.009 * SR)), 0.20, 0.25)
rev_send = rev_send + laugh * 0.7

# 9. Pulse du titre (4.2 s)
k = int(4.2 * SR)
tt = t[k:] - 4.2
pulse = np.sin(phase_of(45 + 60 * np.exp(-tt * 14))) * np.exp(-tt * 5)
pulse += bp(rng.standard_normal(len(tt)), 100, 1500) * np.exp(-tt * 14) * 0.6
x = np.zeros(N)
x[k:] = np.tanh(pulse * 1.6)
add(x, 0.55)
rev_send = rev_send + x * 0.4

# 10. Transition gaming : reverse riser + sweep montant + "zap" final
a = int(4.45 * SR)
tt = t[a:] - 4.45
rev_cym = hp(rng.standard_normal(len(tt)), 4000) * (tt / tt[-1]) ** 3
swp = np.sin(phase_of(220 * (14) ** (tt / tt[-1]))) * (tt / tt[-1]) ** 2
x = np.zeros(N)
x[a:] = rev_cym * 0.6 + swp * 0.25
add(x, 0.6)
w = sweep_filter(rng.standard_normal(N), 400, 7000, 4.6, 0.4, q=1.2)
e = np.clip((t - 4.6) / 0.4, 0, 1) ** 1.5
add_pan_sweep(w * e, 0.8, -0.8, 0.8)

# Thème final : cloche funèbre + tambours de guerre + sub renforcé
if FINAL:
    def bell(start, f0, gain):
        k = int(start * SR)
        tt = t[k:] - start
        partials = [(0.5, 1.0, 1.2), (1.0, 0.8, 1.6), (1.19, 0.5, 2.2), (1.56, 0.45, 2.6),
                    (2.0, 0.35, 3.0), (2.74, 0.25, 4.0), (3.76, 0.15, 5.0)]
        b = sum(a * np.sin(2 * np.pi * f0 * r * tt) * np.exp(-tt * d) for r, a, d in partials)
        x = np.zeros(N)
        x[k:] = b * (1 - np.exp(-tt * 300))
        return x
    for s0 in (0.05, 2.0):
        bl = bell(s0, 196, 1)
        add(bl, 0.12, -0.2)
        add(bl, 0.12, 0.2)
        rev_send = rev_send + bl * 0.5

    def taiko(start, gain, f0=70):
        k = int(start * SR)
        n = min(int(0.6 * SR), N - k)
        tt = np.arange(n) / SR
        body = np.sin(2 * np.pi * (f0 * tt + 60 * (1 - np.exp(-tt * 25)) / 25)) * np.exp(-tt * 7)
        skin = bp(rng.standard_normal(n), 150, 1200) * np.exp(-tt * 30) * 0.5
        x = np.zeros(N)
        x[k:k + n] = np.tanh((body + skin) * 1.8)
        return x * gain

    for s0, g in [(0.30, 0.5), (0.55, 0.5), (0.80, 0.6), (1.00, 0.9), (1.25, 0.6), (1.47, 0.8),
                  (1.62, 0.6), (1.75, 0.7), (1.83, 0.75), (1.91, 0.8), (2.0, 1.0),
                  (4.2, 0.9), (4.45, 0.6), (4.6, 0.7)]:
        dr = taiko(s0, g)
        add(dr, 0.5, rng.uniform(-0.3, 0.3))
        rev_send = rev_send + dr * 0.3
    k = int(2.0 * SR)
    tt = t[k:] - 2.0
    x = np.zeros(N)
    x[k:] = np.sin(phase_of(28 + 40 * np.exp(-tt * 6))) * np.exp(-tt * 1.6)
    add(np.tanh(x * 2), 0.5)

# Réverbération globale
wet = reverb(rev_send, 1.8, 2.5)
add(wet, 0.35, -0.3)
add(np.roll(wet, 331), 0.35, 0.3)

# Master : limiteur doux, -1 dBFS, micro-fondu final
mix = np.stack([L, R], axis=1)
mix = np.tanh(mix * 1.3) / np.tanh(1.3)
mix /= np.max(np.abs(mix)) / 10 ** (-1 / 20)
fade = int(0.012 * SR)
mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
mix[:64] *= np.linspace(0, 1, 64)[:, None]

out_path = sys.argv[1] if len(sys.argv) > 1 else "manche1.wav"
with wave.open(out_path, "wb") as wf:
    wf.setnchannels(2)
    wf.setsampwidth(2)
    wf.setframerate(SR)
    wf.writeframes((mix * 32767).astype("<i2").tobytes())
print("audio ->", out_path)
