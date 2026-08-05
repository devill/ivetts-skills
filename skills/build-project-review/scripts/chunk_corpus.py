#!/usr/bin/env python3
"""Render corpus.jsonl into chronological markdown chunks, one per distillation sub-agent.

Usage: chunk_corpus.py corpus/corpus.jsonl chunks/

Markdown rather than JSONL because a sub-agent reads prose far better than escaped strings,
and chronological because a chunk that spans one era gives its sub-agent the context to tell
a current position from an abandoned one.
"""
import json
import pathlib
import sys

# ~200 KB of markdown is roughly 50k tokens: a chunk a sub-agent can read whole and still
# have room to reason about it. The record cap keeps chunks of very short comments from
# holding hundreds of unrelated threads.
MAX_BYTES = 200_000
MAX_RECORDS = 350


def render(record):
    header = "### {kind} | {author} | {date} | #{number} {title}".format(
        kind=record.get("kind", "?"),
        author=record.get("author", "?"),
        date=str(record.get("date", ""))[:10],
        number=record.get("number", 0),
        title=record.get("title", ""),
    )
    lines = [header, record.get("url", "")]
    if record.get("path"):
        lines.append(f"file: {record['path']}")
    if record.get("hunk_tail"):
        lines.append(f"```\n{record['hunk_tail']}\n```")
    lines.append(record.get("body", ""))
    return "\n".join(lines) + "\n\n"


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    corpus_path, out_dir = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)

    records = [json.loads(line) for line in corpus_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    records.sort(key=lambda r: str(r.get("date", "")))

    chunk, size, written = [], 0, []
    for record in records:
        text = render(record)
        if chunk and (size + len(text) > MAX_BYTES or len(chunk) >= MAX_RECORDS):
            written.append(flush(out_dir, len(written) + 1, chunk))
            chunk, size = [], 0
        chunk.append(text)
        size += len(text)
    if chunk:
        written.append(flush(out_dir, len(written) + 1, chunk))

    for path in written:
        print(path)
    print(f"{len(records)} records -> {len(written)} chunks", file=sys.stderr)


def flush(out_dir, index, chunk):
    path = out_dir / f"chunk-{index:03d}.md"
    path.write_text("".join(chunk), encoding="utf-8")
    return path


if __name__ == "__main__":
    main()
