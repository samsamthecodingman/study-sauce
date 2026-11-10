# Spec: worked solutions to a practice or past exam

A practice or past exam paper for the unit is in `<UNIT>/StudyKB/sources/` (a PDF, or text exported from it). It usually gives only brief final answers or hints. The student needs **full worked solutions** inside the printed notes. Show the hand method a student would write in the exam: partial marks go to reasoning.

Read SPEC.md first: the house format (blocks, classes, TeX escaping, refs, rules) is the same. Each question becomes an **exam-question block** inside the chapter section that teaches it.

## Output
No separate file by default: each question goes into its chapter's `ch/NN.html`, in the section it tests (your brief says which questions belong to which chapter). If the brief asks for a stand-alone set, write `<notes-dir>/ch/pe-<name>.html` as plain fragments of the same blocks.

```html
<div class="blk pe" id="peQ4"><div class="lab">Exam question · PE Q4 · Short topic</div>
  <p class="exq"><b>Question.</b> all given numbers, matrices, options …</p>
  … working (Solution | Explanation grid, or paragraphs) …
  <p><span class="ans">Answer: …</span> ✓ matches official answer</p>
  <div class="seealso"><span>See also</span><a class="ref" data-to="s5B"></a></div>
</div>
```

The id is `peQ<n>` for the (first) paper; for further papers use a prefix letter, `peAQ<n>`, label `PE A Q<n>`, and list the prefixes in `<notes-dir>/paper.json` (`{"": "Practice exam 2026", "A": "2025 final"}`). The label title (after the second `·`) must be plain text; it feeds the practice-exam map at the back.

## For each question
1. **Question** in brief: enough to be read without the PDF (all given numbers, matrices, options). For figures, tables and anything with equations, **render the page** (`pdftoppm -png -r 80 -f P -l P <paper.pdf> <scratchpad>/pe/p`) and look at it; `pdftotext` garbles equations, so check the rendered page for every question, not just the figures.
2. **Solution**: full working, step by step, the way you'd write it in the exam. For multiple choice say why the right option is right and, briefly, why each tempting wrong option is wrong.
3. **Answer** in `<span class="ans">`, followed by `✓ matches official answer`, or, if yours differs from the official answer, a `<div class="blk trap">` explaining the discrepancy (re-check hard before claiming the official answer is wrong; say it in your report too). If the paper has no official answer for the question, write `no official answer given` instead.
4. **See also**: ref chips (`data-to="sNX"` or KB heading ids `wN-k`) to the sections that teach the method.

Verify every number with python3/numpy (scratch in `<scratchpad>/pe/`) before writing it.

## Rules
- Don't edit other chapters' files. Don't commit or publish.
- After writing, run `python3 <skill dir>/check.py <notes-dir> NN` (exam question present, tags balanced, refs valid). The main session runs the build; if you build, fix any "MATHJAX ERRORS" / "RAW TEX OUTSIDE MATHJAX" lines from your file.
- Report: file, questions where you disagree with the official answer, anything you couldn't read from the PDF.
