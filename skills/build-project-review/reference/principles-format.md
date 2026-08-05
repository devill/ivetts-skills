# principles.md format

The one file the reviewer agent reads in full, after it has already reviewed the change without
it. Rules and links — no quotes, no narration, no history for its own sake.

## The inclusion test

**Would a competent reviewer who has never seen this project produce this finding anyway?** If
yes, cut it. Cut without hesitation:

- test hygiene ("add a test", "cover both branches", "name tests after behaviour");
- change hygiene ("keep the PR focused", "no commented-out code", "no lockfile churn");
- generic typing ("avoid `any`", "annotate nullability");
- anything a linter, formatter, type checker or CI job already enforces.

Keep the inverse — what a good reviewer gets *wrong* here, and what they cannot know:

- invariants the system depends on, that make a reasonable-looking change incorrect;
- cases where the project deliberately does the thing a reviewer would flag — the highest-value
  rules in the file, because they prevent confident, expensive false positives;
- scope decisions: what belongs in this repo versus userland;
- house conventions with real consequences — a term meaning one specific thing, an option shape
  every sibling API follows;
- proposals that were argued and rejected, and why.

A section surviving with two rules where a chunk offered twenty is the process working.

## Structure

1. **The stance** — 4–6 bullets on how this project thinks about change, for judging code no
   enumerated rule covers.
2. **Rules by theme** — grouped by the concepts a diff touches.
3. **Divergences** — where maintainers disagree, and what happens in practice.
4. **Superseded** — one line each, `old position → current position`, only where the old
   position is still visible in the codebase.
5. **Precedent index** — `#NNN <what was proposed> — rejected | deferred | accepted: <why>`. No
   quotes; the corpus has the thread.

Open with two lines saying what it was distilled from and how to refresh it.

## Writing a rule

```
- **<imperative>** (<severity>) — <why, one clause>; <what to do instead>. [1](url)
```

- **Imperative and testable** — a reviewer must be able to answer yes/no against a hunk.
- **Severity from evidence** — `blocker`: a change was refused over it, or it is an invariant
  the system depends on; `strong`: argued repeatedly; `lean`: stated once, or with dissent.
- **Reason in one clause** — without it a reviewer cannot recognise the rule in an unfamiliar
  shape, and the fixer cannot tell a real violation from a lookalike.
- **Remedy** — a rule without one produces complaints instead of fixes.
- **One link** — bare markdown link to the record it came from, no quoted text.

## The stance

Derive it from what recurs *across* themes: the trade-off the maintainers keep making, what they
treat as cost.

Weak: "quality matters here". Strong: "New API surface is the expensive thing; runtime cost and
internal complexity are cheap by comparison, so proposals that shrink the public surface win
arguments even when they complicate the implementation."

## Worked example

```markdown
## 3. Configuration

- **Reject invalid config at load; never repair it** (blocker) — silent repair hides typos
  until production; throw naming the offending key. [1](https://github.com/OWNER/REPO/pull/412#discussion_r900000001)
- **Prefer documenting a pattern over adding an option** (strong) — every option is permanent
  maintenance; if the use case is expressible with what exists, document it and close the
  issue. [1](https://github.com/OWNER/REPO/issues/291#issuecomment-900000004)

## Precedent index

- #380 per-environment config file cascade — rejected: resolution order became unexplainable.
- #455 auto-detecting the config format from file contents — deferred: wanted a concrete case
  where the extension was not enough; none arrived.
```

Note what is *absent*: nothing about tests, naming, dead code or PR size. A reviewer supplies
those unprompted.
