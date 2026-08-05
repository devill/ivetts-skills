---
name: project-review
description: Reviews a <PROJECT> change for the places where a normal code review would diverge from what this project's maintainers actually want, before a human reads it. Use in this repo on /project-review, when reviewing a branch, PR or plan, or before opening an upstream pull request.
---

# Project review

A competent review already catches most of what a maintainer would. This skill covers the rest:
where <PROJECT> deliberately does something a reviewer would flag, and where it holds an
invariant a reviewer would not know to check. Findings go to whoever fixes the code, often
another agent, so each names a file, a problem and a fix.

Never write "X would say", and never attribute an opinion to a person.

## Files

- `principles.md` — the project-specific rules. Only what a default review would *not* produce.
- `corpus/corpus.jsonl` — source records (`kind`, `author`, `date`, `number`, `title`, `url`,
  `body`; `path` on inline review comments), for precedent `principles.md` misses.
- `harvest.sh` — rebuilds the corpus. Run occasionally to refresh.

## Run the whole review in a sub-agent

Pass 1 has to happen in a context that has not read `principles.md`; a fresh sub-agent
guarantees that, and keeps a large corpus out of the main conversation.

## Pass 1 — review with no project context

- Do not open `principles.md` or the corpus.
- Scope the change: `git diff <base>...<head>`, or `gh pr diff <n>` plus `gh pr view <n>`, or
  read the plan.
- Review it knowing only what any competent engineer knows, and write the findings down before
  going on. This list is the control.

## Pass 2 — load the principles, then look again

Read `principles.md` in full and work through it in this order:

1. **What does the project contradict?** Drop or invert every pass-1 finding a maintainer
   deliberately chose — sending someone to "fix" working code is the most expensive false
   positive there is.
2. **What does it confirm, and at what severity?** Re-rank: a pass-1 nit may be a blocker here,
   a pass-1 blocker may be something this project accepts.
3. **What did pass 1 not look at?** For each concept the change touches that `principles.md`
   covers, go back to the code and check it specifically. These are the findings that justify
   the skill existing.

Search the corpus for anything `principles.md` does not settle:

```sh
jq -r 'select(.body|test("REGEX";"i")) | "\(.date[:10]) \(.author) #\(.number) \(.title)\n  \(.url)"' corpus/corpus.jsonl
jq -r 'select((.path//"")|test("src/subsystem")) | "\(.url)\n\(.body)"' corpus/corpus.jsonl
```

- The corpus holds only the maintainers' side of a thread, and stores no resolution.
- Read a thread to its end before citing it — `gh issue view <n> --comments -R <OWNER/REPO>`.
- **An issue closed as obsolete or superseded is not precedent**, however well its opening line
  fits your finding.
- Prefer the most recent word on a topic.

## Pass 3 — attack your own findings, then report

Pass 2 goes looking and comes back with more of everything, actionable or not. This pass gives
the reader the first without the second.

- **Try to kill every finding**: establish, without involving a human, that the code is already
  correct or the point is moot. Read the surrounding code, the mechanism it duplicates, the
  config that may already enforce it. If the list is long, delegate to a sub-agent whose only
  brief is to attack.
- **A finding you cannot ground is deleted, not downgraded.** `consider` is for a grounded
  finding of low severity, never for a hunch you failed to close out.
- **Every concrete claim comes from a command you ran in this session** — a worked example, a
  value a function returns, a commit sha, a line number. Run it and quote the output, or state
  the finding without the specific. Reasoning that is only plausible is fine and should be
  labelled as such; an invented measurement reads as verified and the reader acts on it.
- Cut anything that exists to show you reviewed carefully ("verified", "I checked"), how you
  found it, what you first thought and then revised, and restatements of what the change does.
- Over ~150 words on a single finding needs a reason. If nothing survives, say so in one line —
  a clean review is a result.

Report findings ordered by severity, each tagged with where it came from:

```markdown
### `<file>:<line>` — <the problem in one line>  ·  [project-only | corrected | confirmed]
**Severity:** blocker | should-fix | consider
**Why:** <the rule, and why it applies to this code>
**Fix:** <the concrete change to make>
**Basis:** <principle name> · precedent #NNN
```

- `project-only` — surfaced only after reading the principles. This is the skill's output.
- `corrected` — pass 1 raised it and the project disagrees; state what pass 1 got wrong.
- `confirmed` — pass 1 raised it and the project backs it, usually with a severity change.
- No basis in `principles.md` and still worth raising: mark **Basis:** `inference`, keep it to
  the project's evident direction, and attribute it to no one.
- Where the change knowingly departs from a rule, write "departs from <rule>, decided in #NNN"
  rather than calling it an error.

Close with:

- **Aligns** — what the change gets right that maintainers explicitly asked for.
- **Not covered** — where the principles are silent on the main thrust.
- One line: how many pass-1 findings the principles changed. Persistently zero means
  `principles.md` needs cutting or refreshing.
