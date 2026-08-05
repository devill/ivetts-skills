---
name: build-project-review
description: Builds a repo-local project-review skill that catches where a default code review would diverge from what a project's maintainers actually want, distilled from their review history, docs and enforced configs. Use when the user wants an automated first-pass review carrying a specific project's preferences before a human reads the diff.
---

# Build a project-review skill

A competent reviewer produces general good practice unprompted, so distilling it buys nothing.
The deliverable is **the delta** — where this project's maintainers do not want what a default
reviewer would ask for.

**Inclusion test, applied at every step:** *would a competent reviewer who has never seen this
project produce this finding anyway?* If yes, it does not ship.

**Deliverable:** `<repo>/.claude/skills/project-review/` with `SKILL.md`, `principles.md`,
`corpus/corpus.jsonl`, `harvest.sh`.

## 1. Discover the sources, then ask

- Probe what the repo exposes first — source list, discovery commands and sizing in
  `reference/sources.md`. Present findings, not questions about findings.
- Show a numbered menu with sizes and a recommendation; harvest only what the user picks.
- Never assume review history exists, or that it is the richest source here.
- On disagreement, higher wins: **enforced config** > **current docs** > **recent comments** >
  **old comments**.
- Anything a linter, formatter, type checker or CI enforces is out — already automated.

## 2. Harvest

- Create `<repo>/.claude/skills/project-review/` and copy `scripts/harvest_github.sh` there as
  `harvest.sh`.
- Fill its config block (`REPO_OWNER`, `REPO_NAME`, `AUTHORS`) and run it; it writes
  `corpus/corpus.jsonl` beside itself, rebuilding from scratch on every run.
- Records carry `kind`, `author`, `date`, `number`, `title`, `url`, `body`, plus
  `path`/`hunk_tail` on inline review comments.
- Non-GitHub sources become records of the same shape — recipe in `reference/sources.md`.

## 3. Distill, one sub-agent per chunk

- `python3 scripts/chunk_corpus.py corpus/corpus.jsonl <chunkdir>`, then one sub-agent per
  chunk, in parallel. Require of each:
  - **only the non-obvious** — the inclusion test on every candidate, plus a list of themes
    dropped as general practice;
  - **rules, not summaries** — the shape in `reference/principles-format.md`, with severity and
    remedy;
  - **one verbatim contiguous quote per rule** — 5–30 words, no ellipsis, with author,
    `YYYY-MM` and exact URL. Waive the word floor on `doc`/`config` records, where one unique
    line is evidence enough;
  - **rejected and deferred proposals** in their own section — a decision that went against the
    obvious choice is the highest-value output;
  - **silence over extrapolation**, and explicit flagging where maintainers disagreed.
- Merge into `principles.draft.md` yourself: one rule per position, however many eras argued it.
- Re-apply the inclusion test to the merged set — chunk sub-agents are lenient, and this pass is
  where the file gets small.
- Add what no chunk can see: **the stance**, **divergences**, **superseded positions**, the
  **precedent index**.

## 4. Verify the quotes, then strip them

```sh
python3 scripts/verify_quotes.py principles.draft.md corpus/corpus.jsonl
python3 scripts/verify_quotes.py principles.draft.md corpus/corpus.jsonl --strip principles.md
```

- A quote passes only as a verbatim substring of a record whose author, month and URL match.
- Fix or delete every failure — a rule that loses its quote is one a sub-agent invented.
- Ship `principles.md`; discard the draft. Quotes are evidence for this step, not for the
  reviewer.

## 5. Generate, install, trial

- Copy `templates/review-skill.md` to `<repo>/.claude/skills/project-review/SKILL.md` and fill
  the placeholders.
- Keep its three passes separate — an uncontaminated default review, principles only afterwards,
  then an attack pass. Collapsing them hides what the project adds.
- Install at project level. If the repo is not the user's, hide the skill via
  `.git/info/exclude`, never the committed `.gitignore`.
- Trial on a real change and check every finding against the code before handover: a first-pass
  review that cries wolf costs more time than it saves.
