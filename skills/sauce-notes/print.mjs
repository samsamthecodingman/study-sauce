// Print notes.html to PDF via Chrome DevTools Protocol (page.printToPDF, streamed back).
// usage: node print.mjs <chrome> <in.html> <out.pdf>
// Also: fits the formula sheet, and warns on stderr about MathJax errors, raw TeX and formulas wider than their box.
// Print scale: env SN_SCALE (default 0.73, the scale of the ECE4179 booklet; layout width is 665/scale px).
// Heap limit for the renderer: env SN_HEAP_MB (default 2048).
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
const proc = spawn(chrome, ['--headless', '--no-sandbox', '--disable-gpu', '--disable-extensions', '--renderer-process-limit=1', '--disable-dev-shm-usage', '--no-zygote', `--js-flags=--max-old-space-size=${process.env.SN_HEAP_MB || 2048}`,
  `--remote-debugging-port=${port}`, `--user-data-dir=${prof}`, 'about:blank'], { stdio: 'ignore' });
const T0 = Date.now();
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
for (let i = 0; i < 240; i++) {
  await sleep(500);
  const st = await evalJS(`(window.MathJax && MathJax.startup && MathJax.startup.promise) ? MathJax.startup.promise.then(()=>'done') : 'wait'`);
  if (st === 'done') { ok = true; break; }
}
console.error('mathjax', ok, Date.now()-T0);
if (!ok) { console.error('MathJax did not finish'); proc.kill(); process.exit(1); }
// Formula sheet: lay out at A4 content width (176mm), then widen any box whose maths
// overflows to 2 or 3 grid columns; shrink only if it still does not fit at full width.
await send('Emulation.setEmulatedMedia', { media: 'print' });
await send('Emulation.setDeviceMetricsOverride', { width: Math.round(665 / +(process.env.SN_SCALE || 0.73)), height: 1000, deviceScaleFactor: 1, mobile: false });
await sleep(300);
const fit = await evalJS(`(()=>{const log=[];
  const over=f=>{const cs=getComputedStyle(f);const avail=f.clientWidth-parseFloat(cs.paddingLeft)-parseFloat(cs.paddingRight);let w=0,worst=null;
    for(const m of f.querySelectorAll('mjx-container')){const r=m.getBoundingClientRect().width;if(r>w){w=r;worst=m}}
    for(const el of f.querySelectorAll('.m,p,div')){if(el.scrollWidth>el.clientWidth+1&&el.scrollWidth>w){w=el.scrollWidth}}
    return w>avail+0.5?{avail,w,worst}:null};
  for(const fs of document.querySelectorAll('.fs')){fs.style.gridAutoFlow='row dense';
    for(const f of fs.querySelectorAll(':scope>.f')){let o=over(f);if(!o)continue;
      if(o.worst&&o.avail/o.w>=0.85){o.worst.style.fontSize=(95*o.avail/o.w*0.98).toFixed(1)+'%';o=over(f);if(!o){log.push((f.querySelector('.fn')||f).textContent.trim().slice(0,40)+' -> shrunk');continue}o.worst.style.fontSize=''}
      for(const span of [2,3]){f.style.gridColumn='span '+span;o=over(f);if(!o)break}
      if(o&&o.worst){const s=Math.max(0.6,(o.avail/o.w)*0.98);o.worst.style.fontSize=(95*s).toFixed(1)+'%';o=over(f)}
      log.push((f.querySelector('.fn')||f).textContent.trim().slice(0,40)+' -> '+f.style.gridColumn+(o?' STILL OVER':''));}}
  return log})()`);
if (fit && fit.length) console.error('FORMULA SHEET FIT:\n' + fit.join('\n'));
// Formulas wider than the box they sit in (measured at A4 content width, print media; formula-sheet boxes are fitted above).
const wide = await evalJS(`(()=>{const out=[];for(const it of MathJax.startup.document.math){const m=it.typesetRoot;if(!m||m.closest('.fs,svg,h1'))continue;const box=m.closest('.sx>div,.blk,td,th,li,.fgrid>*,section');if(!box)continue;const cs=getComputedStyle(box);const avail=box.clientWidth-parseFloat(cs.paddingLeft)-parseFloat(cs.paddingRight);const s=m.querySelector('svg');const w=(s||m).getBoundingClientRect().width;if(w>avail+1)out.push((box.closest('section[id]')||box).id+' '+Math.round(w)+'px > '+Math.round(avail)+'px: '+it.math.slice(0,140));}return out.slice(0,60)})()`);
if (wide && wide.length) console.error('WIDER THAN COLUMN:\n' + wide.join('\n'));
await send('Emulation.clearDeviceMetricsOverride', {});
const errs = await evalJS(`Array.from(MathJax.startup.document.math).filter(m=>{try{let bad=false;m.root.walkTree(n=>{if(n.isKind&&n.isKind('merror'))bad=true});return bad}catch(e){return true}}).map(m=>m.math.slice(0,120)).slice(0,50)`);
if (errs && errs.length) console.error('MATHJAX ERRORS:\n' + errs.join('\n'));
const raw = await evalJS(`(()=>{const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);const out=[];let n;while(n=w.nextNode()){if(n.parentElement.closest('mjx-container,script,style'))continue;const t=n.textContent;if(/\\\\\\(|\\\\\\[|\\\\frac|_\\{|\\^\\{/.test(t))out.push(t.trim().slice(0,120));}return out.slice(0,50)})()`);
if (raw && raw.length) console.error('RAW TEX OUTSIDE MATHJAX:\n' + raw.join('\n'));
await sleep(500);
// parts (optional 4th arg): JSON {tabs:[...], parts:[{range:"2-3", label:"…", tab:1 or [1,2]}]}
// Each part prints with a running head (section + big page number) and a bottom tab strip
// with the current section highlighted, so sections can be found by flipping.
console.error('checks done', Date.now()-T0);
const partsFile = process.argv[5];
const esc = t => t.replace(/&/g, '&amp;').replace(/</g, '&lt;');
const base = 'font-family:Noto Sans,DejaVu Sans,sans-serif;-webkit-print-color-adjust:exact;print-color-adjust:exact;';
const head = label => `<div style="${base}font-size:7.5pt;width:100%;padding:0 8mm;margin-top:0;display:flex;justify-content:space-between;align-items:baseline;color:#333"><span>${esc(label)}</span><span style="font-size:12pt;font-weight:700;color:#000">p.<span class="pageNumber"></span></span></div>`;
const strip = (tabs, cur) => `<div style="${base}width:100%;padding:0 8mm;margin-bottom:1.5mm;display:flex;gap:0.6mm">` + tabs.map((t, i) =>
  `<div style="flex:1;text-align:center;font-size:6.5pt;line-height:4mm;height:4mm;${[].concat(cur).includes(i) ? 'background:#000;color:#fff;font-weight:700' : 'color:#888;border:0.3pt solid #bbb'}">${esc(t)}</div>`).join('') + '</div>';
const print = async (extra) => {
  const r = await send('Page.printToPDF', { preferCSSPageSize: true, scale: +(process.env.SN_SCALE || 0.73), printBackground: true, displayHeaderFooter: true, transferMode: 'ReturnAsStream', ...extra });
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
