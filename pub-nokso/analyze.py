import wave, sys, numpy as np
w = wave.open(sys.argv[1]); sr = w.getframerate()
x = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, 2).mean(1) / 32768
hop, win = 512, 2048
n = (len(x) - win) // hop
frames = np.lib.stride_tricks.as_strided(x, (n, win), (x.strides[0] * hop, x.strides[0]))
spec = np.abs(np.fft.rfft(frames * np.hanning(win), axis=1))
freqs = np.fft.rfftfreq(win, 1 / sr)
low = spec[:, freqs < 150].sum(1)
flux = np.maximum(0, np.diff(np.log1p(spec * 10), axis=0)).sum(1)
fps = sr / hop
# BPM via autocorrelation de l'onset
o = flux - flux.mean()
ac = np.correlate(o, o, 'full')[len(o) - 1:]
lags = np.arange(len(ac)) / fps
bpm_c = [(60 / l, ac[i]) for i, l in enumerate(lags) if 0.3 < l < 0.75]
bpm = max(bpm_c, key=lambda p: p[1])[0]
print("BPM ~", round(bpm, 2))
# énergie par seconde
rms = np.sqrt((frames ** 2).mean(1)); sec = (np.arange(n) / fps).astype(int)
E = np.bincount(sec, rms) / np.bincount(sec); L = np.bincount(sec, low) / np.bincount(sec)
L = L / L.max()
print("sec: rms low")
print(" ".join(f"{i}:{E[i]:.2f}/{L[i]:.2f}" for i in range(len(E))))
np.save("src/flux.npy", flux); np.save("src/low.npy", low)
print("fps", fps)
