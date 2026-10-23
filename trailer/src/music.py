"""Original 128 BPM track for the Mine to Get Rich trailer (synthesized, royalty-free)."""
import numpy as np
from scipy.signal import butter, sosfilt, fftconvolve
from scipy.io import wavfile
import sys

SR = 48000
BPM = 128
B = 60 / BPM
TOTAL_BEATS = 88
N = int((TOTAL_BEATS * B + 2.5) * SR)
rng = np.random.default_rng(7)

def buf():
    return np.zeros((N, 2))

def t_arr(d):
    return np.arange(int(d * SR)) / SR

def place(track, sig, at, gain=1.0, pan=0.0):
    i = int(at * SR)
    if i >= N:
        return
    if sig.ndim == 1:
        l = np.cos((pan + 1) * np.pi / 4); r = np.sin((pan + 1) * np.pi / 4)
        sig = np.stack([sig * l * 1.414, sig * r * 1.414], 1)
    n = min(len(sig), N - i)
    track[i:i + n] += sig[:n] * gain

def lp(x, fc, order=2):
    return sosfilt(butter(order, min(fc, SR / 2 - 100) / (SR / 2), 'low', output='sos'), x, axis=0)

def hp(x, fc, order=2):
    return sosfilt(butter(order, fc / (SR / 2), 'high', output='sos'), x, axis=0)

def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo / (SR / 2), hi / (SR / 2)], 'band', output='sos'), x, axis=0)

def saw(f, t, phase=0.0):
    p = (f * t + phase) % 1.0
    return 2 * p - 1

def note(n):  # midi -> hz
    return 440 * 2 ** ((n - 69) / 12)

def sweep_filter(x, f0, f1, kind='low', chunk=512):
    out = np.zeros_like(x)
    nch = int(np.ceil(len(x) / chunk))
    zi = None
    for c in range(nch):
        a = c / max(1, nch - 1)
        fc = f0 * (f1 / f0) ** a
        sos = butter(2, min(fc, SR / 2 - 200) / (SR / 2), kind, output='sos')
        seg = x[c * chunk:(c + 1) * chunk]
        if zi is None:
            zi = np.zeros((sos.shape[0], 2) + seg.shape[1:])
        y, zi = sosfilt(sos, seg, axis=0, zi=zi)
        out[c * chunk:(c + 1) * chunk] = y
    return out

def reverb(x, secs=2.2, wet=0.3, damp=4000):
    n = int(secs * SR)
    ir = rng.standard_normal((n, 2)) * np.exp(-np.linspace(0, 7, n))[:, None]
    ir = lp(ir, damp)
    ir /= np.sqrt((ir ** 2).sum(0))
    w = np.stack([fftconvolve(x[:, c], ir[:, c])[:len(x)] for c in range(2)], 1)
    return x * (1 - wet) + w * wet * 1.6

# ---------------- instruments ----------------
def kick(big=False):
    t = t_arr(0.55 if big else 0.4)
    f = 45 + 120 * np.exp(-t * 28)
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) * np.exp(-t * (5 if big else 7.5))
    s += 0.5 * np.exp(-t * 300) * rng.standard_normal(len(t)) * 0.4
    return np.tanh(s * 2.2) * 0.9

def clap():
    t = t_arr(0.35)
    n = rng.standard_normal(len(t))
    env = np.exp(-t * 18)
    for d in (0.0, 0.011, 0.022):
        env += 0.6 * np.exp(-np.maximum(t - d, 0) * 90) * (t >= d)
    s = bp(n, 900, 5000) * env * 0.7
    s += np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30) * 0.4
    return s

def hat(open_=False):
    t = t_arr(0.25 if open_ else 0.06)
    s = hp(rng.standard_normal(len(t)), 7000) * np.exp(-t * (14 if open_ else 70))
    return s * 0.35

