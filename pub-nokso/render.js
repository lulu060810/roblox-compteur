// Rend render.html image par image et encode la vidéo avec la musique.
// Usage : node render.js [sortie.mp4]   |   node render.js --stills t1,t2,...
const { chromium } = require("/opt/node22/lib/node_modules/playwright");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const FPS = 30, DUR = 20;
(async () => {
  const args = process.argv.slice(2);
  const browser = await chromium.launch({ args: ["--allow-file-access-from-files"] });
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  page.on("console", m => console.log("[page]", m.text()));
  page.on("pageerror", e => console.error("[page error]", e));
  await page.goto("file://" + path.join(__dirname, "render.html"));
  await page.evaluate(() => window.ready);
  const grab = t => page.evaluate(t => { renderFrame(t); return document.getElementById("c").toDataURL("image/jpeg", 0.93); }, t)
    .then(u => Buffer.from(u.split(",")[1], "base64"));

  if (args[0] === "--stills") {
    fs.mkdirSync(path.join(__dirname, "stills"), { recursive: true });
    for (const t of args[1].split(",").map(Number)) fs.writeFileSync(path.join(__dirname, "stills", `t${t.toFixed(2)}.jpg`), await grab(t));
  } else {
    const out = args[0] || "nokso_army_pub.mp4";
    const ff = spawn("ffmpeg", ["-y", "-f", "image2pipe", "-framerate", String(FPS), "-c:v", "mjpeg", "-i", "-",
      "-i", path.join(__dirname, "build_music.wav"), "-c:v", "libx264", "-preset", "medium", "-crf", "17",
      "-pix_fmt", "yuv420p", "-r", String(FPS), "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out],
      { stdio: ["pipe", "inherit", "inherit"] });
    for (let f = 0; f < FPS * DUR; f++) {
      const buf = await grab(f / FPS);
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once("drain", r));
    }
    ff.stdin.end();
    await new Promise(r => ff.on("close", r));
  }
  await browser.close();
})();
