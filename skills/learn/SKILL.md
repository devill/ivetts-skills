---
name: learn
description: Reflect on the CURRENT session and route any learnings to the right durable store — Habit Hooks, CLAUDE.md, a new skill, or auto-memory. Does NOT write a log entry. Invoke on /learn, "what did we learn?", "from now on...", or BEFORE saving any auto-memory entry. For logging the session, use /remember instead.
---

# Learn

Reflect on **this session** and put each learning where it belongs. The harness auto-memory prompt offers four memory types (`user` / `feedback` / `project` / `reference`) — but memory is *recall-based* and often not the best home. This skill adds the better alternatives. No log is written; if you want to log the session, use `/remember`.

One roundtrip. Fold any user thoughts from the invocation into the output.

## 1. Reflect (only what you genuinely have)

- What do you wish you'd known at the start?
- What surprised you?
- What did you learn?
- What would you do differently?

## 2. Report

Short paragraph on what the session accomplished, followed by your answers from step 1.

## 3. Route each learning

List your candidate learnings (1–2 lines each). For each, walk this list **in order** and stop at the first match.

1. **Habit Hook** — *enforcement beats recall.* Recurring mistake + **deterministically detectable** (AST, regex, lint rule, file presence, command output) + short repeatable fix. Check whether the project has `habit-hooks` installed and set up.
   - **Present:** draft the check (`title`, `description`, `actionGuidance`, detection logic).
   - **Missing:** suggest implementing installing it. (See https://github.com/habit-hooks/habit-hooks)
2. **CLAUDE.md** — project-wide or global static fact, convention, or strong preference. Keep additions minimal and high-signal; show exact lines and target file (`./CLAUDE.md` or `~/.claude/CLAUDE.md`).
3. **New skill** — multi-step reusable workflow. Draft `SKILL.md` at `~/.claude/skills/<name>/SKILL.md`.
4. **Discard** — one-off, already documented, or too narrow to be useful later.

## Approval

**Ask permission for CLAUDE.md edits, Habit Hooks, and new skills** — show the exact change first.
