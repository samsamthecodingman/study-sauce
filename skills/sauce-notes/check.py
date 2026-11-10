#!/usr/bin/env python3
"""Check chapter files against the markup contract in SPEC.md (and optionally against an older version).

usage: python3 check.py <notes-dir> [N ...] [--variant name] [--against <old-dir>]

N ...        chapter numbers (default: every ch/NN.html in the notes dir)
--variant    check <notes-dir>/<variant>/ch/NN.html where it exists, else ch/NN.html (same as build.py --variant;
             env CH=<name> does the same)
--against    nothing-lost diff: <old-dir> holds the earlier version of the chapters, NN-*.html or NN-*.md (also looked
             for in <old-dir>/sections/), and optionally files named *practice* with `<h2>Q<n>.` headings for exam
             questions. Prints TeX segments and numbers that were in the old text but are not in the new chapter.
             Items listed there are fine only when they were rewritten equivalently (or deliberately cut: a cull).

Always checked: chapter wrapper, sections, tag balance, duplicate ids, dfn without data-def, TeX inside data-def,
formula blocks without data-name, bad ref ids, raw < inside TeX, forbidden tags, and (if <notes-dir>/assign.json
exists) assigned exam questions (peQ<n>, or "X:n" -> peXQ<n>) and terms missing. Exit code 1 if anything is flagged.
"""
import glob, html.parser, json, os, re, sys


def args():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__); sys.exit(0)
    opts = {"variant": os.environ.get("CH", ""), "against": None}
    rest = []
    i = 0
    while i < len(a):
        if a[i] in ("--variant", "--against") and i + 1 < len(a):
            opts[a[i][2:]] = a[i + 1]
            i += 2
        else:
            rest.append(a[i])
            i += 1
    if not rest:
        sys.exit(__doc__)
    return os.path.abspath(rest[0]), [int(x) for x in rest[1:]], opts


NOTES, WEEKS, OPTS = args()
ASSIGN = json.load(open(os.path.join(NOTES, "assign.json"))) if os.path.exists(os.path.join(NOTES, "assign.json")) else {}


def old_texts(wk):
    """(old chapter text, {Qn: text}) from --against dir, or (None, {})."""
    d = OPTS["against"]
    if not d:
        return None, {}
    d = os.path.abspath(d)
    dirs = [d, os.path.join(d, "sections")]
    old = ""
    for dd in dirs:
        for f in sorted(glob.glob(os.path.join(dd, f"{wk:02d}-*.html")) + glob.glob(os.path.join(dd, f"{wk:02d}-*.md")) + glob.glob(os.path.join(dd, f"week-{wk:02d}-*.md"))):
            old += open(f).read() + "\n"
    pes = {}
    for dd in dirs:
        for f in sorted(glob.glob(os.path.join(dd, "*practice*.html"))):
            s = open(f).read()
            for p in re.split(r"(?=<h2>Q\d+\.)", s)[1:]:
                pes[int(re.match(r"<h2>Q(\d+)", p).group(1))] = re.split(r"</section>", p)[0]
    return old, pes


def tex(s):
    segs = re.findall(r"\\\((.*?)\\\)|\\\[(.*?)\\\]|\$\$(.*?)\$\$|(?<![\\$\w])\$([^$\n]+?)\$(?!\w)", s, flags=re.S)
    norm = lambda t: re.sub(r"\\[,;! ]|\\left|\\right|\\dfrac|\\frac|\\tfrac|\\lt|\\gt|&lt;|&gt;|<|>|[\s{}]", "", t)
    return [n for n in (norm(next(x for x in g if x)) for g in segs if any(g)) if len(n) >= 4]


def nums(s):
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\{\{p:[\w-]+\}\}|p\.__", " ", s)
    return re.findall(r"\d[\d,.]*\d|\d", s)


class Bal(html.parser.HTMLParser):
    VOID = {"br", "hr", "img", "meta", "input", "col", "wbr", "path", "rect", "circle", "line", "polyline", "polygon", "ellipse", "use", "stop"}
    OPT = ("p", "li", "td", "th", "tr")

    def __init__(self):
        super().__init__()
        self.st, self.err, self.ids = [], [], []

    def handle_starttag(self, t, a):
        d = dict(a)
        if "id" in d:
            self.ids.append(d["id"])
        if t not in self.VOID and t not in self.OPT:
            self.st.append((t, self.getpos()))

    def handle_startendtag(self, t, a):
        d = dict(a)
        if "id" in d:
            self.ids.append(d["id"])

    def handle_endtag(self, t):
        if t in self.VOID or t in self.OPT:
            return
        if self.st and self.st[-1][0] == t:
            self.st.pop()
        else:
            self.err.append(f"line {self.getpos()[0]}: </{t}> but open {self.st[-1] if self.st else None}")


def pe_id(q):
    if isinstance(q, int) or str(q).isdigit():
        return f"peQ{q}"
    pre, n = str(q).split(":")
    return f"pe{pre}Q{n}"


def new_path(wk):
    for base in ([os.path.join(NOTES, OPTS["variant"])] if OPTS["variant"] else []) + [NOTES]:
        p = os.path.join(base, "ch", f"{wk:02d}.html")
        if os.path.exists(p):
            return p
    return os.path.join(NOTES, "ch", f"{wk:02d}.html")


