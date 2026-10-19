"""Synthétise une piste phonk gaming de 20 s (120 BPM) calée sur le montage.

Aucune boucle externe : tout est généré ici, donc libre de droits.
Usage : python3 music.py out.wav
"""
import sys
import wave

import numpy as np

SR = 44100
DUR = 20.0
BPM = 120
BEAT = 60 / BPM
S16 = BEAT / 4
N = int(SR * DUR)
rng = np.random.default_rng(7)


def env(n, decay, attack=0.002):
    t = np.arange(n) / SR
    a = np.clip(t / attack, 0, 1)
    return a * np.exp(-t / decay)


def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc = (1 - a) * v + a * acc
        y[i] = acc
    return y


def add(buf, sig, t, gain=1.0):
    i = int(t * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[: j - i] * gain


def kick():
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    f = 45 + 110 * np.exp(-t / 0.03)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.tanh(2.2 * np.sin(ph) * env(n, 0.18))


def bass808(freq, length=0.9, glide_from=None):
    n = int(length * SR)
    t = np.arange(n) / SR
    f = np.full(n, freq)
    if glide_from:
        f = freq + (glide_from - freq) * np.exp(-t / 0.06)
    ph = 2 * np.pi * np.cumsum(f) / SR
    e = env(n, 0.45) * np.clip((length - t) / 0.05, 0, 1)
    return np.tanh(3.0 * np.sin(ph) * e) * 0.8


_noise_cache = {}


def noise(n, key):
    if key not in _noise_cache:
        _noise_cache[key] = rng.standard_normal(int(2 * SR))
    return _noise_cache[key][:n].copy()


def snare():
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    nz = noise(n, "sn")
    nz = nz - lowpass(nz, 1200)
    tone = np.sin(2 * np.pi * 190 * t) * env(n, 0.05)
    return (nz * env(n, 0.09) * 0.7 + tone * 0.6) * 0.9


def hat(open_=False):
    n = int((0.25 if open_ else 0.06) * SR)
    nz = noise(n, "hat")
    nz = nz - lowpass(nz, 7000)
    return nz * env(n, 0.12 if open_ else 0.018) * 0.5


def cowbell(freq, length=0.28):
    n = int(length * SR)
    t = np.arange(n) / SR
    sq = np.sign(np.sin(2 * np.pi * freq * t)) + np.sign(np.sin(2 * np.pi * freq * 1.48 * t))
    sq = lowpass(sq, 3500)
    sq = sq - lowpass(sq, 400)
    return np.tanh(1.5 * sq * env(n, 0.09)) * 0.35


def ding():
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    a = np.sin(2 * np.pi * 1318 * t) * env(n, 0.12)
    b = np.zeros(n)
    k = int(0.09 * SR)
    b[k:] = (np.sin(2 * np.pi * 1760 * t[: n - k]) * env(n - k, 0.2))
    return (a + b) * 0.35


def whoosh(length, up=True):
    n = int(length * SR)
    t = np.arange(n) / SR
    nz = noise(n, "wh")
    out = np.zeros(n)
    # balayage de filtre par blocs
    blocks = 40
    for bi in range(blocks):
        s, e = bi * n // blocks, (bi + 1) * n // blocks
        p = bi / blocks if up else 1 - bi / blocks
        cut = 300 + 9000 * p ** 2
        out[s:e] = lowpass(nz[s:e], cut)
    shape = (t / length) ** 2 if up else np.exp(-t / (length / 3))
    return out * shape * 0.9


def impact():
    n = int(1.6 * SR)
    t = np.arange(n) / SR
    f = 32 + 80 * np.exp(-t / 0.08)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.6)
    nz = lowpass(noise(n, "imp"), 2500) * env(n, 0.25) * 0.6
    return np.tanh(2.5 * (boom + nz)) * 0.9


