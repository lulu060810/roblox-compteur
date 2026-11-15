// Rendu des images de la scène via WebGL2 (Chromium headless / SwiftShader)
// usage: node render.js <outDir> <width> <height> [start] [end] [step] [times...]
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const TL = require('./timeline.js');

const out = process.argv[2] || 'frames';
const W = +(process.argv[3] || 1080), H = +(process.argv[4] || 1920);
const start = +(process.argv[5] || 0), end = +(process.argv[6] || TL.FPS * 14), step = +(process.argv[7] || 1);
const extraTimes = process.argv.slice(8).map(Number);
fs.mkdirSync(out, { recursive: true });

const frag = fs.readFileSync(path.join(__dirname, 'scene.frag'), 'utf8');
const vert = `#version 300 es
in vec2 p; void main(){ gl_Position = vec4(p,0.,1.); }`;

(async () => {
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage();
  page.on('console', m => console.log('[page]', m.text()));
  await page.setContent(`<canvas id=c width=${W} height=${H}></canvas>`);
  const err = await page.evaluate(({ vert, frag }) => {
    const c = document.getElementById('c');
    const gl = c.getContext('webgl2', { preserveDrawingBuffer: true, antialias: false });
    const sh = (t, s) => { const o = gl.createShader(t); gl.shaderSource(o, s); gl.compileShader(o); if (!gl.getShaderParameter(o, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(o)); return o; };
    try {
      const pr = gl.createProgram();
      gl.attachShader(pr, sh(gl.VERTEX_SHADER, vert)); gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, frag));
      gl.linkProgram(pr); if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) return gl.getProgramInfoLog(pr);
      gl.useProgram(pr);
      const b = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, b);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
      const loc = gl.getAttribLocation(pr, 'p'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
      const U = n => gl.getUniformLocation(pr, n);
      window.draw = (s) => {
        gl.viewport(0, 0, c.width, c.height);
        gl.uniform2f(U('uRes'), c.width, c.height);
        gl.uniform1f(U('uTime'), s.t);
        gl.uniform3fv(U('uCamPos'), s.cam.pos); gl.uniform3fv(U('uCamTgt'), s.cam.tgt);
        gl.uniform1f(U('uFov'), s.cam.fov * Math.PI / 180); gl.uniform1f(U('uRoll'), s.cam.roll);
        gl.uniform1f(U('uFlash'), s.flash); gl.uniform1f(U('uBolt'), s.bolt);
        gl.uniform2fv(U('uBoltPts'), new Float32Array(s.boltPts.flat()));
        gl.uniform1f(U('uQ'), s.qmark); gl.uniform1f(U('uFog'), s.fog); gl.uniform1f(U('uExposure'), s.exposure);
        gl.uniform1f(U('uCarX'), s.carX); gl.uniform1f(U('uCarZ'), s.carZ); gl.uniform1f(U('uWheelAng'), s.wheelAng);
        gl.drawArrays(gl.TRIANGLES, 0, 3);
        gl.finish();
        return c.toDataURL('image/png');
      };
    } catch (e) { return String(e.message); }
    return null;
  }, { vert, frag });
  if (err) { console.error('SHADER ERROR\n' + err); process.exit(1); }

  const jobs = [];
  if (extraTimes.length) extraTimes.forEach(t => jobs.push({ t, name: `t_${t.toFixed(2)}.png` }));
  else for (let f = start; f < end; f += step) jobs.push({ t: f / TL.FPS, name: `f_${String(f).padStart(4, '0')}.png` });

  for (const j of jobs) {
    const file = path.join(out, j.name);
    if (fs.existsSync(file)) continue;
    const t0 = Date.now();
    const s = TL.frameState(j.t);
    let data;
    if (s.exposure <= 0.0005) {
      data = await page.evaluate(() => { const c = document.createElement('canvas'); c.width = document.getElementById('c').width; c.height = document.getElementById('c').height; const x = c.getContext('2d'); x.fillStyle = '#000'; x.fillRect(0, 0, c.width, c.height); return c.toDataURL('image/png'); });
    } else data = await page.evaluate(s => window.draw(s), s);
    fs.writeFileSync(file + '.tmp', Buffer.from(data.split(',')[1], 'base64'));
    fs.renameSync(file + '.tmp', file);
    console.log(j.name, s.shot, ((Date.now() - t0) / 1000).toFixed(2) + 's');
  }
  await browser.close();
})();
