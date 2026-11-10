#!/usr/bin/env python3
"""Build the exam-notes booklet (Cambridge-textbook layout) for any unit.

usage: python3 build.py <notes-dir> [--title "..."] [--code ABC1234] [--only 1,2]
                        [--variant name] [--html] [--no-tabs]

<notes-dir> holds   front.html            front matter (see the skill's front.html template; placeholders filled)
                    ch/NN.html            one chapter per file (SPEC.md)
                    assign.json           optional: {"N": {"pe": [...], "terms": [...]}}, used for warnings
                    paper.json            optional: practice-paper name(s) for the practice-exam map
                    <variant>/front.html, <variant>/ch/NN.html   optional overrides, chosen with --variant
Writes into <notes-dir>: notes[-variant].html, <Code>_Exam_Notes[-variant].pdf, and build/ (intermediates).

Pages are found by printing with invisible markers (@@ID@@) and reading them back with pdftotext; refs,
contents, formula sheet and glossary get page numbers, and the loop repeats until the page map settles.
The final print has no markers. Then per-page furniture (thumb tab, running head, page number) is
printed separately and laid over the body with qpdf (skipped, with a message, if qpdf is missing).

--html     stop after writing notes.html (fast check; prints unresolved refs)
--no-tabs  skip the thumb-tab overlay; the PDF is the plain body
--only 1,2 build just those chapters (for testing)

paper.json: a string ("Practice Exam 2026") for one paper, or {"": "Paper name", "A": "Second paper"} keyed by the
id prefix. Exam-question ids are peQ<n> (prefix "") or pe<X>Q<n> (prefix X).
"""
import argparse, glob, html as H, json, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = None            # set in main
NOTES = SRC = VAR = SFX = OUT_HTML = BODY_PDF = TABS_HTML = TABS_PDF = OUT_PDF = BUILD = CODE = TITLE = None
CHROME = None


def find_chrome():
    cands = glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome"))
    cands += glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium_headless_shell-*/chrome-linux*/headless_shell"))
    cands += glob.glob(os.path.expanduser("~/Library/Caches/ms-playwright/chromium-*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium"))
    cands += glob.glob(os.path.expanduser("~/AppData/Local/ms-playwright/chromium-*/chrome-win*/chrome.exe"))
    cands += ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/Applications/Chromium.app/Contents/MacOS/Chromium",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]
    cands += [shutil.which(n) for n in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "microsoft-edge")]
    return next((c for c in cands if c and os.path.exists(c)), None)


def plain(x):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", x))).strip()


def block(s, start):
    """Return end index of the element whose opening tag starts at `start` (balanced by tag name)."""
    tag = re.match(r"<(\w+)", s[start:]).group(1)
    depth, i = 0, start
    pat = re.compile(rf"<(/?){tag}\b[^>]*>")
    for m in pat.finditer(s, start):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return m.end()
    return len(s)


def slug(t):
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


# ---------------------------------------------------------------- model
def pick(rel):
    """Variant file if present, else the base file."""
    v = os.path.join(SRC, rel)
    return v if os.path.exists(v) else os.path.join(NOTES, rel)


def chnum(p):
    return int(re.search(r"(\d+)\.html$", p).group(1))


def load():
    if not os.path.exists(pick("front.html")):
        sys.exit(f"missing {pick('front.html')} (copy the skill's front.html template and fill it)")
    front = re.sub(r"<!--.*?-->", "", open(pick("front.html")).read(), flags=re.S)   # writer comments
    only = set(ARGS.only.split(",")) if ARGS.only else None
    chs = []
    for f in sorted(glob.glob(os.path.join(NOTES, "ch", "*.html")), key=chnum):
        if only and str(chnum(f)) not in only:
            continue
        chs.append(open(pick(os.path.join("ch", os.path.basename(f)))).read())
    if not chs:
        sys.exit(f"no chapters found in {os.path.join(NOTES, 'ch')}")
    return front, chs


def papers():
    """{prefix: paper name} from paper.json (optional)."""
    p = os.path.join(NOTES, "paper.json")
    if not os.path.exists(p):
        return {"": "Practice exam"}
    d = json.load(open(p))
    return {"": d} if isinstance(d, str) else d