def shimmer():
    n = int(1.4 * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for i, f in enumerate([2093, 2637, 3136, 4186]):
        k = int(i * 0.06 * SR)
        out[k:] += np.sin(2 * np.pi * f * t[: n - k]) * env(n - k, 0.4) * 0.18
    return out


def main(path):
    drums = np.zeros(N)
    bass = np.zeros(N)
    melo = np.zeros(N)
    fx = np.zeros(N)

    # Fa# mineur : notes de la mélodie cowbell (Hz de base) sur 2 mesures de 16 doubles-croches
    F = {"F#": 370, "A": 440, "C#": 554, "E": 330, "D": 294, "G#": 415, "B": 494}
    melody = ["F#", None, "F#", None, "A", None, "F#", "C#",
              None, "C#", "B", None, "A", None, "G#", None,
              "F#", None, "F#", None, "A", None, "C#", None,
              "E", None, "D", None, "C#", None, "B", "A"]
    bassline = [(0, 46.2), (6, 46.2), (10, 55.0), (16, 46.2), (22, 41.2), (26, 36.7)]  # (pas, Hz)

    def in_break(t):
        return 16.0 <= t < 17.0

    steps = int(DUR / S16)
    for s in range(steps):
        t = s * S16
        if t >= 19.5 or in_break(t):
            continue
        bar_step = s % 16
        two_bar = s % 32
        drop = t >= 17.0
        # kick
        if bar_step in (0, 6, 10) or (drop and bar_step == 14):
            add(drums, kick(), t, 0.9)
        # snare/clap sur 2 et 4
        if bar_step in (4, 12):
            add(drums, snare(), t, 0.8)
        # hats en doubles-croches + rolls
        if t >= 0.5:
            add(drums, hat(open_=(bar_step == 14)), t, 0.35 if bar_step % 2 else 0.55)
            if (12.0 <= t < 13.0 or 15.0 <= t < 16.0) and bar_step % 2 == 0:
                add(drums, hat(), t + S16 / 2, 0.3)
        # 808
        for st, fr in bassline:
            if two_bar == st:
                add(bass, bass808(fr * (1 if not drop else 1), 0.7 if st != 26 else 0.5,
                                  glide_from=fr * 1.5 if st in (10, 26) else None), t, 1.0)
        # cowbell
        note = melody[two_bar]
        if note and t >= 3.0:
            add(melo, cowbell(F[note] * 2), t, 1.0 if not drop else 1.15)

    # FX calés sur le montage
    add(fx, ding(), 0.0, 1.0)
    add(fx, impact(), 0.0, 0.6)
    add(fx, impact(), 1.5, 0.35)
    add(fx, whoosh(0.5), 2.5, 0.5)
    add(fx, impact(), 3.0, 0.55)       # logo
    add(fx, whoosh(0.5), 6.5, 0.5)
    add(fx, impact(), 7.0, 0.4)        # barre de progression
    add(fx, ding(), 7.5, 0.5)
    add(fx, ding(), 8.7, 0.5)
    add(fx, ding(), 9.9, 0.6)
    add(fx, whoosh(0.6), 10.4, 0.5)
    add(fx, shimmer(), 11.0, 1.0)      # carte cadeau
    add(fx, impact(), 11.0, 0.5)
    add(fx, whoosh(0.5), 12.5, 0.5)
    for tt in (13.0, 14.3, 15.6):
        add(fx, impact(), tt, 0.35)
    add(fx, whoosh(1.0), 16.0, 1.0)    # montée avant le drop
    add(fx, impact(), 17.0, 1.0)       # bass drop
    add(bass, bass808(36.7, 1.6, glide_from=73.4), 17.0, 1.1)
    add(fx, impact(), 19.5, 0.6)
    add(bass, bass808(46.2, 0.5), 19.5, 0.9)

    mix = drums * 0.8 + bass * 0.9 + melo * 0.9 + fx * 0.8
    mix = np.tanh(mix * 1.1)
    fade = np.ones(N)
    k = int(0.12 * SR)
    fade[-k:] = np.linspace(1, 0, k)
    mix = mix * fade / max(1e-9, np.abs(mix).max()) * 0.93
    pcm = (mix * 32767).astype(np.int16)
    stereo = np.repeat(pcm[:, None], 2, axis=1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(stereo.tobytes())


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "music.wav")