def supersaw(freqs, dur, cutoff=5000, voices=7, detune=0.18):
    t = t_arr(dur)
    L = np.zeros(len(t)); R = np.zeros(len(t))
    for f in freqs:
        for v in range(voices):
            d = (v - (voices - 1) / 2) / ((voices - 1) / 2) * detune
            ff = f * 2 ** (d / 12)
            s = saw(ff, t, rng.random())
            if v % 2: L += s * (0.6 + 0.4 * (v / voices))
            else: R += s * (0.6 + 0.4 * (v / voices))
    s = np.stack([L, R], 1) / (voices * len(freqs)) * 1.6
    att = np.minimum(1, t / 0.01)[:, None]
    rel = np.minimum(1, (dur - t) / 0.05).clip(0)[:, None]
    return lp(s * att * rel, cutoff)

def pluck(f, dur=0.22, bright=6000):
    t = t_arr(dur)
    s = 0.6 * saw(f, t) + 0.4 * np.sign(np.sin(2 * np.pi * f * 2 * t))
    s *= np.exp(-t * 14)
    return lp(s, bright) * 0.5

def bass(f, dur):
    t = t_arr(dur)
    s = 0.7 * np.sin(2 * np.pi * f * t) + 0.35 * lp(saw(f * 2, t), 900)
    env = np.minimum(1, t / 0.005) * np.minimum(1, (dur - t) / 0.02).clip(0)
    return np.tanh(s * env * 1.5) * 0.6

def lead(f, dur):
    t = t_arr(dur)
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.5 * t) * np.minimum(1, t / 0.2)
    ph = np.cumsum(f * vib) / SR
    s = 0.5 * (2 * (ph % 1) - 1) + 0.5 * np.sign(np.sin(2 * np.pi * ph + 0.3))
    s += 0.3 * (2 * ((ph * 1.004) % 1) - 1)
    env = np.minimum(1, t / 0.01) * (0.75 + 0.25 * np.exp(-t * 6)) * np.minimum(1, (dur - t) / 0.03).clip(0)
    return lp(s * env, 4500) * 0.35

def riser(dur, f0=300, f1=9000):
    t = t_arr(dur)
    n = rng.standard_normal((len(t), 2))
    s = sweep_filter(n, f0, f1, 'low') * (t / dur)[:, None] ** 2
    tone = np.sin(2 * np.pi * np.cumsum(200 * 2 ** (3 * t / dur)) / SR) * (t / dur) ** 3 * 0.25
    return s * 0.5 + tone[:, None]

def impact(big=1.0):
    t = t_arr(3.0)
    f = 30 + 80 * np.exp(-t * 6)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 1.6)
    crash = hp(rng.standard_normal(len(t)), 2500) * np.exp(-t * 2.2) * 0.35
    noise = lp(rng.standard_normal(len(t)), 1200) * np.exp(-t * 5) * 0.6
    s = np.tanh((boom * 1.4 + noise) * 1.5) * 0.8 + crash
    return s * big

def whoosh(dur=0.45, up=True):
    t = t_arr(dur)
    n = rng.standard_normal((len(t), 2))
    f0, f1 = (500, 6000) if up else (6000, 400)
    env = np.sin(np.pi * t / dur) ** 2
    return sweep_filter(n, f0, f1, 'low') * env[:, None] * 0.55

def sparkle():
    t = t_arr(1.2)
    s = np.zeros(len(t))
    for i, n in enumerate([88, 93, 95, 100, 105]):
        d = i * 0.045
        tt = np.maximum(t - d, 0)
        s += np.sin(2 * np.pi * note(n) * tt) * np.exp(-tt * 6) * (t >= d)
    return s * 0.12

def reverse_cymbal(dur):
    t = t_arr(dur)
    s = hp(rng.standard_normal(len(t)), 4000) * (t / dur) ** 3
    return s * 0.4