def pe_label(prefix, n):
    return f"PE {prefix + ' ' if prefix else ''}Q{n}"


def index(chs):
    """Sections, examples, PE blocks, old-id map, formulas, definitions."""
    info = {"sec": {}, "ch": {}, "old": {}, "label": {}, "f": [], "dfn": [], "pe": {}}
    for c in chs:
        cm = re.search(r'<section class="ch" id="(c\d+)" data-tab="(\d+)" data-title="([^"]+)"', c)
        cid, tab, title = cm.groups()
        info["ch"][cid] = {"tab": tab, "title": title, "secs": []}
        info["label"][cid] = f"Ch {tab}"
        for sm in re.finditer(r'<section class="sec[^"]*" id="(s\d+[A-Z])"(?: data-from="([^"]*)")?', c):
            sid = sm.group(1)
            end = block(c, sm.start())
            body = c[sm.start():end]
            h2 = re.search(r"<h2[^>]*>(.*?)</h2>", body, flags=re.S)
            info["sec"][sid] = {"title": plain(h2.group(1)) if h2 else sid, "ch": cid, "text": plain(body).lower()}
            info["ch"][cid]["secs"].append(sid)
            info["label"][sid] = sid[1:]
            for o in (sm.group(2) or "").split():
                info["old"][o] = sid
            for em in re.finditer(r'<div class="blk ex" id="(ex(\d+[A-Z])-(\d+))"', body):
                info["label"][em.group(1)] = f"Ex {em.group(2)}.{em.group(3)}"
            for pm in re.finditer(r'<div class="blk pe" id="(pe([A-Za-z0-9]*)Q(\d+))"><div class="lab">(.*?)</div>', body, flags=re.S):
                info["label"][pm.group(1)] = pe_label(pm.group(2), pm.group(3))
                info["pe"][(pm.group(2), int(pm.group(3)))] = {"id": pm.group(1), "sec": sid, "title": plain(pm.group(4))}
            for fm in re.finditer(r'<div class="blk f" data-name="([^"]+)"', body):
                e = block(body, fm.start())
                inner = body[fm.start():e]
                inner = re.sub(r'^<div[^>]*>\s*<div class="lab">.*?</div>', "", inner, count=1, flags=re.S)[:-6]
                inner = re.sub(r'\sid="[^"]*"', "", inner)
                info["f"].append({"name": fm.group(1), "sec": sid, "ch": cid, "html": inner.strip()})
            for dm in re.finditer(r"<dfn([^>]*)>(.*?)</dfn>", body, flags=re.S):
                t = re.search(r'data-term="([^"]+)"', dm.group(1))
                d = re.search(r'data-def="([^"]+)"', dm.group(1))
                term = (t.group(1) if t else plain(dm.group(2))).strip()
                info["dfn"].append({"term": term, "def": d.group(1) if d else "", "sec": sid, "ch": cid, "tab": tab})
    return info


def resolve(to, info):
    if to in info["label"]:
        return to
    if to in info["old"]:
        return info["old"][to]
    return None


# ---------------------------------------------------------------- generated parts
def ref(tid, info, pages, text=None):
    lab = text or info["label"].get(tid, tid)
    p = pages.get(tid)
    pp = f'<span class="pp">{p}</span>' if p else ""
    return f'<a class="ref" href="#{tid}">{lab}{pp}</a>'


def contents(info, pages):
    out = ['<div class="qlist cont">']
    for cid, c in info["ch"].items():
        out.append(f'<div class="wk-c"><div class="op-mini"><span class="sb">{c["tab"]}</span>{H.escape(c["title"])}<span style="margin-left:auto;font:700 10pt var(--sans)">{pages.get(cid, "")}</span></div><ul class="toc">')
        for sid in c["secs"]:
            out.append(f'<li><span class="sb">{sid[1:]}</span><span>{H.escape(info["sec"][sid]["title"])}</span><span class="pn">{pages.get(sid, "")}</span></li>')
        out.append("</ul></div>")
    rows = f'<li><span class="sb">G</span><span>Glossary A–Z</span><span class="pn">{pages.get("glossary", "")}</span></li>'
    if info["pe"]:
        qs = sorted(q for _, q in info["pe"])
        rows += f'<li><span class="sb">PE</span><span>Practice exam Q{qs[0]}–Q{qs[-1]}: where each is</span><span class="pn">{pages.get("petable", "")}</span></li>'
    out.append(f'<div class="wk-c"><div class="op-mini"><span class="sb">G</span>Back matter</div><ul class="toc">{rows}</ul></div>')
    out.append("</div>")
    return "\n".join(out)


