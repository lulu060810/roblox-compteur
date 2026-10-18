"""Synthèse 100 % originale (donc libre de droits) de la musique et des SFX.

Usage : python3 synth_audio.py <out_dir> <duree_musique_s> <bpm> <sections>
  sections = "t0:niveau,t1:niveau,..." (niveau 0 = intro, 1 = build, 2 = full, 3 = outro)
"""
import sys, os, wave
import numpy as np

SR = 48000
rng = np.random.default_rng(7)


def write(path, x):
    x = np.asarray(x, np.float32)
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    peak = np.abs(x).max() or 1
    x = x / peak * 0.89
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def env(n, a, d, s=0.0, r=None):
    """Enveloppe ADSR simple (en échantillons)."""
    a = max(1, int(a * SR)); d = max(1, int(d * SR))
    e = np.full(n, s, np.float32)
    e[:a] = np.linspace(0, 1, a)[:n]
    if a < n:
        k = min(d, n - a)
        e[a:a + k] = np.linspace(1, s, d)[:k]
    if r:
        r = int(r * SR); e[-r:] *= np.linspace(1, 0, r)
    return e


def onepole_lp(x, fc):
    """Passe-bas 1 pôle, fc scalaire ou tableau (filtre balayé)."""
    fc = np.broadcast_to(np.asarray(fc, np.float32), x.shape)
    a = np.exp(-2 * np.pi * fc / SR)
    y = np.empty_like(x); z = 0.0
    for i in range(len(x)):
        z = (1 - a[i]) * x[i] + a[i] * z
        y[i] = z
    return y


def bandnoise(n, f0, f1, q=2):
    """Bruit filtré passe-bande balayé f0 -> f1 (via FFT par blocs)."""
    noise = rng.standard_normal(n).astype(np.float32)
    out = np.zeros(n, np.float32)
    blk = 2048; hop = 512
    win = np.hanning(blk).astype(np.float32)
    freqs = np.fft.rfftfreq(blk, 1 / SR)
    for i in range(0, n - blk, hop):
        t = i / max(1, n - blk)
        fc = f0 * (f1 / f0) ** t
        bw = fc / q
        g = np.exp(-0.5 * ((freqs - fc) / bw) ** 2)
        out[i:i + blk] += np.fft.irfft(np.fft.rfft(noise[i:i + blk] * win) * g) * win
    return out


# ---------------------------------------------------------------- SFX
def sfx_whoosh(d=0.55):
    n = int(d * SR)
    x = bandnoise(n, 400, 5000, q=1.5) * np.sin(np.linspace(0, np.pi, n)) ** 2
    pan = np.linspace(-0.6, 0.6, n)
    return np.stack([x * (1 - pan) / 2, x * (1 + pan) / 2], 1)


def sfx_impact(d=1.4):
    n = int(d * SR); t = np.arange(n) / SR
    f = 38 + 70 * np.exp(-t * 18)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 3.2)
    click = rng.standard_normal(n) * np.exp(-t * 90) * 0.35
    tail = onepole_lp(rng.standard_normal(n).astype(np.float32), 900) * np.exp(-t * 4) * 0.6
    return np.tanh(1.6 * (boom + click + tail))


def sfx_riser(d=1.6):
    n = int(d * SR); t = np.arange(n) / SR
    noise = bandnoise(n, 300, 7000, q=3) * (t / d) ** 2
    f = 180 * (2 ** (2.5 * t / d))
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * (t / d) ** 3 * 0.25
    x = noise + tone
    x[-int(0.02 * SR):] *= np.linspace(1, 0, int(0.02 * SR))
    return x


def sfx_pop(d=0.12):
    n = int(d * SR); t = np.arange(n) / SR
    f = 900 * np.exp(-t * 30) + 380
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 45)


def sfx_tick(d=0.05):
    n = int(d * SR); t = np.arange(n) / SR
    return onepole_lp(rng.standard_normal(n).astype(np.float32), 6000) * np.exp(-t * 160)


# ---------------------------------------------------------------- Musique
def note(m):
    return 440 * 2 ** ((m - 69) / 12)


