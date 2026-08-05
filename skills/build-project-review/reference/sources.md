# Preference sources

## Discovering what exists

Run these before asking the user anything.

```sh
gh repo view --json nameWithOwner,isPrivate,hasIssuesEnabled,hasDiscussionsEnabled
ls CONTRIBUTING* ARCHITECTURE* CODE_OF_CONDUCT* CLAUDE.md AGENTS.md 2>/dev/null
ls docs/adr docs/decisions docs 2>/dev/null | head
ls .github/workflows .github/*TEMPLATE* CODEOWNERS 2>/dev/null
ls .eslintrc* eslint.config.* .rubocop.yml ruff.toml pyproject.toml tsconfig.json .editorconfig 2>/dev/null
gh api repos/OWNER/REPO/contributors --jq '.[:10] | .[] | "\(.login) \(.contributions)"'
```

Contributor counts identify candidates, not maintainers. Confirm who reviews rather than who
commits:

```sh
gh pr list --state merged --limit 60 --json number,reviews --jq '.[].reviews[].author.login' | sort | uniq -c | sort -rn
```

## Source types, most authoritative first

- **Enforced config** — lint/format rules, type strictness, CI steps, `CODEOWNERS`, commit
  hooks, PR templates. Cheap, current, unambiguous. Harvest them so the review *stops*
  re-checking what CI already fails on.
- **Written rules** — `CONTRIBUTING.md`, `ARCHITECTURE.md`, ADRs, style guides,
  `CLAUDE.md`/`AGENTS.md`, design sections of the README. Authoritative and current, but usually
  state rules without the reasoning that lets a reviewer generalize.
- **Review history** — maintainers' issue/PR bodies, comments, inline review comments, review
  bodies. The deepest source and the only one carrying reasoning, trade-offs and rejected
  proposals. Also the most dated: prefer the most recent word on a topic.
- **Merge and revert history** — `git log` on hot files, reverts especially, show which changes
  did not survive contact with reality. Useful when review history is thin.
- **Elsewhere** — Discussions, a mailing list archive, a chat export the user can provide,
  maintainers' blog posts. Ask; do not go hunting.

## Sizing a GitHub harvest

```sh
# threads a person participated in
gh api -X GET search/issues -f q='repo:OWNER/REPO commenter:LOGIN' --jq .total_count
# total comment counts: read the last page number out of the Link response header
gh api -i "repos/OWNER/REPO/issues/comments?per_page=1" | grep -i '^link:'
gh api -i "repos/OWNER/REPO/pulls/comments?per_page=1" | grep -i '^link:'
```

A few thousand records is a few MB. `grep`/`jq` retrieval is enough at that scale — no
embeddings, no vector store.

## Turning non-GitHub sources into corpus records

Same shape, so chunking, distillation and quote verification work unchanged:

```sh
BLOB=https://github.com/OWNER/REPO/blob/main
ls CONTRIBUTING.md ARCHITECTURE.md docs/adr/*.md | while IFS= read -r f; do
  jq -nc --arg p "$f" --arg d "$(git log -1 --format=%aI -- "$f")" --arg u "$BLOB/$f" --rawfile b "$f" \
    '{kind:"doc", author:"repo", date:$d, number:0, title:$p, url:$u, body:$b}'
done >> corpus/corpus.jsonl
jq -sc 'sort_by(.date)[]' corpus/corpus.jsonl > corpus/sorted.jsonl && mv corpus/sorted.jsonl corpus/corpus.jsonl
```

Config files go in the same way with `kind:"config"`. Keep them small — a lockfile is noise, an
ESLint config is signal.

## GitHub harvest gotchas

`scripts/harvest_github.sh` handles all of these. Preserve them when editing it.

- **Four endpoints, not one.** `/issues?state=all` (issue *and* PR bodies, plus the
  number→title map), `/issues/comments`, `/pulls/comments`, and **GraphQL** for top-level PR
  review bodies — REST only exposes those one PR at a time.
- `gh api --paginate` emits one JSON *array per page*; pipe through `jq -c '.[]'`.
- Comment records carry no thread title. Join via the titles map with `--slurpfile`;
  `--argjson` blows the argv limit on large repos.
- On inline review comments keep `path` and the last few lines of `diff_hunk` — the commented
  line is the hunk's last line, and without it the comment is unreadable.
- Guard deleted accounts: `.user.login // ""` before matching.
- Sort the whole corpus by date at the end; chunking assumes chronological order.