def ch_toc(cid, info, pages):
    out = ['<ul class="toc">']
    for sid in info["ch"][cid]["secs"]:
        out.append(f'<li><a class="sb" href="#{sid}">{sid[1:]}</a><span>{H.escape(info["sec"][sid]["title"])}</span><span class="pn">{pages.get(sid, "")}</span></li>')
    return "\n".join(out) + "</ul>"


_SEP = re.compile(r',?\s*\\q?quad\s*|,(?:\s*\\ )+\s*|(?:\s*\\ ){2,}\s*(?!\(|\\text\{\s*\()'
                  r'|(?:\s|\\ )*(?=\\(?:Rightarrow|Leftrightarrow|iff)\b)')


def split_display(tex):
    """Split one display formula at top-level ',\\quad', '\\qquad' or before '\\Rightarrow'.
    Returns the parts (comma kept on the left part); one part means it can't be split."""
    parts, depth, env, last, i = [], 0, 0, 0, 0
    while i < len(tex):
        ch = tex[i]
        if ch == "\\":
            m = re.match(r"\\(left|right|begin|end)\b", tex[i:])
            if m:
                env += 1 if m.group(1) in ("left", "begin") else -1
                i += len(m.group(0))
                continue
            if depth == 0 and env == 0 and i > last:
                m = _SEP.match(tex, i - (1 if i and tex[i - 1] == "," else 0))
                if m and m.end() > m.start():
                    s = m.start()
                    left = tex[last:s] + ("," if "," in m.group(0) else "")
                    if left.strip():
                        parts.append(left)
                    last = i = m.end()
                    continue
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1
    parts.append(tex[last:])
    return [p.strip() for p in parts if p.strip()]


def wrap_displays(html):
    """\\[a,\\quad b\\] -> parts that sit on one line when they fit and wrap otherwise."""
    def rep(m):
        parts = split_display(m.group(1))
        if len(parts) < 2:
            return m.group(0)
        return '<span class="eqs">' + "".join(
            f'<span class="eq">\\(\\displaystyle {p}\\)</span>' for p in parts) + "</span>"
    return re.sub(r"\\\[(.*?)\\\]", rep, html, flags=re.S)


def formulas(info, pages):
    out = []
    for cid, c in info["ch"].items():
        fs = [f for f in info["f"] if f["ch"] == cid]
        if not fs:
            continue
        out.append(f'<div class="wkh"><span class="sb">{c["tab"]}</span>{H.escape(c["title"])}</div><div class="fs">')
        for f in fs:
            out.append(f'<div class="blk f"><span class="fn">{H.escape(f["name"])}</span>{ref(f["sec"], info, pages)}<div class="m">{wrap_displays(f["html"])}</div></div>')
        out.append("</div>")
    return "\n".join(out)


def glossary(info, pages):
    seen, rows = set(), []
    for d in info["dfn"]:
        k = d["term"].lower()
        if k in seen:
            continue
        seen.add(k)
        pat = re.compile(r"\b" + re.escape(k.rstrip("s")) + r"s?\b")
        also = [s for s, v in info["sec"].items() if s != d["sec"] and pat.search(v["text"])][:4]
        rows.append((d, also))
    rows.sort(key=lambda r: re.sub(r"^[^a-z0-9]+", "", r[0]["term"].lower()))
    out = ['<section class="bm np" id="glossary" data-tab="G" data-title="Glossary">',
           '<div class="fs-h"><h2>Glossary</h2><span class="src">A–Z. Every term marked <span class="tag d">DEF</span> in the notes.</span></div>',
           '<div class="gl-how"><span><b style="color:var(--ink)">Term</b> <span class="w" style="display:inline-block;font:700 7pt/1 var(--sans);background:var(--ink);color:#fff;border-radius:2pt;padding:1.5pt 3pt">W5</span> = chapter</span>'
           '<span><b style="color:var(--lil-t)">5H</b> = where it is defined (look for <span class="tag d">DEF</span>)</span><span>plain refs = where else it is used</span></div>',
           '<div class="gl">']
    letter = ""
    for d, also in rows:
        L = re.sub(r"^[^A-Za-z0-9]+", "", d["term"])[:1].upper()
        L = L if L.isalpha() else "#"
        if L != letter:
            letter = L
            out.append(f'<div class="L">{L}</div>')
        did = "def-" + slug(d["term"])
        p = pages.get(did) or pages.get(d["sec"])
        al = " · ".join(f'<a href="#{s}">{s[1:]}</a>' for s in also)
        out.append(f'<div class="e"><span class="t">{H.escape(d["term"])}</span><span class="w">W{d["tab"]}</span>'
                   f'<div class="dd">{d["def"]}</div><div class="rr"><a href="#{did}"><b>{d["sec"][1:]}</b> p{p or ""}</a>{" · " + al if al else ""}</div></div>')
    out.append("</div></section>")
    return "\n".join(out)


