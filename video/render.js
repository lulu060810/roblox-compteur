// usage: node render.js <outdir> [workers] [res] [fps]
const { chromium } = require('playwright'); const { spawn } = require('child_process');
const out = process.argv[2], WK = +(process.argv[3] || 4), RES = +(process.argv[4] || 2), FPS = +(process.argv[5] || 60);
const N = 10 * FPS, W = 1080 * RES, H = 1920 * RES;
(async () => {
  const b = await chromium.launch();
  const chunk = Math.ceil(N / WK), t0 = Date.now();
  await Promise.all([...Array(WK)].map(async (_, w) => {
    const p = await b.newPage({ viewport: { width: W, height: H } });
    p.on('pageerror', e => console.log('ERR', e.message));
    await p.goto('file://' + __dirname + `/scene.html?res=${RES}&t=0`); await p.evaluate(() => window.ready);
    const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'png', '-i', '-',
      '-c:v', 'libx264', '-preset', 'medium', '-crf', '14', '-pix_fmt', 'yuv420p', '-r', String(FPS), `${out}/seg${w}.mp4`], { stdio: ['pipe', 'inherit', 'inherit'] });
    for (let f = w * chunk; f < Math.min(N, (w + 1) * chunk); f++) {
      await p.evaluate(t => render(t), f / FPS);
      const buf = await p.screenshot({ type: 'png' });
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      if (f % 30 === 0) console.log(`w${w} f${f} ${((Date.now() - t0) / 1000).toFixed(0)}s`);
    }
    ff.stdin.end(); await new Promise(r => ff.on('close', r));
  }));
  await b.close();
})();
