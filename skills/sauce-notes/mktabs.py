# Per-page furniture overlay: thumb tab on the outer edge, running head, page number.
# usage: python3 mktabs.py pages.json out.html
# pages.json = {"slots": ["F","1","2",...,"G"], "pages": [{"tab":"5","head":"...","num":"31"}, ...]}
# The slots are the tab labels in order, derived by build.py from the chapters present
# (F = front matter, one per chapter data-tab, G = back matter). Odd pages get tabs on the
# right edge, even pages on the left.
import json, sys, html

data = json.load(open(sys.argv[1]))
SLOTS = data["slots"]
pages = data["pages"]
TOP, BOT = 18.0, 279.0
H = min((BOT - TOP) / 13, (BOT - TOP) / len(SLOTS))   # same pitch as a 13-tab book; fewer tabs stay compact at the top
out = ['''<!doctype html><meta charset="utf-8"><style>
@page{size:A4;margin:0}*{box-sizing:border-box;margin:0;-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{font-family:'Noto Sans',sans-serif;color:#2A2521}
.p{position:relative;width:210mm;height:297mm;break-after:page;overflow:hidden}
.s{position:absolute;width:9mm;display:flex;align-items:center;justify-content:center;font:700 7pt/1 'Noto Sans';color:#B5ACA2;border:.4pt solid #DDD6CC;background:#fff}
.s.on{background:#2A2521;color:#fff;border-color:#2A2521;font-size:12pt;width:12mm}
.r .s{right:4mm;border-radius:2mm 0 0 2mm}.l .s{left:4mm;border-radius:0 2mm 2mm 0}
.hd{position:absolute;top:8mm;font-size:8pt;color:#6B625A;letter-spacing:.02em}
.hd b{color:#2A2521}
.r .hd{right:20mm;text-align:right}.l .hd{left:20mm}
.pn{position:absolute;bottom:8mm;font:700 11pt/1 'Noto Sans'}
.r .pn{right:20mm}.l .pn{left:20mm}
</style>''']
for i, p in enumerate(pages):
    side = 'r' if i % 2 == 0 else 'l'
    tabs = ''.join(f'<div class="s{" on" if s == p["tab"] else ""}" style="top:{TOP + k*H + .6:.2f}mm;height:{H - 1.2:.2f}mm">{html.escape(s)}</div>' for k, s in enumerate(SLOTS))
    head = f'<div class="hd">{p["head"]}</div>' if p.get("head") else ''
    out.append(f'<div class="p {side}">{tabs}{head}<div class="pn">{html.escape(p["num"])}</div></div>')
open(sys.argv[2], 'w').write('\n'.join(out))
