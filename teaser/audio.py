"""Bande-son 100 % synthétisée (aucun échantillon externe => aucun problème de droits).
Pluie, tonnerre, moteur, pneus mouillés, vent, musique sombre avec montée en tension, impact final.
usage: python3 audio.py car.json out.wav
"""
import json, sys
import numpy as np
from scipy import signal

SR = 48000
DUR = 18.0
N = int(SR * DUR)
rng = np.random.default_rng(7)
t = np.arange(N) / SR


def bp(x, lo, hi, order=4):
    sos = signal.butter(order, [lo, hi], btype='band', fs=SR, output='sos')
    return signal.sosfilt(sos, x)


def lp(x, f, order=4):
    return signal.sosfilt(signal.butter(order, f, btype='low', fs=SR, output='sos'), x)


def hp(x, f, order=4):
    return signal.sosfilt(signal.butter(order, f, btype='high', fs=SR, output='sos'), x)


def env(points):
    """enveloppe linéaire par morceaux [(temps, valeur), ...]"""
    ts, vs = zip(*points)
    return np.interp(t, ts, vs)


def noise():
    return rng.standard_normal(N)


def pink():
    w = np.fft.rfft(noise())
    f = np.fft.rfftfreq(N, 1 / SR)
    f[0] = 1
    return np.fft.irfft(w / np.sqrt(f), N) * 30


def brown():
    b = np.cumsum(noise())
    return hp(b, 15, 2) / 400


def reverb(x, secs=3.0, decay=3.0, mix=0.35, seed=1):
    r = np.random.default_rng(seed)
    n = int(SR * secs)
    tt = np.arange(n) / SR
    ir = r.standard_normal(n) * np.exp(-tt * decay)
    ir = lp(ir, 6000, 2)
    ir /= np.sqrt(np.sum(ir ** 2))
    y = signal.fftconvolve(x, ir)[: len(x)]
    return x * (1 - mix) + y * mix * 1.2


def place(buf, start, snd):
    i = int(start * SR)
    if i >= N:
        return
    n = min(len(snd), N - i)
    buf[i:i + n] += snd[:n]


L = np.zeros(N)
R = np.zeros(N)
CUT = 14.0
pre = (t < CUT).astype(float)

# ---------------------------------------------------------------- pluie
rainL = hp(lp(pink(), 9000), 250) * 0.9 + hp(noise(), 3000) * 0.05
rainR = hp(lp(pink(), 9000), 250) * 0.9 + hp(noise(), 3000) * 0.05
# gouttes / crépitements
drops = np.zeros(N)
idx = rng.integers(0, N, 9000)
drops[idx] = rng.standard_normal(9000) * rng.uniform(0.2, 1, 9000)
drops = bp(drops, 1500, 7000, 2) * 2.0
rain_env = env([(0, 0), (0.3, 0.0), (1.6, 0.55), (4.2, 0.55), (4.25, 0.75), (9.2, 0.75), (9.25, 0.6), (13.99, 0.65), (14.0, 0)])
L += (rainL + drops) * rain_env * 0.11
R += (rainR + np.roll(drops, 1234)) * rain_env * 0.11

# ---------------------------------------------------------------- tonnerre
def thunder(strength, crack=True, length=5.0, seed=0):
    r = np.random.default_rng(seed)
    n = int(SR * length)
    tt = np.arange(n) / SR
    out = np.zeros(n)
    if crack:
        c = r.standard_normal(n) * np.exp(-tt / 0.06)
        c = bp(c, 300, 5000, 2) * 1.4
        # claquements secondaires
        for k in range(5):
            d = r.uniform(0.02, 0.35)
            s = int(d * SR)
            seg = r.standard_normal(n - s) * np.exp(-np.arange(n - s) / SR / r.uniform(0.02, 0.08))
            out[s:] += bp(seg, 200, 4000, 2) * r.uniform(0.3, 0.8)
        out += c
    rum = np.cumsum(r.standard_normal(n))
    rum = lp(hp(rum, 20, 2), 180, 4)
    rum /= np.max(np.abs(rum)) + 1e-9
    am = np.zeros(n)
    for k in range(9):
        c0 = r.uniform(0.05, length * 0.6)
        am += r.uniform(0.3, 1.0) * np.exp(-np.maximum(tt - c0, 0) / r.uniform(0.4, 1.4)) * (tt > c0) * (1 - np.exp(-np.maximum(tt - c0, 0) / 0.05))
    am /= am.max()
    out += rum * am * 2.2
    out *= np.minimum(1, (length - tt) / 0.8)
    return reverb(out * strength, 3.5, 2.0, 0.4, seed + 3)