def petable(info, pages):
    if not info["pe"]:
        return ""
    names = papers()
    src = "; ".join(names.get(p, names.get("", "Practice exam")) for p in sorted({p for p, _ in info["pe"]}))
    out = ['<section class="bm np" id="petable" data-tab="G" data-title="Practice exam map">',
           f'<div class="fs-h"><h2>Practice exam: where each question is</h2><span class="src">{H.escape(src)}. Each is worked in full inside its section.</span></div>',
           '<div class="qlist"><ul class="toc">']
    for prefix, q in sorted(info["pe"]):
        e = info["pe"][(prefix, q)]
        t = re.sub(r"^Exam question\s*·\s*PE [A-Za-z0-9 ]*?Q\d+\s*·?\s*", "", e["title"])
        lab = f"{prefix} Q{q}" if prefix else f"Q{q}"
        out.append(f'<li><a class="sb" href="#{e["id"]}">{H.escape(lab)}</a><span>{H.escape(t)} {ref(e["sec"], info, pages)}</span><span class="pn">{pages.get(e["id"], "")}</span></li>')
    out.append("</ul></div></section>")
    return "\n".join(out)


# ---------------------------------------------------------------- assemble
def assemble(info, pages, markers):
    front, chs = load()
    hp = pick("head.html") if os.path.exists(pick("head.html")) else os.path.join(HERE, "template-head.html")
    head = open(hp).read().replace("{{TITLE}}", H.escape(TITLE))
    body = front + "\n".join(chs) + glossary(info, pages) + petable(info, pages)
    body = body.replace("{{CONTENTS}}", contents(info, pages)).replace("{{FORMULAS}}", formulas(info, pages))
    tabs = [c["tab"] for c in info["ch"].values()]
    secs = [s for c in info["ch"].values() for s in c["secs"]]
    fills = {"{{UNIT_CODE_BR}}": "<br>".join(H.escape(x) for x in ((re.match(r"^([A-Za-z]+)(\d.*)$", CODE) or [None]).groups() if re.match(r"^([A-Za-z]+)(\d.*)$", CODE) else (CODE,)) if x),
             "{{TAB_LIST}}": "F front, " + (f"{tabs[0]}–{tabs[-1]}" if len(tabs) > 2 else ", ".join(tabs)) + ", G glossary",
             "{{SEC_EG}}": ", ".join(s[1:] for s in secs[:2]), "{{FIRST_SEC}}": secs[0] if secs else ""}
    if ARGS.title:
        fills["{{UNIT_TITLE}}"] = H.escape(ARGS.title)
    for k, v in fills.items():
        body = body.replace(k, v)
    left = sorted(set(re.findall(r"\{\{[A-Z_]+\}\}", body)))
    if left:
        print("WARNING: unfilled placeholders in front.html:", " ".join(left), file=sys.stderr)
    body = re.sub(r'(<section class="ch" id="(c\d+)".*?<div class="ch-toc">)(</div>)',
                  lambda m: m.group(1) + ch_toc(m.group(2), info, pages) + m.group(3), body, flags=re.S)
    body = re.sub(r'data-def="([^"]*)"', lambda m: 'data-def="' + m.group(1).replace("<", "&lt;").replace(">", "&gt;") + '"', body)
    unresolved = set()

    def fix_ref(m):
        to, text = m.group(1), m.group(2)
        tid = resolve(to, info)
        if not tid:
            unresolved.add(to)
            return f'<a class="ref">{text or to}</a>'
        return ref(tid, info, pages, text.strip() or None)
    body = re.sub(r'<a class="ref" data-to="([^"]+)">(.*?)</a>', fix_ref, body, flags=re.S)
    # dfn anchors
    seen = set()

    def fix_dfn(m):
        t = re.search(r'data-term="([^"]+)"', m.group(1))
        term = (t.group(1) if t else plain(m.group(2))).strip()
        did = "def-" + slug(term)
        if did in seen:
            return m.group(0)
        seen.add(did)
        mk = f'<span class="mk">@@{did}@@</span>' if markers else ""
        return f'<dfn id="{did}"{m.group(1)}>{mk}{m.group(2)}</dfn>'
    body = re.sub(r"<dfn([^>]*)>(.*?)</dfn>", fix_dfn, body, flags=re.S)
    if markers:
        body = re.sub(r'(<section class="(?:ch|sec|fm|bm)[^"]*" id="([^"]+)"[^>]*>)', r'\1<span class="mk">@@\2@@</span>', body)
        body = re.sub(r'(<div class="blk (?:ex|pe)" id="([^"]+)">)', r'\1<span class="mk">@@\2@@</span>', body)
    open(OUT_HTML, "w").write(head + body + "\n</body></html>\n")
    return body, unresolved


