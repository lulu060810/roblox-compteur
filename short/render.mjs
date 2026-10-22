// Renders short.html frame by frame and pipes JPEGs into ffmpeg.
import { createRequire } from 'node:module';
const { chromium } = createRequire('/opt/node22/lib/node_modules/')('playwright');
import { spawn } from 'node:child_process';
import path from 'node:path';

const dir = path.dirname(new URL(import.meta.url).pathname);
const out = process.argv[2] || path.join(dir, 'video_noaudio.mp4');
const browser = await chromium.launch({ args: ['--allow-file-access-from-files'] });
const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
import fs from 'node:fs';
const timeline = JSON.parse(fs.readFileSync(path.join(dir, 'timeline.json'), 'utf8'));
await page.addInitScript(tl => { window.TIMELINE = tl; }, timeline);
await page.goto('file://' + path.join(dir, 'short.html'));
await page.evaluate(() => window.ready);
const total = await page.evaluate(() => window.TOTAL);

const ff = spawn('ffmpeg', ['-y', '-f', 'image2pipe', '-framerate', '30', '-i', '-',
  '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p', out], { stdio: ['pipe', 'ignore', 'inherit'] });
for (let f = 0; f < total; f++) {
  const url = await page.evaluate(f => window.renderFrame(f), f);
  if (!ff.stdin.write(Buffer.from(url.split(',')[1], 'base64'))) await new Promise(r => ff.stdin.once('drain', r));
}
ff.stdin.end();
await new Promise(r => ff.on('close', r));
await browser.close();
console.log('frames:', total);