def pad(freqs, dur):
    t = t_arr(dur)
    s = sum(np.sin(2 * np.pi * f * t + np.sin(2 * np.pi * 0.3 * t)) + 0.3 * saw(f * 1.003, t) for f in freqs)
    env = np.minimum(1, t / 0.6) * np.minimum(1, (dur - t) / 0.5).clip(0)
    return lp(s * env / len(freqs), 1800) * 0.4

# ---------------- arrangement ----------------
drums, music, fx, sc_src = buf(), buf(), buf(), []
CH = {'Am': ([57, 60, 64], 33), 'F': ([53, 57, 60], 29), 'C': ([55, 60, 64], 36), 'G': ([55, 59, 62], 31)}
PROG = ['Am', 'F', 'C', 'G']
bt = lambda b: b * B

def kick_at(b, big=False):
    place(drums, kick(big), bt(b), 1.0)
    sc_src.append(bt(b))

# Intro 0-8: dark drone, sparkle, riser, impact on 4, roll 6-8
place(music, pad([note(45), note(57), note(64)], bt(8)), 0, 0.9)
place(fx, sparkle(), 0.15, 1.0)
place(fx, riser(bt(4), 150, 5000), 0, 0.7)
place(fx, impact(1.0), bt(4), 1.0)
kick_at(4, big=True)
place(fx, sparkle(), bt(5), 1.3, 0.3)
for i in range(16):  # accelerating snare roll beats 6-8
    b = 6 + i * 0.125
    place(drums, clap(), bt(b), 0.25 + 0.5 * i / 16)
place(fx, riser(bt(2), 800, 12000), bt(6), 0.8)
place(fx, reverse_cymbal(bt(2)), bt(6), 1.0)
place(fx, whoosh(0.5), bt(8) - 0.42, 1.0)

