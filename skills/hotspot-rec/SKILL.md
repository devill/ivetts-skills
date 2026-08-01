---
name: hotspot-rec
description: Adam Tornhill-style hotspot and temporal-coupling analysis on any git repo (language independent), producing ONE design improvement — a long-term goal plus the smallest meaningful step toward it. Use when asked for hotspot or change-coupling analysis, "where does our maintenance cost live", an architecture improvement grounded in git history, or an assessment of a specific named pain. Also offer it, unprompted, when a bug keeps coming back, when the same area is repeatedly slow or risky to change, when a file is described as one nobody wants to touch, or when you yourself hit a file that is needlessly complex or has an unusual number of collaborators.
---

# Hotspot recommendation

Find where a codebase's maintenance cost accrues, and turn it into one design improvement
worth making next.

## Measure

```
python3 <this-skill-dir>/scripts/forensics.py <repo> --ext <exts> [--rev SHA] [--packages FILE]
```

Run it without `--ext` first: it lists the extensions the repo actually contains, with file
and line counts. Identify the language and name its source extensions — most have several
(`.ts .tsx`, `.py .pyi`, `.c .h`), and generated, data and prose formats routinely outweigh
the real source on line count, so opt in deliberately rather than trusting the biggest numbers.

The run then prints the package map, hotspots by churn × size with their co-change partners,
lockstep pairs and fan-out, each column explained in the output. The window is the smallest
span holding both ≥6 months and ≥5000 commits, or all history if the repo holds less.

Packages are detected from the tree. Settle them before reading any history and override with `--packages`
(one directory prefix per line) wherever they misread the architecture.

`--rev` requires the tree checked out at that commit. Needs real history, never a `--depth 1`
clone.

## Judge

Treat the output as a starting point for identifying design improvements, never as the answer.
The numbers say where change lands; only the code says why.

A design change is worth making when it moves the codebase toward this: **a file changes for
one reason, and making a change requires understanding only a small part of the codebase.**
So for whatever the numbers surface, the question to answer in the code is where the
inappropriate coupling sits that keeps bringing you back to this file — and whether the
dependencies at that seam point the right way, or want an interface to invert them.

Read every candidate in the code before choosing anything, and write down what you found; a
dismissal cites code. Corroborate the pick against what the metrics cannot see — what the
commits actually were, who pays, stated intent in the tree, the tracker, the team. "No change
recommended" is a legitimate answer.

If the user named a problem, analyse that one through the data; say so in a sentence if the
data points somewhere more expensive.

## Deliver

Commit to one improvement: the long-term goal, and the smallest step toward it that is worth
doing on its own. Add a second or third only where it independently clears the same bar.
Never a plan, never a list of options.

Per recommendation — title, long-term goal, smallest meaningful step, why this step first,
step done when, evidence, corroboration — plus the candidates compared, recommended or not.
The goal and the step are what the reader acts on and lead the page; everything else supports
them. Add a before/after diagram only where it makes the change easier to understand.

Then render the report. Re-run with `--json analysis.json` **using the same flags**, write
`rec.json`, and:

```
python3 <this-skill-dir>/scripts/report_html.py analysis.json rec.json -o <out>.html
```

```json
{
  "recommendations": [
    {
      "picked_file": "...", "title": "...",
      "long_term_goal": "...", "smallest_meaningful_step": "...",
      "why_this_step_first": "...", "step_done_when": "...", "evidence": "...",
      "corroboration": ["<bullet naming its source>", "..."],
      "weaker_because": "OPTIONAL — why this ranks below the ones above it",
      "diagram": {
        "before": {"caption": "...", "boxes": [{"id": "a", "label": "...", "note": "...", "row": 0}],
                   "edges": [{"from": "a", "to": "b", "label": "...", "hot": true}]},
        "after":  {"...": "same shape"}
      }
    }
  ],
  "verdict": "no-change  (OPTIONAL — with an empty recommendations list)",
  "candidates": [{"file": "...", "verified_diagnosis": "...", "meaningful_improvement": "...", "corroboration": "..."}]
}
```

All fields are plain text; the renderer escapes HTML. Diagram the change, not the system —
at most 6 boxes a panel, `row` orders them top to bottom, `hot` marks the recurring cost in
*before* and the mechanism replacing it in *after*.

Write the page where the user asks, otherwise outside version control, and say where it went.
Delete `analysis.json` and `rec.json` afterwards.
