# Ivett's skills

Claude Code skills, distributed as a plugin marketplace. Add it once, then install whichever
you want:

```
/plugin marketplace add devill/ivetts-skills
```

---

## hotspot-rec

```
/plugin install hotspot-rec@ivetts-skills
```

Reads a git repository's history the way Adam Tornhill's *Your Code as a Crime Scene* does —
change frequency against file size, temporal coupling, fan-out — and turns it into **one**
design improvement: a long-term goal, and the smallest step toward it that is worth doing on
its own.

Not a report. Not a backlog. One thing to do next, with the evidence behind it and the
candidates it was chosen over.

Ask for it by name, or with *"where does our maintenance cost live?"*, *"run a hotspot
analysis"*, or by naming a file you dread touching.

### What it produces

A self-contained HTML page — offline, light and dark — with:

- the recommendation, goal and step first, evidence and corroboration underneath;
- an optional before/after diagram of the proposed change;
- the hotspot enclosure map, sized by lines and coloured by commits, with the target outlined;
- the temporal-coupling overlay with a live threshold slider;
- the comparison table, so you can see what was rejected and on what verified grounds.

### How it decides

**The metrics nominate, they never decide.** Churn and coupling say where change lands; only
reading the code says why. The skill requires every candidate to be read before anything is
picked, and every dismissal to cite code rather than a hunch. "No change recommended" is a
legitimate answer.

The design question it asks of whatever the numbers surface: *where is the inappropriate
coupling that keeps bringing us back to this file, and do the dependencies at that seam point
the right way?* A codebase is healthy when a file changes for one reason and a change requires
understanding only a small part of the whole.

### The measurement

`scripts/forensics.py` is stdlib-only Python over `git log --numstat`, so it works on any
language.

- **Window** — the smallest span holding both ≥6 months and ≥5000 commits, or all history if
  the repo holds less. Commit rate varies with team size, so a fixed period samples a busy repo
  and a quiet one very differently.
- **Source files opt in.** Run without `--ext` and it lists the extensions the repo actually
  contains, with file and line counts, so you can name the language's source extensions
  yourself. Excluding known non-source cannot work: generated SVG, `.ai`, `.po` and minified
  bundles are all text, and each outranks real source on line count.
- **Packages at adaptive depth** — boundaries are detected by descending into directories while
  they are oversized, so packages come out comparable in size rather than at one fixed depth.
  Override them with `--packages` when they misread the architecture. Settle them before
  reading any history: boundaries chosen afterwards get drawn where they flatter a favourite.
- **Coupling is reported two ways** — degree (how tightly two files track each other) and
  distance (how many directory levels apart they sit). High degree between few partners is
  usually cohesion. Broad fan-out is the expensive shape, and it is why churn alone is a signal:
  every change to that file drags in understanding the others around it.

Run it directly if you want the raw tables:

```
python3 skills/hotspot-rec/scripts/forensics.py <repo>                  # what extensions are here?
python3 skills/hotspot-rec/scripts/forensics.py <repo> --ext .ts .tsx   # analyse
```

### Does it work?

It was developed against a frozen commit of [vLLM](https://github.com/vllm-project/vllm) —
`1f400c58b`, 21 November 2025 — chosen because the maintainers began restructuring
`gpu_model_runner.py` immediately afterwards. Runs were blinded: the analysing agent had no web
or issue-tracker access and was instructed to treat that date as the present, so it could not
see the answer.

An early version rated `gpu_model_runner.py` first on churn × size and then rejected it,
because its package-boundary rule scored the whole of `vllm/v1/**` as one package and read the
file's coupling as internal cohesion. With boundaries at adaptive depth and fan-out weighed
properly, a blinded run reached it on the mechanism rather than the size — that warm-up
maintains a hand-written second copy of the execution path, down to two inlined copies of a
helper the spec-decode path calls normally — and the same run turned up two live defects on
the way.

---

## learn

```
/plugin install learn@ivetts-skills
```

Reflect on the session that just happened, and put each learning where it will actually take
effect. Invoke it with `/learn`, *"what did we learn?"*, or when you catch yourself saying
*"from now on..."*.

The premise: an agent's memory is **recall-based**, so it works only if the right entry
surfaces at the right moment. Often something else is a better home. The skill reflects first,
then routes each learning through a fixed order, stopping at the first match:

1. **a deterministic hook** — for a recurring mistake a check can catch, because enforcement
   beats recall;
2. **CLAUDE.md** — for a static fact, convention or strong preference;
3. **a new skill** — for a reusable multi-step workflow;
4. **discard** — one-off, already written down, or too narrow to help later.

It shows you the exact change and asks before writing anything.

## Licence

MIT — see [LICENCE.md](LICENCE.md).