def drop_section(b0, b1, with_lead=False):
    for b in range(b0, b1):
        kick_at(b, big=(b == b0))
        if b % 2 == 1:
            place(drums, clap(), bt(b), 0.7)
        place(drums, hat(True), bt(b + 0.5), 0.45, 0.2)
        for s in (0.25, 0.75):
            place(drums, hat(), bt(b + s), 0.35, -0.3)
    for bar in range((b1 - b0) // 4):
        b = b0 + bar * 4
        chord, root = CH[PROG[bar % 4]]
        place(music, supersaw([note(n) for n in chord] + [note(chord[0] + 12)], bt(4) - 0.02, 5500), bt(b), 0.55)
        for i in range(8):  # offbeat bass pattern
            place(music, bass(note(root), bt(0.45)), bt(b + i * 0.5), 0.9 if i % 2 else 0.7)
        arp = chord + [chord[0] + 12, chord[1] + 12, chord[2], chord[1], chord[0] + 12]
        for i in range(16):
            place(music, pluck(note(arp[i % len(arp)] + 12)), bt(b + i * 0.25), 0.32, 0.5 if i % 2 else -0.5)
    if with_lead:
        mel = [  # (beat offset, midi, length in beats) per 4 bars
            [(0, 76, .5), (.5, 76, .5), (1, 74, .5), (1.5, 72, .5), (2, 74, .5), (2.5, 76, 1), (3.5, 69, .5)],
            [(0, 72, .5), (.5, 72, .5), (1, 74, .5), (1.5, 76, 1), (2.5, 72, .5), (3, 69, 1)],
            [(0, 79, 1), (1, 76, 1), (2, 74, .5), (2.5, 72, .5), (3, 74, .5), (3.5, 76, .5)],
            [(0, 74, 1), (1, 71, 1), (2, 67, .5), (2.5, 69, .5), (3, 71, .5), (3.5, 74, .5)],
        ]
        for bar in range((b1 - b0) // 4):
            for (o, n, l) in mel[bar % 4]:
                place(music, lead(note(n), bt(l) - 0.01), bt(b0 + bar * 4 + o), 0.5, 0.1)

drop_section(8, 40)
place(fx, impact(0.9), bt(8), 1.0)

# Breakdown 40-48
place(fx, impact(0.9), bt(40), 1.0)
kick_at(40, big=True)
for bar, ch in enumerate(['F', 'G']):
    chord, root = CH[ch]
    place(music, pad([note(n) for n in chord] + [note(root + 12)], bt(4)), bt(40 + bar * 4), 1.4)
    for i in range(16):
        arp = chord + [chord[0] + 12]
        place(music, lp(pluck(note(arp[i % 4] + 12)), 1500 + bar * 2500 + i * 200), bt(40 + bar * 4 + i * 0.25), 0.35, 0.5 if i % 2 else -0.5)
for i in range(32):  # build: 8ths then 16ths
    b = 44 + (i * 0.25 if i < 16 else 4 + (i - 16) * 0.125 - 0)
    if b >= 48: break
    place(drums, clap(), bt(b), 0.2 + 0.6 * (b - 44) / 4)
for i in range(16):
    place(drums, kick(), bt(44 + i * 0.25), 0.25 + 0.3 * i / 16)
place(fx, riser(bt(4), 400, 14000), bt(44), 1.0)
place(fx, reverse_cymbal(bt(1)), bt(47), 1.0)

# Drop 2 48-72 with lead
drop_section(48, 72, with_lead=True)
place(fx, impact(1.0), bt(48), 1.0)

# Final 72-80: hit + halftime
place(fx, impact(1.1), bt(72), 1.0)
place(fx, whoosh(0.5), bt(72) - 0.42, 0.9)
for bar, ch in enumerate(['F', 'G']):
    chord, root = CH[ch]
    b = 72 + bar * 4
    place(music, supersaw([note(n) for n in chord] + [note(chord[0] + 12)], bt(4) - 0.02, 4000), bt(b), 0.5)
    place(music, bass(note(root), bt(3.9)), bt(b), 0.9)
    kick_at(b); kick_at(b + 2.5)
    place(drums, clap(), bt(b + 2), 0.8)
    for i in range(8):
        place(drums, hat(), bt(b + i * 0.5 + 0.25), 0.3)
for i in range(8):
    place(drums, clap(), bt(79 + i * 0.125), 0.3 + 0.4 * i / 8)
# End 80: final Am chord hit + tail
kick_at(80, big=True)
place(fx, impact(1.2), bt(80), 1.0)
place(music, supersaw([note(n) for n in [57, 60, 64, 69, 45]], 3.5, 3000) * np.exp(-t_arr(3.5) * 1.2)[:, None], bt(80), 0.7)
place(music, pad([note(45), note(57), note(64)], 4.0), bt(80), 1.2)
place(fx, sparkle(), bt(81), 1.4)

# Transition whooshes at cuts
for b in [12, 20, 28, 32, 36, 52, 56, 60, 64, 66, 68]:
    place(fx, whoosh(0.32), bt(b) - 0.26, 0.55, rng.uniform(-0.6, 0.6))
for b in range(22, 28):  # pickaxe card hits
    place(fx, sparkle(), bt(b), 0.7, (b - 25) * 0.25)

# ---------------- mix ----------------
sc = np.ones(N)
tt = np.arange(int(0.35 * SR)) / SR
shape = 1 - 0.75 * np.exp(-tt / 0.07)
for s in sc_src:
    i = int(s * SR); n = min(len(shape), N - i)
    sc[i:i + n] = np.minimum(sc[i:i + n], shape[:n])
music = reverb(music, 2.0, 0.22) * sc[:, None]
fx = reverb(fx, 2.8, 0.35)
drums = drums + reverb(hp(drums, 400), 1.2, 1.0) * 0.08
mix = drums * 0.85 + music * 0.9 + fx * 0.8
mix = hp(mix, 25)
mix = np.tanh(mix * 1.1) / np.tanh(1.1)
mix /= np.abs(mix).max() / 0.95
fade = int(0.8 * SR)
mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
wavfile.write(sys.argv[1], SR, (mix * 32767).astype(np.int16))
print('ok', len(mix) / SR)