def pdf(src, out, script="print.mjs"):
    r = subprocess.run(["node", os.path.join(HERE, script), CHROME, src, out], capture_output=True, text=True, timeout=900)
    if r.returncode:
        sys.exit(r.stderr)
    return r.stderr


def npages(path):
    return int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", path], capture_output=True, text=True).stdout).group(1))


def find_pages():
    n = npages(BODY_PDF)
    txt = subprocess.run(["pdftotext", BODY_PDF, "-"], capture_output=True, text=True).stdout
    pages = {}
    for i, t in enumerate(txt.split("\f")[:n], 1):
        for m in re.finditer(r"@@([\w-]+)@@", t):
            pages.setdefault(m.group(1), i)
    return pages, n


def tex2txt(t):
    """Plain-text form of short inline TeX, for running heads (no MathJax there)."""
    G = {"alpha":"α","beta":"β","gamma":"γ","delta":"δ","epsilon":"ε","varepsilon":"ε","zeta":"ζ","eta":"η","theta":"θ","lambda":"λ","mu":"μ","nu":"ν","xi":"ξ","pi":"π","rho":"ρ","sigma":"σ","tau":"τ","phi":"φ","varphi":"φ","chi":"χ","psi":"ψ","omega":"ω",
         "Gamma":"Γ","Delta":"Δ","Theta":"Θ","Lambda":"Λ","Sigma":"Σ","Pi":"Π","Phi":"Φ","Psi":"Ψ","Omega":"Ω","nabla":"∇","partial":"∂","infty":"∞","leftarrow":"←","rightarrow":"→","to":"→","leq":"≤","geq":"≥","le":"≤","ge":"≥","neq":"≠","approx":"≈","times":"×","cdot":"·","pm":"±","sum":"∑","prod":"∏","int":"∫","sqrt":"√","in":"∈","top":"ᵀ"}
    t = re.sub(r"\\(?:hat|bar|tilde|vec|mathbf|bm|mathrm|text|mathcal|mathbb|operatorname)\s*\{([^{}]*)\}", r"\1", t)
    t = re.sub(r"\\hat\s+(\w)", lambda m: m.group(1) + "\u0302", t)
    t = re.sub(r"\\([A-Za-z]+)", lambda m: G.get(m.group(1), m.group(1)), t)
    t = re.sub(r"[_^]\{([^{}]*)\}", r"\1", t)
    t = re.sub(r"[_^](\w)", r"\1", t)
    return t.replace("\\(", "").replace("\\)", "").replace("{", "").replace("}", "")


