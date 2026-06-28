const path = require('path');
const fs = require('fs');
const puppeteer = require('puppeteer-core');
const { PuppeteerScreenRecorder } = require('puppeteer-screen-recorder');
const ffmpegPath = require('@ffmpeg-installer/ffmpeg').path;

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const BASE = 'http://localhost:8899';
const OUT = path.resolve(__dirname, '..'); // marketing/
const sleep = ms => new Promise(r => setTimeout(r, ms));

const jobs = [
  { file: 'promo-3d-30s.html',   out: 'promo-3d-30s.mp4',   w: 1080, h: 1920, mode: 'promo' },
  { file: 'promo-3d.html',       out: 'promo-3d.mp4',       w: 1080, h: 1920, mode: 'promo' },
  { file: 'promo-vertical.html', out: 'promo-vertical.mp4', w: 1080, h: 1920, mode: 'promo' },
  { file: 'promo-video.html',    out: 'promo-video.mp4',    w: 1920, h: 1080, mode: 'promo' },
  { file: 'explainer.html?auto=1', out: 'explainer-silent.mp4', w: 1080, h: 1920, mode: 'explainer' },
];

(async () => {
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: CHROME,
    args: ['--no-sandbox', '--autoplay-policy=no-user-gesture-required', '--disable-gpu-vsync', '--force-device-scale-factor=1'],
  });
  for (const j of jobs) {
    const outPath = path.join(OUT, j.out);
    console.log(`\n=== ${j.file} -> ${j.out} (${j.w}x${j.h}) ===`);
    const page = await browser.newPage();
    await page.setViewport({ width: j.w, height: j.h, deviceScaleFactor: 1 });
    try {
      await page.goto(`${BASE}/${j.file}`, { waitUntil: 'networkidle2', timeout: 60000 });
      await page.evaluate(() => (document.fonts ? document.fonts.ready : null)).catch(() => {});
      await sleep(1000); // settle fonts/first paint

      const recorder = new PuppeteerScreenRecorder(page, {
        fps: 30,
        ffmpeg_Path: ffmpegPath,
        videoFrame: { width: j.w, height: j.h },
        videoCrf: 20,
        videoCodec: 'libx264',
        videoPreset: 'medium',
        videoBitrate: 6000,
        autopad: { color: '#080a16' },
      });
      await recorder.start(outPath);

      if (j.mode === 'promo') {
        const total = await page.evaluate(() =>
          [...document.querySelectorAll('.scene')].reduce((a, s) => a + (parseInt(s.getAttribute('data-dur'), 10) || 0), 0)
        );
        // clean restart at scene 0, then capture exactly one loop
        await page.evaluate(() => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'r', bubbles: true })));
        const cap = total + 400;
        console.log(`  capturing ~${Math.round(cap / 1000)}s (one loop)`);
        await sleep(cap);
      } else {
        // explainer (?auto=1) auto-plays on timers; poll for end state
        console.log('  capturing explainer until it finishes...');
        const startT = Date.now();
        while (Date.now() - startT < 220000) {
          const done = await page.evaluate(() => {
            const c = document.getElementById('scenechip');
            const p = document.getElementById('sprog');
            return (p && p.style.width === '100%') || (c && /That/.test(c.textContent));
          });
          if (done) break;
          await sleep(1000);
        }
        await sleep(2000);
      }

      await recorder.stop();
      const kb = Math.round(fs.statSync(outPath).size / 1024);
      console.log(`  ✓ wrote ${j.out} (${kb} KB)`);
    } catch (e) {
      console.log(`  ✗ FAILED ${j.file}: ${e.message}`);
    } finally {
      await page.close().catch(() => {});
    }
  }
  await browser.close();
  console.log('\nAll done.');
})().catch(e => { console.error('FATAL', e); process.exit(1); });