def music(total, bpm, sections):
    n = int(total * SR)
    L = np.zeros(n, np.float32); R = np.zeros(n, np.float32)
    beat = 60 / bpm; bar = 4 * beat

    def level(t):
        lv = 0
        for t0, l in sections:
            if t >= t0:
                lv = l
        return lv

    # Progression : Am7 - Fmaj7 - C - G/B (moderne, légèrement mélancolique / motivante)
    chords = [[57, 60, 64, 67], [53, 57, 60, 64], [48, 55, 60, 64], [47, 55, 59, 62]]
    roots = [45, 41, 48, 43]
    nbars = int(total / bar) + 1

    for b in range(nbars):
        t0 = b * bar; i0 = int(t0 * SR)
        if i0 >= n:
            break
        lv = level(t0)
        ch = chords[b % 4]
        # Pad (toujours présent, doux)
        m = min(int(bar * SR) + int(0.5 * SR), n - i0)
        tt = np.arange(m) / SR
        e = env(m, 0.6, bar, 0.7, r=0.5)
        pad = np.zeros(m, np.float32)
        for k, nn in enumerate(ch):
            for det in (-0.08, 0.08):
                f = note(nn) * 2 ** (det / 12)
                pad += np.sin(2 * np.pi * f * tt + k) * 0.5 + 0.25 * np.sin(4 * np.pi * f * tt)
        pad = onepole_lp(pad * e, 1400 if lv >= 2 else 900) * 0.10
        L[i0:i0 + m] += pad * 0.9; R[i0:i0 + m] += pad

        # Pluck arpégé en croches (dès le niveau 1)
        if lv >= 1 and lv != 3 or (lv == 3 and b % 2 == 0):
            for s in range(8):
                ts = t0 + s * beat / 2; j = int(ts * SR)
                mm = min(int(0.35 * SR), n - j)
                if mm <= 0:
                    continue
                f = note(ch[[0, 2, 1, 3, 2, 1, 3, 2][s]] + 12)
                tp = np.arange(mm) / SR
                p = (np.sin(2 * np.pi * f * tp) + 0.3 * np.sin(6 * np.pi * f * tp)) * np.exp(-tp * 11)
                g = 0.06 if lv >= 2 else 0.045
                pan = 0.35 if s % 2 else -0.35
                L[j:j + mm] += p * g * (1 - pan); R[j:j + mm] += p * g * (1 + pan)

        if lv == 2:
            # Kick 1 et 3 (+ croche), sub-bass en blanches
            for s, vel in ((0, 1), (2, 1), (2.5, 0.6)):
                j = int((t0 + s * beat) * SR); mm = min(int(0.4 * SR), n - j)
                if mm <= 0:
                    continue
                tk = np.arange(mm) / SR
                k = np.sin(2 * np.pi * np.cumsum(45 + 90 * np.exp(-tk * 30)) / SR) * np.exp(-tk * 8)
                L[j:j + mm] += k * 0.22 * vel; R[j:j + mm] += k * 0.22 * vel
            for s in (0, 2):
                j = int((t0 + s * beat) * SR); mm = min(int(2 * beat * SR), n - j)
                if mm <= 0:
                    continue
                tb = np.arange(mm) / SR
                bs = np.sin(2 * np.pi * note(roots[b % 4] - 12) * tb) * env(mm, 0.01, 0.3, 0.6, r=0.05)
                L[j:j + mm] += bs * 0.12; R[j:j + mm] += bs * 0.12
            # Clap/snare léger temps 2 et 4
            for s in (1, 3):
                j = int((t0 + s * beat) * SR); mm = min(int(0.2 * SR), n - j)
                if mm <= 0:
                    continue
                tc = np.arange(mm) / SR
                c = rng.standard_normal(mm) * np.exp(-tc * 25)
                c = c - onepole_lp(c.astype(np.float32), 1200)
                L[j:j + mm] += c * 0.05; R[j:j + mm] += c * 0.05
        if lv >= 1 and lv != 3:
            # Hi-hats en double-croches (plus présents en full)
            for s in range(16):
                j = int((t0 + s * beat / 4) * SR); mm = min(int(0.05 * SR), n - j)
                if mm <= 0:
                    continue
                th = np.arange(mm) / SR
                h = rng.standard_normal(mm) * np.exp(-th * 120)
                g = (0.03 if s % 2 == 0 else 0.016) * (1 if lv == 2 else 0.6)
                pan = 0.3
                L[j:j + mm] += h * g * (1 - pan); R[j:j + mm] += h * g * (1 + pan)

    # Fade-in / fade-out
    fi = int(1.5 * SR); fo = int(2.5 * SR)
    L[:fi] *= np.linspace(0, 1, fi); R[:fi] *= np.linspace(0, 1, fi)
    L[-fo:] *= np.linspace(1, 0, fo); R[-fo:] *= np.linspace(1, 0, fo)
    x = np.stack([L, R], 1)
    return np.tanh(x * 1.4) / 1.4


if __name__ == "__main__":
    out, total, bpm = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    sections = [(float(a), int(b)) for a, b in (s.split(":") for s in sys.argv[4].split(","))]
    os.makedirs(out, exist_ok=True)
    write(f"{out}/whoosh.wav", sfx_whoosh())
    write(f"{out}/impact.wav", sfx_impact())
    write(f"{out}/riser.wav", sfx_riser())
    write(f"{out}/pop.wav", sfx_pop())
    write(f"{out}/tick.wav", sfx_tick())
    write(f"{out}/music.wav", music(total, bpm, sections))
    print("ok")