def check(wk):
    new_f = new_path(wk)
    if not os.path.exists(new_f):
        print(f"== ch{wk}: {new_f} missing")
        return 1
    new = open(new_f).read()
    out = []
    secs = re.findall(r'<section class="sec[^"]*" id="(s\d+[A-Z])"', new)
    if not secs:
        out.append('no <section class="sec" id="sNX"> found')
    if not re.search(rf'<section class="ch" id="c{wk}" data-tab="{wk}" data-title="[^"]+">', new):
        out.append(f'chapter wrapper missing: <section class="ch" id="c{wk}" data-tab="{wk}" data-title="...">')
    bad_sec = [s for s in secs if not s.startswith(f"s{wk}")]
    if bad_sec:
        out.append("section ids must start with the chapter number: " + " ".join(bad_sec))
    a = ASSIGN.get(str(wk), {})
    for q in a.get("pe", []):
        if f'id="{pe_id(q)}"' not in new:
            out.append(f"exam question {pe_id(q)} missing")
    # terms
    terms_by = {}
    for m in re.finditer(r"<dfn([^>]*)>(.*?)</dfn>", new, flags=re.S):
        t = re.search(r'data-term="([^"]+)"', m.group(1))
        terms_by[(t.group(1) if t else re.sub(r"<[^>]+>", "", m.group(2))).strip().lower()] = m.group(1)
    nodef = [k for k, v in terms_by.items() if "data-def=" not in v]
    if nodef:
        out.append("dfn without data-def: " + ", ".join(nodef))
    tm = [t for t in a.get("terms", []) if t.lower() not in terms_by]
    if tm:
        out.append(f"{len(tm)} assigned terms without <dfn>: " + "; ".join(tm))
    tdef = re.findall(r'data-def="([^"]*(?:[_^]\{|\\[a-z(\[])[^"]*)"', new)
    if tdef:
        out.append("TeX inside data-def (glossary shows it raw; use Unicode): " + " | ".join(t[:60] for t in tdef))
    # formula blocks
    nostrip, pos = new, 0
    for m in re.finditer(r'<div class="strip">', new):      # opener strip may omit data-name
        depth, end = 0, None
        for t in re.finditer(r"<(/?)div\b[^>]*>", new[m.start():]):
            depth += -1 if t.group(1) else 1
            if depth == 0:
                end = m.start() + t.end()
                break
        nostrip = nostrip.replace(new[m.start():end], "", 1) if end else nostrip
    nf = len(re.findall(r'class="blk f"(?![^>]*data-name)', nostrip))
    if nf:
        out.append(f"{nf} formula blocks without data-name (only the opener strip may omit it)")
    # refs
    bad = re.findall(r'data-to="(?!s\d+[A-Z]\b|ex\d+[A-Z]-\d+\b|pe[A-Za-z0-9]*Q\d+\b|c\d+\b|w\d+-\d+\b)([^"]*)"', new)
    if bad:
        out.append("bad ref ids: " + " ".join(bad))
    lt = [m.group(0)[:60] for m in re.finditer(r"\\\((?:(?!\\\)).)*?<(?!/?(?:span|b|i)\b)(?:(?!\\\)).)*?\\\)", new, flags=re.S)]
    if lt:
        out.append("raw < inside TeX (use \\lt): " + " | ".join(lt[:5]))
    if re.search(r"<(html|head|style|script)\b", new):
        out.append("contains html/head/style/script")
    if re.search(r"<marker\b", new):
        out.append("redefines a marker (use url(#ar) from the head)")
    if re.search(r"\{\{[A-Za-z_:]+\}\}", new):
        out.append("contains {{...}} placeholders")
    b = Bal()
    b.feed(new)
    out += b.err[:10]
    if b.st:
        out.append(f"unclosed: {b.st[:5]}")
    d = sorted({i for i in b.ids if b.ids.count(i) > 1})
    if d:
        out.append("duplicate ids: " + " ".join(d))
    # ---- nothing-lost diff
    old, pes = old_texts(wk)
    old_len = 0
    if OPTS["against"]:
        if not old:
            out.append(f"--against: no {wk:02d}-* file in {OPTS['against']}")
        else:
            old_all = old + "".join(pes.get(q, "") for q in a.get("pe", []) if isinstance(q, int) or str(q).isdigit())
            old_len = len(old_all)
            n_h2 = len(re.findall(r"<h2[\s>]", old))
            got = []
            for m in re.finditer(r'<section class="sec[^"]*" id="[^"]+" data-from="([^"]*)"', new):
                got += m.group(1).split()
            if got and n_h2:
                want = {f"w{wk}-{k}" for k in range(1, n_h2 + 1)}
                miss = sorted(want - set(got), key=lambda x: int(x.split("-")[1]))
                dup = sorted({g for g in got if got.count(g) > 1})
                if miss:
                    out.append("old h2s not in any data-from: " + " ".join(miss))
                if dup:
                    out.append("old h2s in two data-from: " + " ".join(dup))
            nt = set(tex(new))
            tmiss = [t for t in tex(old_all) if t not in nt]
            if tmiss:
                out.append(f"{len(tmiss)} TeX segments missing (ok only if rewritten equivalently):\n    " + "\n    ".join(m[:110] for m in tmiss[:60]))
            nn = set(nums(new))
            mn = sorted(set(n for n in nums(old_all) if n not in nn))
            if mn:
                out.append("numbers missing: " + " ".join(mn[:100]))
    print(f"== ch{wk}: {old_len + 0 if old_len else '-'} -> {len(new)} bytes, sections {' '.join(secs)}")
    print("\n".join("  " + o for o in out) if out else "  OK")
    return 1 if out else 0


if not WEEKS:
    WEEKS = sorted(int(re.search(r"(\d+)\.html$", p).group(1)) for p in glob.glob(os.path.join(NOTES, "ch", "*.html")))
rc = 0
for w in WEEKS:
    rc |= check(w)
sys.exit(rc)
