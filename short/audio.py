# Synthesised sound design: 128 BPM beat + whooshes, impacts, click, chime, riser.
import numpy as np, wave, sys
SR = 44100; DUR = 11.5; N = int(SR * DUR)
rng = np.random.default_rng(1)
mix = np.zeros((N, 2))
t_all = np.arange(N) / SR

def add(sig, at, gain=1.0, pan=0.0):
    i = int(at * SR); sig = sig[:max(0, N - i)]
    l, r = np.sqrt((1 - pan) / 2), np.sqrt((1 + pan) / 2)
    mix[i:i + len(sig), 0] += sig * gain * l * 1.41
    mix[i:i + len(sig), 1] += sig * gain * r * 1.41

def lp(x, a):  # one-pole lowpass, a in (0,1)
    y = np.empty_like(x); acc = 0.0
    for i, v in enumerate(x): acc += a * (v - acc); y[i] = acc
    return y

def kick(d=.45):
    t = np.arange(int(d * SR)) / SR
    f = 45 + 110 * np.exp(-t * 28)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7) + .3 * np.exp(-t * 300) * rng.standard_normal(len(t))

def hat(d=.06):
    t = np.arange(int(d * SR)) / SR; n = rng.standard_normal(len(t))
    return (n - lp(n, .5)) * np.exp(-t * 70)

def clap():
    t = np.arange(int(.25 * SR)) / SR; n = rng.standard_normal(len(t))
    env = sum(np.exp(-np.clip(t - o, 0, None) * 60) * (t >= o) for o in (0, .012, .024))
    return (n - lp(n, .15)) * env * .6

def whoosh(d=.5, rev=False):
    t = np.arange(int(d * SR)) / SR; n = rng.standard_normal(len(t))
    sweep = np.linspace(.02, .45, len(t)); y = np.empty_like(n); acc = 0.0
    for i, v in enumerate(n): acc += sweep[i] * (v - acc); y[i] = acc
    env = np.sin(np.pi * t / d) ** 2
    y = y * env
    return y[::-1] if rev else y

def impact(d=1.4):
    t = np.arange(int(d * SR)) / SR
    boom = np.sin(2 * np.pi * np.cumsum(30 + 90 * np.exp(-t * 12)) / SR) * np.exp(-t * 3)
    n = rng.standard_normal(len(t)); crack = lp(n, .3) * np.exp(-t * 18)
    return boom + .8 * crack

def riser(d=1.2):
    t = np.arange(int(d * SR)) / SR
    f = 200 * (2 ** (t / d * 3))
    tone = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * .15
    n = rng.standard_normal(len(t)) * .4
    return (tone + n - lp(n, .2)) * (t / d) ** 2

def chime():
    t = np.arange(int(1.2 * SR)) / SR; y = np.zeros_like(t)
    for k, (f, o) in enumerate([(1318.5, 0), (1760, .07), (2637, .14)]):
        tt = np.clip(t - o, 0, None)
        y += (t >= o) * np.sin(2 * np.pi * f * tt) * np.exp(-tt * 4) * .5
    return y

def click():
    t = np.arange(int(.05 * SR)) / SR
    return np.sin(2 * np.pi * 2200 * t) * np.exp(-t * 200) + rng.standard_normal(len(t)) * np.exp(-t * 400) * .5

# --- beat: starts on the "VIDÉO" slam ---
beat = 60 / 128; start = .78
bass_notes = [55, 55, 65.4, 49]  # A1 A1 C2 G1 per bar
b = 0
while start + b * beat < 11.2:
    at = start + b * beat
    if not (8.9 < at < 9.15):  # drop-out before the final section
        add(kick(), at, .9)
        add(hat(), at + beat / 2, .25, .3)
        if b % 2 == 1: add(clap(), at, .5, -.1)
        f = bass_notes[(b // 4) % 4]
        tt = np.arange(int(beat * SR)) / SR
        add(np.tanh(2.5 * np.sin(2 * np.pi * f * tt)) * np.exp(-tt * 3) * .5, at, .55)
    b += 1

# --- FX hits synced to the picture ---
add(whoosh(.3), 0.0, .6, -.5)
add(whoosh(.5), .1, .7, -.6)            # NOUVELLE slides in
add(whoosh(.4, rev=True), .4, .6, .2)  # VIDÉO falls
add(impact(), .78, 1.1)
add(riser(.5), 1.7, .6); add(whoosh(.35), 1.95, .8)
add(impact(1.0), 2.2, .7)
for i in range(10): add(click() * .5, 2.27 + i * .04, .35, (i - 5) / 6)  # letter pops
add(whoosh(.6), 2.6, .6, .4)            # card flip-in
add(impact(.6), 3.75, .45); add(whoosh(.3, rev=True), 3.75, .5)  # play button blows away
add(chime() * .4, 3.8, .5, .3)          # shine sweep
for i in range(8): add(click(), 3.7 + i * .08, .35, (i - 4) / 5)  # title words
add(whoosh(.3), 4.4, .5, -.3)           # channel pill
for i in range(9): add(click(), 4.6 + i * .055, .2)  # typed channel name
# from here on everything runs 1 s later (SHIFT in short.html)
S = 1.0
add(whoosh(.45), 4.65 + S, .9, .5)
add(impact(.8), 5.05 + S, .6)
add(whoosh(.35, rev=True), 5.3 + S, .6)
add(whoosh(.5), 6.15 + S, .3, .7)       # cursor
add(click(), 6.8 + S, 1.2); add(impact(.9), 6.8 + S, .7); add(chime(), 6.85 + S, .9)
for i in range(6): add(chime() * np.exp(-i * .4) * .5, 7.0 + S + i * .12, .5, (-1) ** i * .5)  # bell
add(riser(1.0), 7.15 + S, .8)
add(whoosh(.35), 7.95 + S, .8)
add(impact(1.5), 8.45 + S, 1.3)
add(whoosh(.5, rev=True), 8.75 + S, .5)

# master: fade out, soft clip, normalise
mix *= np.clip((DUR - t_all) / .4, 0, 1)[:, None]
mix = np.tanh(mix * .9); mix /= np.abs(mix).max() / .89
pcm = (mix * 32767).astype('<i2')
with wave.open(sys.argv[1], 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
