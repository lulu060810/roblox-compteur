const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 540, height: 960 } });
  p.on('console', m => console.log('console', m.text())); p.on('pageerror', e => console.log('ERR', e.message));
  await p.goto('file://' + __dirname + '/scene.html?res=0.5&t=0.01'); await p.evaluate(() => window.ready);
  for (const t of process.argv.slice(2)) { await p.evaluate(t => render(t), +t); await p.screenshot({ path: process.env.OUT + '/s_' + t + '.png' }); }
  await b.close();
})();
