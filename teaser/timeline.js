// Timeline partagée (navigateur + Node) : caméra, voiture, éclairs, brume, néon.
(function (root) {
  const FPS = 30, DURATION = 18.0;
  const CAR_X = -3.3, CAR_SPEED = 6.5, CAR_Z0 = 2.0;

  const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
  const lerp = (a, b, t) => a + (b - a) * t;
  const smooth = (t) => { t = clamp(t, 0, 1); return t * t * (3 - 2 * t); };
  const ease = (t) => { t = clamp(t, 0, 1); return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; };
  const easeOut = (t) => { t = clamp(t, 0, 1); return 1 - Math.pow(1 - t, 3); };
  const v3 = (x, y, z) => [x, y, z];
  const mix3 = (a, b, t) => [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];

  // Éclairs : [temps, amplitude, éclair visible?, azimut, graine]
  const STRIKES = [
    [0.85, 1.00, 1, -0.30, 11],
    [2.95, 0.30, 0, 0.0, 0],
    [6.55, 1.35, 1, 0.22, 27],
    [9.12, 1.10, 0, 0.0, 0],
    [12.75, 0.55, 1, -0.10, 41],
  ];

  function flashAt(t) {
    let f = 0, bolt = 0, boltIdx = -1;
    for (let i = 0; i < STRIKES.length; i++) {
      const [t0, a, hasBolt] = STRIKES[i];
      const pulses = [[0, 1.0], [0.085, 0.65], [0.21, 0.45], [0.33, 0.18]];
      for (const [dt, pa] of pulses) {
        const x = t - (t0 + dt);
        if (x >= 0) f += a * pa * Math.exp(-x / 0.055);
      }
      // lueur résiduelle dans les nuages
      const x = t - t0;
      if (x >= 0) f += a * 0.06 * Math.exp(-x / 0.5);
      if (hasBolt && x >= 0 && x < 0.42) {
        const b = (x < 0.05 ? 1 : x < 0.085 ? 0.25 : x < 0.12 ? 0.9 : x < 0.21 ? 0.3 : x < 0.26 ? 0.7 : 0.15) * Math.exp(-x / 0.3);
        if (b > bolt) { bolt = b; boltIdx = i; }
      }
    }
    return { flash: f, bolt, boltIdx };
  }

  function carZ(t) { return CAR_Z0 + CAR_SPEED * t; }

  // Néon du point d'interrogation : allumage avec grésillements
  function qmarkAt(t) {
    const t0 = 10.35;
    if (t < t0) return 0;
    const seq = [[0, 0.06, 0.9], [0.06, 0.18, 0.0], [0.18, 0.23, 0.6], [0.23, 0.42, 0.0], [0.42, 0.47, 1.0],
                 [0.47, 0.52, 0.1], [0.52, 0.60, 0.8], [0.60, 0.66, 0.2], [0.66, 0.8, 1.0], [0.8, 0.83, 0.4]];
    const x = t - t0;
    for (const [a, b, v] of seq) if (x >= a && x < b) return v;
    const buzz = 0.94 + 0.06 * Math.sin(t * 97.0) * Math.sin(t * 13.0);
    return buzz * (1.0 + 0.25 * smooth((t - 12.8) / 1.2));
  }

  function shotAt(t) {
    if (t < 4.2) return 'A';
    if (t < 9.2) return 'B';
    if (t < 14.0) return 'C';
    return 'END';
  }

  function cameraAt(t) {
    const shot = shotAt(t);
    if (shot === 'A') {
      const s = t / 4.2;
      const e = ease(s);
      return { pos: mix3(v3(2.0, 14.5, -30), v3(0.6, 10.5, -14), e),
               tgt: mix3(v3(-0.6, 15.5, 140), v3(-1.6, 11.0, 140), e), fov: lerp(56, 52, s), roll: lerp(-0.015, 0.008, s) };
    }
    if (shot === 'B') {
      const s = (t - 4.2) / 5.0;
      const e = ease(s);
      const cz = carZ(t);
      // la caméra glisse le long de la voiture qui la dépasse doucement
      const pos = [CAR_X + lerp(2.6, 1.5, e), lerp(0.6, 1.5, e), cz + lerp(-3.4, -8.5, e)];
      const tgt = [CAR_X + lerp(-0.4, 0.2, e), lerp(1.7, 2.6, e), cz + 10.0];
      return { pos, tgt, fov: lerp(54, 50, s), roll: lerp(0.02, -0.01, s) };
    }
    if (shot === 'C') {
      const s = (t - 9.2) / 4.8;
      const e = ease(s), e2 = smooth(s);
      return { pos: v3(lerp(3.2, 0.0, ease(s)), lerp(1.4, 30.0, e), lerp(140, 166, easeOut(s))),
               tgt: v3(lerp(1.5, 0.0, s), lerp(9.0, 124.0, smooth(s * 1.35)), 260), fov: lerp(52, 46, s), roll: lerp(0.01, 0, s) };
    }
    return { pos: v3(0, 10, 0), tgt: v3(0, 10, 10), fov: 50, roll: 0 };
  }

  function exposureAt(t, flash) {
    if (t < 4.2) {
      const fade = smooth((t - 0.95) / 2.1);
      return Math.max(fade, Math.min(1, flash * 0.9));
    }
    if (t < 9.2) return Math.min(smooth((t - 4.2) / 0.25), 1.0);
    if (t < 14.0) return 1.0;
    return 0.0;
  }

  function fogAt(t) {
    if (t < 4.2) return lerp(0.55, 0.7, t / 4.2);
    if (t < 9.2) return lerp(0.6, 0.8, (t - 4.2) / 5);
    return lerp(0.85, 1.6, smooth((t - 9.2) / 4.8));
  }

  // Éclair : ligne brisée en coordonnées angulaires (azimut, élévation)
  function boltPoints(seed, az0) {
    let s = seed * 9301 + 49297;
    const rnd = () => { s = (s * 9301 + 49297) % 233280; return s / 233280; };
    const N = 24, pts = [];
    let az = az0, el = 0.95;
    for (let i = 0; i < N; i++) {
      pts.push([az, el]);
      el -= (0.95 - 0.12) / (N - 1) * (0.6 + 0.8 * rnd());
      az += (rnd() - 0.5) * 0.06;
      el = Math.max(el, 0.05);
    }
    return pts;
  }

  function frameState(t) {
    const cam = cameraAt(t);
    const fl = flashAt(t);
    const st = STRIKES[fl.boltIdx] || null;
    const cz = carZ(t);
    return {
      t, shot: shotAt(t), cam,
      flash: fl.flash, bolt: fl.bolt,
      boltPts: st ? boltPoints(st[4], st[3]) : boltPoints(1, 0),
      qmark: qmarkAt(t), fog: fogAt(t), exposure: exposureAt(t, fl.flash),
      carX: CAR_X, carZ: cz, wheelAng: cz / 0.36,
      carDist: Math.hypot(cam.pos[0] - CAR_X, cam.pos[1] - 0.7, cam.pos[2] - cz),
      carPan: clamp((CAR_X - cam.pos[0]) / 6, -1, 1),
    };
  }

  const api = { FPS, DURATION, STRIKES, frameState, flashAt, carZ };
  if (typeof module !== 'undefined') module.exports = api; else root.TL = api;
})(this);
