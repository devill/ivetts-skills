#!/usr/bin/env bash
# Harvest a repo's maintainers' GitHub writing — issue and PR bodies, issue comments, inline
# review comments and PR review bodies — into corpus/corpus.jsonl, sorted by date.
# Rebuilds from scratch; rerun to refresh. Fill in the config block before first use.
set -euo pipefail

: "${REPO_OWNER:=OWNER}"
: "${REPO_NAME:=REPO}"
: "${AUTHORS:=[\"LOGIN\"]}"   # JSON array of GitHub logins

if [ "$REPO_OWNER" = OWNER ] || [ "$REPO_NAME" = REPO ] || [ "$AUTHORS" = '["LOGIN"]' ]; then
  echo "Set REPO_OWNER, REPO_NAME and AUTHORS in this script (or in the environment)." >&2
  exit 2
fi

cd "$(dirname "$0")"
mkdir -p corpus
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# gh api --paginate emits one JSON array per page, so flatten to one object per line.
fetch() { gh api --paginate "repos/$REPO_OWNER/$REPO_NAME/$1" | jq -c '.[]'; }

echo "Fetching issue and PR bodies..." >&2
fetch "issues?state=all&per_page=100" > "$TMP/issues.ndjson"

echo "Fetching issue comments..." >&2
fetch "issues/comments?per_page=100" > "$TMP/issue_comments.ndjson"

echo "Fetching inline review comments..." >&2
fetch "pulls/comments?per_page=100" > "$TMP/review_comments.ndjson"

# Top-level PR review bodies are only exposed per-PR over REST, so page them over GraphQL.
echo "Fetching PR reviews..." >&2
cursor=""
: > "$TMP/review_pages.ndjson"
while :; do
  args=(-f owner="$REPO_OWNER" -f name="$REPO_NAME")
  [ -n "$cursor" ] && args+=(-f cursor="$cursor")
  page=$(gh api graphql "${args[@]}" -f query='
    query($owner: String!, $name: String!, $cursor: String) {
      repository(owner: $owner, name: $name) {
        pullRequests(first: 50, after: $cursor) {
          pageInfo { hasNextPage endCursor }
          nodes {
            number title
            reviews(first: 40) {
              nodes { author { login } body state submittedAt url }
            }
          }
        }
      }
    }')
  jq -c '.' <<<"$page" >> "$TMP/review_pages.ndjson"
  [ "$(jq -r '.data.repository.pullRequests.pageInfo.hasNextPage' <<<"$page")" = "true" ] || break
  cursor=$(jq -r '.data.repository.pullRequests.pageInfo.endCursor' <<<"$page")
done

echo "Assembling corpus..." >&2
# Comment records carry no thread title; --slurpfile keeps this map off the argv limit.
jq -sc 'map({(.number|tostring): .title}) | add // {}' "$TMP/issues.ndjson" > "$TMP/titles.json"

{
  jq -c --argjson a "$AUTHORS" '
    select((.user.login // "") as $l | $a | index($l)) |
    select((.body // "") != "") |
    {kind: (if .pull_request then "pr_body" else "issue_body" end),
     author: .user.login, date: .created_at, number: .number,
     title: .title, url: .html_url, body: .body}
  ' "$TMP/issues.ndjson"

  jq -c --argjson a "$AUTHORS" --slurpfile t "$TMP/titles.json" '
    select((.user.login // "") as $l | $a | index($l)) |
    (.issue_url | split("/") | last) as $n |
    {kind: "issue_comment", author: .user.login, date: .created_at,
     number: ($n | tonumber), title: ($t[0][$n] // ""), url: .html_url,
     body: .body}
  ' "$TMP/issue_comments.ndjson"

  # The commented line is the last line of diff_hunk; without a tail the comment is unreadable.
  jq -c --argjson a "$AUTHORS" --slurpfile t "$TMP/titles.json" '
    select((.user.login // "") as $l | $a | index($l)) |
    (.pull_request_url | split("/") | last) as $n |
    {kind: "review_comment", author: .user.login, date: .created_at,
     number: ($n | tonumber), title: ($t[0][$n] // ""), url: .html_url,
     path: .path,
     hunk_tail: ((.diff_hunk // "") | split("\n") | .[-6:] | join("\n")),
     body: .body}
  ' "$TMP/review_comments.ndjson"

  jq -c --argjson a "$AUTHORS" '
    .data.repository.pullRequests.nodes[] as $pr |
    $pr.reviews.nodes[] |
    select(((.author.login // "") as $l | $a | index($l)) and .body != "") |
    {kind: "review", author: .author.login, date: .submittedAt,
     number: $pr.number, title: $pr.title, state: .state, url: .url,
     body: .body}
  ' "$TMP/review_pages.ndjson"
} | jq -sc 'sort_by(.date)[]' > corpus/corpus.jsonl

echo "Done: $(wc -l < corpus/corpus.jsonl) records" >&2
jq -r '[.author, .kind] | join(" ")' corpus/corpus.jsonl | sort | uniq -c >&2