def overlay(body, pages, n):  # uses INFO for the tab slots
    """Per page: tab (chapter), running head (current section), page number."""
    order = [(m.group(1), m.group(2)) for m in re.finditer(r'<section class="(ch|sec|fm|bm)[^"]*" id="([^"]+)"', body)]
    tabs = {m.group(1): m.group(2) for m in re.finditer(r'<section class="(?:ch|fm|bm)[^"]*" id="([^"]+)" data-tab="([^"]+)"', body)}
    titles = {m.group(1): m.group(2) for m in re.finditer(r'<section class="(?:ch|fm|bm)[^"]*" id="([^"]+)" data-tab="[^"]+" data-title="([^"]+)"', body)}
    secs = {m.group(1): tex2txt(plain(m.group(2))) for m in re.finditer(r'<section class="sec[^"]*" id="(s\d+[A-Z])".*?<h2[^>]*>(.*?)</h2>', body, flags=re.S)}
    out = []
    cur_tab, cur_head, cur_top = "F", "", None
    for p in range(1, n + 1):
        starts = [(k, i) for k, i in order if pages.get(i) == p]
        opener = False
        for k, i in starts:
            if k in ("ch", "fm", "bm"):
                cur_tab, cur_top = tabs.get(i, cur_tab), i
                cur_head = f'<b>{"Ch " + cur_tab if k == "ch" else ("Front" if cur_tab == "F" else "Back")}</b> · {H.escape(titles.get(i, ""))}'
                opener = k == "ch" and starts[0][1] == i
            else:
                cur_head = f"<b>{i[1:]}</b> · {H.escape(secs.get(i, ''))}"
        out.append({"tab": cur_tab, "head": "" if opener else cur_head, "num": str(p)})
    slots = ["F"] + [c["tab"] for c in INFO["ch"].values()] + ["G"]
    pj = os.path.join(BUILD, f"pages{SFX}.json")
    json.dump({"slots": slots, "pages": out}, open(pj, "w"))
    subprocess.run([sys.executable, os.path.join(HERE, "mktabs.py"), pj, TABS_HTML], check=True)
    pdf(TABS_HTML, TABS_PDF, "printplain.mjs")
    if not shutil.which("qpdf"):
        print("NOTE: qpdf not found, so the thumb tabs / running heads / page numbers were not laid over the body. "
              f"The PDF is the plain body. Install qpdf and rerun to get them (overlay pages: {TABS_PDF}).", file=sys.stderr)
        shutil.copyfile(BODY_PDF, OUT_PDF)
        return
    r = subprocess.run(["qpdf", BODY_PDF, "--overlay", TABS_PDF, "--", OUT_PDF], capture_output=True, text=True)
    if r.returncode not in (0, 3):      # 3 = warnings only
        sys.exit("qpdf failed: " + r.stderr)


INFO = None


def warn_assign(info):
    """Compare the book with assign.json ({"N": {"pe": [...], "terms": [...]}}), if there is one."""
    p = os.path.join(NOTES, "assign.json")
    if not os.path.exists(p):
        return
    asg = json.load(open(p))
    ids = set(info["label"])
    terms = {d["term"].lower() for d in info["dfn"]}
    only = set(ARGS.only.split(",")) if ARGS.only else None
    for ch, a in asg.items():
        if only and ch not in only:
            continue
        for q in a.get("pe", []):
            pid = pe_id(q)
            if pid not in ids:
                print(f"WARNING: chapter {ch}: assigned exam question {pid} is missing from the book", file=sys.stderr)
        miss = [t for t in a.get("terms", []) if t.lower() not in terms]
        if miss:
            print(f"WARNING: chapter {ch}: {len(miss)} assigned terms without <dfn>: " + "; ".join(miss), file=sys.stderr)


def pe_id(q):
    """assign.json pe entry -> element id: 4 -> peQ4, "A:4" -> peAQ4."""
    if isinstance(q, int) or str(q).isdigit():
        return f"peQ{q}"
    pre, n = str(q).split(":")
    return f"pe{pre}Q{n}"