for (st, strength, crack, seed, pan) in [
        (0.05, 0.7, False, 1, 0.2),   # écran noir : grondement
        (0.93, 1.0, True, 2, -0.3),
        (3.55, 0.35, False, 3, 0.5),
        (6.62, 1.25, True, 4, 0.25),
        (9.18, 1.0, True, 5, -0.1),
        (13.15, 0.5, False, 6, 0.0)]:
    th = thunder(strength, crack, 5.5, seed)
    th_full = np.zeros(N)
    place(th_full, st, th)
    if st < CUT:
        th_full *= np.concatenate([np.ones(int(CUT * SR)), np.zeros(N - int(CUT * SR))])
    L += th_full * (1 - pan) * 0.5
    R += th_full * (1 + pan) * 0.5

# ---------------------------------------------------------------- moteur + pneus
car = json.load(open(sys.argv[1]))
ft = np.array([c['t'] for c in car])
cd = np.interp(t, ft, [c['dist'] for c in car])
cp = np.interp(t, ft, [c['pan'] for c in car])
gain = 1.0 / (1.0 + (cd / 5.0) ** 2)
f0 = 31 + 3 * np.sin(2 * np.pi * 0.3 * t)
ph = 2 * np.pi * np.cumsum(f0) / SR
eng = sum(a * np.sin(k * ph + rng.uniform(0, 6)) for k, a in [(1, 1.0), (2, 0.6), (3, 0.35), (4, 0.25), (6, 0.12)])
eng *= 1 + 0.3 * lp(noise(), 25, 2) * 8
eng = lp(eng, 400, 2)
hiss = bp(noise(), 600, 5000, 2) * (0.6 + 0.4 * lp(noise(), 3, 1) * 10)
carsnd = (eng * 0.35 + hiss * 0.25) * gain * pre
L += carsnd * (1 - cp * 0.6) * 0.8
R += carsnd * (1 + cp * 0.6) * 0.8

# ---------------------------------------------------------------- vent
w = noise()
wind = np.zeros(N)
blk = 4800
for i in range(0, N, blk):
    fc = 750 + 300 * np.sin(2 * np.pi * 0.11 * i / SR) + 150 * np.sin(2 * np.pi * 0.37 * i / SR)
    wind[i:i + blk] = bp(w[max(0, i - 2000):i + blk], fc * 0.8, fc * 1.25, 2)[-min(blk, N - i):]
wind = lp(wind, 2000, 2)
wenv = env([(0, 0.0), (1.0, 0.25), (9.2, 0.3), (13.9, 0.8), (14.0, 0.0)])
L += wind * wenv * 0.25
R += np.roll(wind, 3000) * wenv * 0.25

# ---------------------------------------------------------------- musique
def saw(freq, detune=0.0):
    ph = (np.cumsum(np.full(N, freq * (1 + detune))) / SR) % 1.0
    return 2 * ph - 1

D1 = 36.71
drone = lp(saw(D1) + saw(D1, 0.004) + 0.6 * saw(D1 * 2, -0.003) + 0.35 * saw(D1 * 3 * 1.0, 0.002), 160, 2)
drone += 0.5 * np.sin(2 * np.pi * D1 * t)
denv = env([(0, 0), (0.6, 0), (3.0, 0.5), (9.2, 0.6), (13.99, 0.9), (14.0, 0)])
music = drone * denv * 0.22

# nappe sombre (Ré mineur + seconde mineure qui monte en tension)
pad = np.zeros(N)
for f, a in [(146.83, 1), (174.61, 0.8), (220.0, 0.6), (155.56, 0.0)]:
    pad += a * (saw(f, 0.003) + saw(f, -0.004))
pad = lp(pad, 900, 2)
tension = (saw(155.56, 0.002) + saw(155.56, -0.003)) * env([(0, 0), (9.2, 0), (13.9, 0.7), (14, 0)])
pad = pad * env([(0, 0), (2.0, 0), (4.2, 0.12), (9.2, 0.2), (13.99, 0.35), (14, 0)]) + lp(tension, 1200, 2) * 0.35
music += reverb(pad, 3.0, 1.5, 0.5, 11) * 0.12

# pulsations (battements de cœur) qui accélèrent
def kick(freq=55, dur=0.7, drop=2.5):
    tt = np.arange(int(SR * dur)) / SR
    f = freq * (1 + drop * np.exp(-tt / 0.03))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / 0.22)

