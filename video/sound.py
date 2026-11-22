"""Procedural sound design for the UNITED GAMES x NOKSO teaser (10 s, 48 kHz stereo).
No voice, no sung music: sub-bass hits, whooshes, risers, electronic pulses, synced to scene.html."""
import sys
import wave
import numpy as np

SR = 48000
DUR = 19.0
N = int(SR * DUR)
L = np.zeros(N)
R = np.zeros(N)
rng = np.random.default_rng(42)


def add(sig, t0, pan=0.0, gain=1.0):
    i = int(t0 * SR)
    if i >= N:
        return
    sig = sig[: N - i] * gain
    L[i:i + len(sig)] += sig * np.sqrt((1 - pan) / 2)
    R[i:i + len(sig)] += sig * np.sqrt((1 + pan) / 2)


def tt(d):
    return np.arange(int(d * SR)) / SR


def lowpass(x, fc):
    """one-pole low-pass; fc may be an array (time-varying)."""
    fc = np.broadcast_to(np.asarray(fc, float), x.shape)
    a = np.exp(-2 * np.pi * fc / SR)
    y = np.empty_like(x)
    acc = 0.0
    for n in range(len(x)):
        acc = (1 - a[n]) * x[n] + a[n] * acc
        y[n] = acc
    return y


def bandnoise(d, f0, f1):
    t = tt(d)
    fc_lo = np.geomspace(f0, f1, len(t))
    n = rng.standard_normal(len(t))
    lp = lowpass(n, fc_lo * 1.8)
    hp = lp - lowpass(lp, fc_lo * 0.5)
    return hp / (np.abs(hp).max() + 1e-9)


def sub_hit(d=1.6, f_hi=120, f_lo=38, drop=0.06, decay=0.55, click=0.35):
    t = tt(d)
    f = f_lo + (f_hi - f_lo) * np.exp(-t / drop)
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) * np.exp(-t / decay)
    s = np.tanh(s * 1.8) / np.tanh(1.8)
    c = rng.standard_normal(len(t)) * np.exp(-t / 0.006) * click
    return s + lowpass(c, 4000)


def whoosh(d, f0, f1, shape='swell'):
    t = tt(d)
    x = bandnoise(d, f0, f1)
    if shape == 'swell':
        env = np.sin(np.pi * np.clip(t / d, 0, 1)) ** 1.5
    else:  # fast attack, release
        env = (1 - np.exp(-t / 0.02)) * np.exp(-t / (d * 0.35))
    return x * env


def riser(d, f0=80, f1=900):
    t = tt(d)
    f = np.geomspace(f0, f1, len(t))
    ph = 2 * np.pi * np.cumsum(f) / SR
    tone = (np.sin(ph) + 0.5 * np.sin(ph * 1.503)) * 0.5
    nz = bandnoise(d, 400, 9000)
    env = (t / d) ** 2.2
    return (tone * 0.6 + nz * 0.7) * env


def reverse_swell(d=0.45):
    t = tt(d)
    x = bandnoise(d, 300, 6000)
    return x * (t / d) ** 3


def blip(f, d=0.07, kind='sq'):
    t = tt(d)
    if kind == 'sq':
        w = np.sign(np.sin(2 * np.pi * f * t)) * 0.5
    else:
        w = np.sin(2 * np.pi * f * t)
    return lowpass(w, 6000) * np.exp(-t / (d * 0.35))


def glitch(d=0.3):
    out = np.zeros(int(d * SR))
    pos = 0
    while pos < len(out) - 2000:
        seg = blip(rng.choice([800, 1200, 1600, 2400, 3200]), rng.uniform(0.015, 0.04))
        out[pos:pos + len(seg)] += seg * rng.uniform(0.4, 1)
        pos += int(rng.uniform(0.02, 0.05) * SR)
    return out


def crack(d=0.5):
    t = tt(d)
    n = rng.standard_normal(len(t))
    hp = n - lowpass(n, 1500)
    return np.tanh(3 * hp * np.exp(-t / 0.05)) * 0.6


def shimmer(d=1.0, base=880):
    t = tt(d)
    s = sum(np.sin(2 * np.pi * base * m * t + m) / (i + 1) for i, m in enumerate([1, 1.5, 2, 3]))
    trem = 0.6 + 0.4 * np.sin(2 * np.pi * 14 * t)
    return s * trem * (1 - np.exp(-t / 0.05)) * np.exp(-t / (d * 0.4)) * 0.25


def pad(d, notes, cutoff):
    t = tt(d)
    s = np.zeros(len(t))
    for f in notes:
        for det in (-0.12, 0.0, 0.11):
            fr = f * 2 ** (det / 12)
            s += 2 * ((t * fr) % 1) - 1
    s /= len(notes) * 3
    return lowpass(s, cutoff)


# ---------------- timeline (matches T in scene.html) ----------------
# ambient drone for the whole piece
dr = pad(DUR, [41.2, 61.7, 82.4], 260)
dr *= np.minimum(1, tt(DUR) / 2.5) * np.minimum(1, (DUR - tt(DUR)) / 1.0)
add(dr, 0.0, gain=0.55)
add(sub_hit(2.5, 60, 28, 0.4, 1.2, 0), 0.2, gain=0.4)           # opening rumble
add(whoosh(1.5, 200, 5000), 0.65, pan=-0.6, gain=0.5)          # red light line L->R
add(shimmer(1.4, 1760), 0.9, pan=-0.3, gain=0.25)
add(whoosh(1.5, 300, 6000), 1.45, pan=0.6, gain=0.5)           # blue line R->L
add(shimmer(1.4, 1320), 1.7, pan=0.3, gain=0.25)
for tb, f, pn in [(3.1, 100, -0.3), (3.7, 95, 0.3), (4.3, 120, 0.0)]:   # rings on bass hits
    add(sub_hit(1.6, f, 36, 0.06, 0.6, 0.45), tb, gain=0.9)
    add(blip(f * 8, 0.3, 'sine'), tb + 0.01, pan=pn, gain=0.14)