def main():
    global ARGS, NOTES, SRC, VAR, SFX, OUT_HTML, BODY_PDF, TABS_HTML, TABS_PDF, OUT_PDF, BUILD, CODE, TITLE, CHROME, INFO
    ap = argparse.ArgumentParser(description="Build the exam-notes booklet.")
    ap.add_argument("notes_dir")
    ap.add_argument("--title", help="unit title for the front page, e.g. 'Neural networks & deep learning'")
    ap.add_argument("--code", help="unit code, e.g. ABC1234 (also names the PDF)")
    ap.add_argument("--only", help="comma list of chapter numbers to build, e.g. 3,5")
    ap.add_argument("--variant", default=os.environ.get("VARIANT", ""), help="read <notes-dir>/<variant>/{front.html,ch/} where present; outputs get -<variant>")
    ap.add_argument("--html", action="store_true", help="only write notes.html")
    ap.add_argument("--no-tabs", action="store_true", help="skip the thumb-tab overlay")
    ARGS = ap.parse_args()
    NOTES = os.path.abspath(ARGS.notes_dir)
    VAR = ARGS.variant
    SFX = "-" + VAR if VAR else ""
    SRC = os.path.join(NOTES, VAR) if VAR else NOTES
    CODE = ARGS.code or (os.path.basename(os.path.dirname(NOTES)) if os.path.basename(NOTES) == "ExamNotes" else os.path.basename(NOTES))
    TITLE = f"{CODE} {ARGS.title + ' ' if ARGS.title else ''}exam notes"
    BUILD = os.path.join(NOTES, "build")
    os.makedirs(BUILD, exist_ok=True)
    OUT_HTML = os.path.join(NOTES, f"notes{SFX}.html")
    BODY_PDF = os.path.join(BUILD, f"body{SFX}.pdf")
    TABS_HTML = os.path.join(BUILD, f"tabs{SFX}.html")
    TABS_PDF = os.path.join(BUILD, f"tabs{SFX}.pdf")
    OUT_PDF = os.path.join(NOTES, f"{re.sub(r'[^A-Za-z0-9_-]+', '_', CODE)}_Exam_Notes{SFX}.pdf")

    front, chs = load()
    INFO = info = index(chs)
    warn_assign(info)
    pages = {}
    if ARGS.html:
        body, unres = assemble(info, pages, markers=False)
        print(f"wrote {OUT_HTML}")
        print("unresolved refs:", sorted(unres))
        return
    CHROME = os.environ.get("CHROME") or find_chrome()
    missing_tools = [t for t in ("node", "pdftotext", "pdfinfo") if not shutil.which(t)]
    if not CHROME or missing_tools:
        body, unres = assemble(info, pages, markers=False)
        print(f"wrote {OUT_HTML}, but cannot make the PDF: " + (f"no Chrome/Chromium found (set CHROME=/path/to/chrome); " if not CHROME else "")
              + (f"missing tools: {', '.join(missing_tools)}. " if missing_tools else "")
              + "Open notes.html in a browser and print to PDF (A4, margins None, background graphics on); page numbers will be blank.", file=sys.stderr)
        sys.exit(1)
    for attempt in range(6):
        body, unres = assemble(info, pages, markers=True)
        pdf(OUT_HTML, BODY_PDF)
        new, n = find_pages()
        print(f"pass {attempt + 1}: {n} pages", file=sys.stderr)
        if new == pages:
            break
        pages = new
    else:
        print("WARNING: page numbers did not settle", file=sys.stderr)
    body, unres = assemble(info, pages, markers=False)
    err = pdf(OUT_HTML, BODY_PDF)
    n2 = npages(BODY_PDF)
    if n2 != n:
        print(f"WARNING: page count changed without markers ({n} -> {n2})", file=sys.stderr)
    if err.strip():
        print(err, file=sys.stderr)
    if ARGS.no_tabs:
        shutil.copyfile(BODY_PDF, OUT_PDF)
    else:
        overlay(body, pages, n2)
    ids = set(re.findall(r'\bid="([^"]+)"', body))
    missing = [i for i in ids if re.match(r"(s\d|c\d|ex\d|pe[A-Za-z0-9]*Q\d|def-)", i) and i not in pages]
    print(f"{n2} pages -> {OUT_PDF}")
    print("chapters:", {c: pages.get(c) for c in info["ch"]})
    print("unresolved refs:", sorted(unres))
    print("ids without page:", sorted(missing)[:30])


if __name__ == "__main__":
    main()
