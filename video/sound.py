"""Procedural sound design for the UNITED GAMES x NOKSO teaser (10 s, 48 kHz stereo).
No voice, no sung music: sub-bass hits, whooshes, risers, electronic pulses, synced to scene.html."""
import sys
import wave
import numpy as np

SR = 48000
DUR = 10.0
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


# ---------------- timeline (matches scene.html) ----------------
add(sub_hit(1.2, 70, 30, 0.2, 0.6, 0), 0.0, gain=0.35)          # low rumble open
add(whoosh(0.55, 300, 6000), 0.05, pan=-0.6, gain=0.55)         # red line L->R
add(whoosh(0.35, 2000, 9000, 'hit'), 0.30, pan=0.7, gain=0.3)
add(whoosh(0.55, 400, 7000), 0.33, pan=0.6, gain=0.55)          # blue line R->L
add(whoosh(0.35, 2000, 9000, 'hit'), 0.62, pan=-0.7, gain=0.3)
for tb, f in [(0.86, 110), (1.21, 100), (1.56, 130)]:            # beats with shapes
    add(sub_hit(1.0, f, 40, 0.05, 0.38, 0.5), tb, gain=0.85)
    add(blip(f * 8, 0.12, 'sq'), tb + 0.01, pan=(-0.4 if f == 110 else 0.4), gain=0.18)
add(riser(0.45, 120, 1500), 1.62, gain=0.5)                       # push to camera
add(reverse_swell(0.4), 1.66, gain=0.6)
add(sub_hit(1.6, 140, 36, 0.06, 0.6, 0.6), 2.06, gain=1.0)       # cut impact
add(crack(0.4), 2.06, gain=0.5)
add(whoosh(0.8, 200, 5000, 'hit'), 2.05, pan=-0.8, gain=0.7)     # UNITED GAMES from left
add(whoosh(0.8, 300, 7000, 'hit'), 2.30, pan=0.8, gain=0.7)      # NOKSO from right
add(shimmer(1.0, 1320), 2.32, pan=0.6, gain=0.6)                  # NOKSO light animation
add(blip(660, 0.25, 'sine'), 2.9, pan=-0.5, gain=0.25)
add(blip(990, 0.25, 'sine'), 3.15, pan=0.5, gain=0.25)
add(reverse_swell(0.5), 2.92, gain=0.8)                           # build to the ×
add(sub_hit(2.6, 160, 32, 0.08, 0.95, 0.8), 3.42, gain=1.25)     # × BIG IMPACT
add(crack(0.7), 3.42, gain=0.8)
add(whoosh(1.2, 100, 3000, 'hit'), 3.42, gain=0.5)
add(shimmer(1.4, 660), 3.45, gain=0.5)

# rhythmic electronic pulse 3.9 -> 7.85 (120 bpm sub pulses + filtered pad + arp)
bpm_step = 0.25
k = 0
tp = 3.92
arp = [220, 330, 440, 330, 262, 392, 523, 392]
while tp < 7.8:
    if k % 2 == 0:
        add(sub_hit(0.35, 90, 45, 0.03, 0.12, 0.15), tp, gain=0.6)
    add(blip(arp[k % 8] * 2, 0.12, 'sq'), tp, pan=0.35 * np.sin(k), gain=0.07 + 0.05 * ((tp - 3.9) / 4))
    k += 1
    tp += bpm_step
p = pad(4.4, [55, 82.4, 110, 164.8], 900)
p *= np.minimum(1, tt(4.4) / 0.8) * np.minimum(1, (4.4 - tt(4.4)) / 0.3)
add(p, 3.55, gain=0.5)
add(glitch(0.3), 5.15, pan=-0.2, gain=0.35)                       # text 1
add(glitch(0.25), 5.35, pan=0.2, gain=0.3)
add(whoosh(0.4, 1000, 8000, 'hit'), 5.6, gain=0.25)
add(glitch(0.3), 6.45, pan=-0.2, gain=0.35)                       # text 2
add(sub_hit(0.8, 120, 45, 0.04, 0.3, 0.3), 6.75, gain=0.55)       # "DE NOKSO"
add(glitch(0.25), 6.75, pan=0.2, gain=0.3)
add(riser(0.35, 150, 2000), 7.82, gain=0.55)                       # transition
add(reverse_swell(0.32), 7.84, gain=0.7)
add(whoosh(0.5, 300, 9000, 'hit'), 7.9, gain=0.5)
add(sub_hit(1.6, 140, 34, 0.06, 0.6, 0.6), 8.16, gain=1.0)        # final cut
add(crack(0.4), 8.16, gain=0.45)
add(blip(1320, 0.12, 'sine'), 8.32, gain=0.25)
add(blip(880, 0.12, 'sine'), 8.56, pan=-0.3, gain=0.2)
add(blip(1100, 0.12, 'sine'), 8.71, pan=0.3, gain=0.2)
add(glitch(0.25), 8.95, gain=0.3)
add(shimmer(1.2, 880), 8.98, gain=0.55)
add(reverse_swell(0.4), 9.06, gain=0.7)
add(sub_hit(1.0, 150, 28, 0.09, 0.9, 0.9), 9.46, gain=1.35)        # final pulse, deep hit
add(crack(0.6), 9.46, gain=0.5)

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
st *= np.minimum(1, (DUR - t) / 0.12)[:, None]  # tiny tail fade at 10 s
st *= 0.93 / np.abs(st).max()
out = sys.argv[1] if len(sys.argv) > 1 else 'sound.wav'
with wave.open(out, 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((st * 32767).astype('<i2').tobytes())
print('wrote', out)