add(riser(0.5, 120, 1600), 4.5, gain=0.5)                       # collapse to centre
add(reverse_swell(0.55), 4.45, gain=0.7)
add(sub_hit(2.4, 140, 32, 0.07, 0.9, 0.6), 5.0, gain=1.1)       # flash / reveal
add(crack(0.5), 5.0, gain=0.4)
add(whoosh(1.4, 150, 4000), 4.95, pan=-0.8, gain=0.65)         # UNITED GAMES from left
add(whoosh(1.4, 200, 6000), 5.35, pan=0.8, gain=0.65)          # NOKSO from right
add(shimmer(1.6, 1320), 5.6, pan=0.6, gain=0.45)               # NOKSO light rings
add(shimmer(1.0, 990), 6.55, pan=-0.4, gain=0.3)               # light sweeps
add(shimmer(1.0, 1180), 6.95, pan=0.4, gain=0.3)
add(reverse_swell(0.7), 7.2, gain=0.85)                         # build to the ×
add(sub_hit(3.2, 160, 30, 0.09, 1.2, 0.8), 7.9, gain=1.3)       # × BIG IMPACT
add(crack(0.8), 7.9, gain=0.7)
add(whoosh(1.6, 100, 2500, 'hit'), 7.9, gain=0.45)
add(shimmer(2.0, 660), 7.95, gain=0.45)

# rhythmic electronic pulse 8.6 -> 14.1 (~100 bpm)
step = 0.3
k = 0
tp = 8.6
arp = [220, 330, 440, 330, 262, 392, 523, 392]
while tp < 14.1:
    ramp = min(1, (tp - 8.6) / 1.5)
    if k % 2 == 0:
        add(sub_hit(0.5, 90, 42, 0.03, 0.16, 0.12), tp, gain=0.6 * ramp)
    add(blip(arp[k % 8] * 2, 0.16, 'sq'), tp, pan=0.4 * np.sin(k), gain=(0.05 + 0.05 * (tp - 8.6) / 5.5) * ramp)
    k += 1
    tp += step
pd = pad(5.8, [55, 82.4, 110, 164.8], 1000)
pd *= np.minimum(1, tt(5.8) / 1.2) * np.minimum(1, (5.8 - tt(5.8)) / 0.4)
add(pd, 8.3, gain=0.45)
add(whoosh(0.7, 800, 7000), 9.35, gain=0.3)                     # text 1 in
add(blip(1320, 0.3, 'sine'), 9.45, gain=0.15)
add(whoosh(0.5, 800, 5000), 11.45, gain=0.22)                   # text 1 out
add(whoosh(0.7, 800, 7000), 11.8, gain=0.3)                     # text 2 in
add(sub_hit(1.0, 120, 42, 0.04, 0.35, 0.3), 12.2, gain=0.6)     # "DE NOKSO"
add(whoosh(0.5, 800, 5000), 13.95, gain=0.22)
add(riser(0.7, 150, 2200), 13.85, gain=0.55)                    # light wipe
add(whoosh(0.9, 300, 9000), 14.05, pan=-0.5, gain=0.6)
add(sub_hit(2.4, 140, 32, 0.07, 0.9, 0.5), 14.75, gain=1.0)     # final screen
add(shimmer(1.4, 880), 15.3, gain=0.35)                         # title
add(blip(880, 0.25, 'sine'), 15.9, pan=-0.3, gain=0.18)
add(blip(1100, 0.25, 'sine'), 16.2, pan=0.3, gain=0.16)
add(whoosh(1.4, 300, 5000), 16.7, gain=0.35)                    # BIENTÔT focus pull
add(shimmer(1.8, 660), 16.85, gain=0.4)
add(reverse_swell(0.8), 17.1, gain=0.8)
add(sub_hit(3.0, 150, 26, 0.1, 1.3, 0.8), 17.9, gain=1.4)       # final pulse, deep hit
add(crack(0.7), 17.9, gain=0.45)

# ---------------- mix: reverb, glue, limit ----------------
def reverb(x, d=1.6, mix=0.22):
    ir = rng.standard_normal(int(d * SR)) * np.exp(-tt(d) / (d * 0.25))
    ir = lowpass(ir, 5000)
    ir /= np.sqrt((ir ** 2).sum())
    n = len(x) + len(ir)
    y = np.fft.irfft(np.fft.rfft(x, n) * np.fft.rfft(ir, n), n)[: len(x)]
    return x + mix * y


L, R = reverb(L), reverb(R)
st = np.stack([L, R], 1)
st /= np.abs(st).max()
st = np.tanh(st * 1.4) / np.tanh(1.4)          # soft-clip glue
t = np.arange(N) / SR
st *= np.minimum(1, (DUR - t) / 0.5)[:, None]  # tail fade
st *= 0.93 / np.abs(st).max()
out = sys.argv[1] if len(sys.argv) > 1 else 'sound.wav'
with wave.open(out, 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((st * 32767).astype('<i2').tobytes())
print('wrote', out)
