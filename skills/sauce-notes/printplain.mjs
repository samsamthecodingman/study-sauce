// Print a plain HTML file (the thumb-tab overlay pages, no MathJax) to PDF via Chrome DevTools Protocol.
// usage: node printplain.mjs <chrome> <in.html> <out.pdf>
// Heap limit for the renderer: env SN_HEAP_MB (default 768).
import { spawn } from 'node:child_process';
import { writeFileSync, mkdtempSync, readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

const [chrome, input, output] = process.argv.slice(2);
const port = 9300 + Math.floor(Math.random() * 500);
const prof = mkdtempSync(join(tmpdir(), 'sn-cdp-'));
const die = (c, m) => { if (m) console.error(m); try { proc.kill(); } catch {} process.exit(c); };
process.on('uncaughtException', e => die(4, 'uncaught: ' + e));
process.on('unhandledRejection', e => die(4, 'unhandled: ' + e));
const proc = spawn(chrome, ['--headless', '--no-sandbox', '--disable-gpu', '--disable-extensions', '--renderer-process-limit=1', '--disable-dev-shm-usage', '--no-zygote', `--js-flags=--max-old-space-size=${process.env.SN_HEAP_MB || 768}`,
  `--remote-debugging-port=${port}`, `--user-data-dir=${prof}`, 'about:blank'], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));

let targets;
for (let i = 0; i < 50; i++) {
  try { targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); break; } catch { await sleep(200); }
}
const page = targets.find(t => t.type === 'page');
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise(r => ws.addEventListener('open', r));
ws.addEventListener('close', () => { if (globalThis.DONE) return; console.error('CDP socket closed (renderer crash / OOM?)'); process.exit(2); });
proc.on('exit', c => { if (globalThis.DONE) return; console.error('chrome exited', c); process.exit(3); });
let id = 0; const pending = new Map();
ws.addEventListener('message', ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
});
const send = (method, params = {}) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const evalJS = async expr => (await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true })).result?.result?.value;

await send('Page.enable');
await send('Page.navigate', { url: pathToFileURL(input).href });
let ok = false;
await sleep(1500);

// parts (optional 4th arg): JSON {tabs:[...], parts:[{range:"2-3", label:"…", tab:1 or [1,2]}]}
// Each part prints with a running head (section + big page number) and a bottom tab strip
// with the current section highlighted, so sections can be found by flipping.
const partsFile = process.argv[5];
const esc = t => t.replace(/&/g, '&amp;').replace(/</g, '&lt;');
const base = 'font-family:Noto Sans,DejaVu Sans,sans-serif;-webkit-print-color-adjust:exact;print-color-adjust:exact;';
const head = label => `<div style="${base}font-size:7.5pt;width:100%;padding:0 8mm;margin-top:0;display:flex;justify-content:space-between;align-items:baseline;color:#333"><span>${esc(label)}</span><span style="font-size:12pt;font-weight:700;color:#000">p.<span class="pageNumber"></span></span></div>`;
const strip = (tabs, cur) => `<div style="${base}width:100%;padding:0 8mm;margin-bottom:1.5mm;display:flex;gap:0.6mm">` + tabs.map((t, i) =>
  `<div style="flex:1;text-align:center;font-size:6.5pt;line-height:4mm;height:4mm;${[].concat(cur).includes(i) ? 'background:#000;color:#fff;font-weight:700' : 'color:#888;border:0.3pt solid #bbb'}">${esc(t)}</div>`).join('') + '</div>';
const print = async (extra) => {
  const r = await send('Page.printToPDF', { preferCSSPageSize: true, scale: 1, printBackground: true, displayHeaderFooter: true, transferMode: 'ReturnAsStream', ...extra });
  if (!r.result) { console.error('printToPDF failed', JSON.stringify(r.error)); process.exit(1); }
  const bufs = [];
  for (;;) {
    const c = (await send('IO.read', { handle: r.result.stream, size: 4 << 20 })).result;
    bufs.push(Buffer.from(c.data, c.base64Encoded ? 'base64' : 'utf8'));
    if (c.eof) break;
  }
  await send('IO.close', { handle: r.result.stream });
  return Buffer.concat(bufs);
};
if (partsFile) {
  const { tabs, parts } = JSON.parse(readFileSync(partsFile, 'utf8'));
  const files = [];
  for (const [i, p] of parts.entries()) {
    const f = join(prof, `part${i}.pdf`);
    writeFileSync(f, await print({ pageRanges: p.range, headerTemplate: head(p.label), footerTemplate: strip(tabs, p.tab) }));
    files.push(f);
  }
  execFileSync('pdfunite', [...files, output]);
} else {
  writeFileSync(output, await print({ headerTemplate: '<span></span>', footerTemplate: '<span></span>' }));
}
globalThis.DONE = true; ws.close(); proc.kill();
console.log('wrote', output);