beats = np.zeros(N)
bt = 4.2
while bt < 13.95:
    progress = (bt - 4.2) / 9.8
    place(beats, bt, kick() * (0.6 + 0.4 * progress))
    place(beats, bt + 0.22, kick(50, 0.5) * 0.45 * (0.6 + 0.4 * progress))
    bt += 60 / (68 + 70 * progress ** 1.6)
music += beats * pre * 0.5

# braams (cuivres graves synthétiques)
def braam(dur=3.0):
    n = int(SR * dur)
    tt = np.arange(n) / SR
    x = np.zeros(n)
    for f, a in [(D1 * 2, 1.0), (D1 * 3, 0.5), (D1 * 4, 0.6), (D1 * 4.8, 0.3)]:
        ph = 2 * np.pi * np.cumsum(np.full(n, f) * (1 + 0.004 * np.sin(2 * np.pi * 5 * tt))) / SR
        x += a * signal.sawtooth(ph)
    cutoff_env = np.exp(-tt / 0.9)
    y = np.zeros(n)
    # filtre balayé grossier par blocs
    for i in range(0, n, 2400):
        fc = 200 + 1600 * cutoff_env[i]
        y[i:i + 2400] = lp(x[max(0, i - 4800):i + 2400], fc, 2)[-min(2400, n - i):]
    y *= np.minimum(1, tt / 0.04) * np.exp(-tt / 1.4)
    return np.tanh(y * 0.8)

br = np.zeros(N)
place(br, 4.2, braam())
place(br, 9.2, braam(3.5) * 1.1)
br *= pre
music += reverb(br, 3.0, 1.8, 0.4, 21) * 0.33

# montée (riser) 10.5 -> 14
rt = np.clip((t - 10.5) / 3.5, 0, 1)
riser = bp(noise(), 800, 9000, 2) * rt ** 2.2
f_r = 110 * 2 ** (rt * 2.2)
riser += 0.6 * signal.sawtooth(2 * np.pi * np.cumsum(f_r) / SR) * rt ** 2 * 0.4
riser = lp(riser, 9000, 2) * pre
music += riser * 0.18

# impact final à 14.0
def impact():
    n = int(SR * 4.0)
    tt = np.arange(n) / SR
    f = 30 + 60 * np.exp(-tt / 0.08)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / 1.3) * 1.3
    hit = bp(rng.standard_normal(n), 80, 6000, 2) * np.exp(-tt / 0.12) * 1.2
    low = lp(rng.standard_normal(n), 120, 2) * np.exp(-tt / 0.6) * 6
    return reverb(np.tanh((sub + hit + low) * 1.2), 4.0, 1.4, 0.45, 31)

imp = np.zeros(N)
place(imp, 14.0, impact())
music += imp * 0.95

# carte de fin : nappe grave + note cristalline
endpad = (np.sin(2 * np.pi * D1 * 2 * t) + 0.5 * np.sin(2 * np.pi * 110.0 * t) + 0.3 * np.sin(2 * np.pi * 146.83 * t))
endpad *= env([(0, 0), (14.2, 0), (15.2, 0.25), (16.6, 0.22), (18.0, 0)])
music += endpad * 0.18
ping = np.zeros(N)
pt = np.arange(int(SR * 3.5)) / SR
pn = (np.sin(2 * np.pi * 587.33 * pt) + 0.3 * np.sin(2 * np.pi * 1174.66 * pt) + 0.1 * np.sin(2 * np.pi * 1761.99 * pt)) * np.exp(-pt / 0.9) * np.minimum(1, pt / 0.005)
place(ping, 15.0, pn)
music += reverb(ping, 3.0, 1.5, 0.6, 41) * 0.07
# tonnerre lointain final
th = thunder(0.25, False, 3.0, 9)
tf = np.zeros(N)
place(tf, 15.4, th)
music += tf * env([(0, 1), (17.2, 1), (18, 0)])

L += music
R += music + np.roll(music, 600) * 0.0

# ---------------------------------------------------------------- master
st = np.stack([L, R], 1)
st = hp(st.T, 25, 2).T
fade = env([(0, 1), (17.4, 1), (18.0, 0)])
st *= fade[:, None]
peak = np.max(np.abs(st))
st = np.tanh(st / peak * 1.6) / np.tanh(1.6) * 0.89
from scipy.io import wavfile
wavfile.write(sys.argv[2], SR, (st * 32767).astype(np.int16))
print('ok peak', peak)
