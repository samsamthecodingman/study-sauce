# Cull pass brief

The booklet is too long (or over the exam's page limit). Make a **proposal**: what could be cut to save space, as a separate variant the student can compare against the full version.

## What you produce
1. For each chapter in your brief: copy `<notes-dir>/ch/NN.html` to `<notes-dir>/cull/ch/NN.html`, then make the cuts **in the copy only**. Never edit `<notes-dir>/ch/`.
2. `<notes-dir>/cull/NOTES-<your range>.md`: one line per cut, grouped by chapter, as
   `- [S|J] 5H · what was cut · why it is safe · ~lines saved`
   S = safe (pure duplication / restatement / padding), J = judgement call (the student might want it). Put a per-chapter total estimate at the end of each group.

## Aim
About **30–40% shorter** text per chapter (or whatever cut the page limit needs; the brief says) without losing anything an exam answer needs. The brief gives the current pages per chapter (from the build's output).

## Keep (never cut)
- Every formula block (`blk f`) and its `data-name`; every exam question block (`blk pe`, ids `peQn`) with its full working.
- At least one worked example for each distinct exam question type, with its answer.
- Every `<dfn>` (move it into kept text if its sentence goes; the glossary is built from them), every section id (and `data-from` if present), every example id that a `<a class="ref" data-to=…>` anywhere in `ch/*.html` or `front.html` points at (grep before deleting an example; if you must delete one, retarget the refs to its section `sNX`).
- Traps that name a real mistake. Calculator chips (if the unit has them).

## Cut candidates (in this order)
- Text that repeats a formula block or Key-ideas line in words; Key-ideas bullets that restate the section heading.
- A second/third worked example of the same type with the same steps (keep the clearest one).
- "You will learn" lines (`p.li`) if they only restate the heading.
- Long prose paragraphs → one line or a table row.
- `extra` (beyond-course) material, anything the unit says is not examinable, and forum notes that only say things already in the text.
- Duplicate content that appears in two chapters (keep it where it's taught, leave a ref chip in the other).
- Concept-map figures stay; architecture figures stay unless a table already says the same.

## Rules
- Plain HTML fragments as in SPEC.md. Keep tags balanced. No `<`/`>` inside `data-def`.
- Check the **copy**: `python3 <skill dir>/check.py <notes-dir> NN --variant cull`. Structural errors (unbalanced tags, missing exam questions, dfn without data-def, bad refs) must be zero. Add `--against <old-dir>` only if you want to see what was lost; the "missing" lines are then your cuts, so expect them.
- Build the comparison with `python3 <skill dir>/build.py <notes-dir> --variant cull` (outputs get a `-cull` suffix; chapters you did not copy fall back to the full version). If memory is tight (several agents running), don't build; the main session builds.
- Don't commit. Don't edit anything outside `<notes-dir>/cull/`.
- Report: per-chapter estimated % shorter, and the 5 biggest J cuts the student should decide on.
