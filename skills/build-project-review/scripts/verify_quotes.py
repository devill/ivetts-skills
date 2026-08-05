#!/usr/bin/env python3
"""Verify the quotes in a distilled principles draft against the corpus, then strip them.

Usage:
  verify_quotes.py principles.draft.md corpus/corpus.jsonl
  verify_quotes.py principles.draft.md corpus/corpus.jsonl --strip principles.md

A quote line looks like:

    > "verbatim words taken from the corpus" — someuser, 2024-03, https://github.com/...

It passes only if the quoted text is a whitespace-normalized substring of a corpus record
whose author, year-month and URL all match. Anything else is a sub-agent's invention: fix the
citation or delete the claim it supports.

--strip writes the shippable file: quote lines are removed and their URLs are appended to the
rule they backed as bare numbered links, so the reviewer gets the rule and a human keeps a
one-click path back to the evidence. Stripping only runs if verification passed.
"""
import json
import pathlib
import re
import sys

QUOTE_RE = re.compile(
    r'^\s*>\s*[“"](?P<quote>.+?)[”"]\s*[—-]+\s*'
    r'(?P<author>[\w.\-]+),\s*(?P<date>\d{4}-\d{2}),\s*(?P<url>\S+)\s*$'
)


def normalize(text):
    return re.sub(r"\s+", " ", text).strip()


def verify(lines, records):
    """Report every quote line that is not backed by a matching corpus record."""
    checked = failures = 0
    for number, line in enumerate(lines, start=1):
        if not line.lstrip().startswith(">"):
            continue
        match = QUOTE_RE.match(line)
        if not match:
            failures += 1
            print(f"line {number}: UNPARSED  {line.strip()[:100]}")
            continue
        checked += 1
        quote = normalize(match["quote"])
        holders = [r for r in records if quote in r["normalized_body"]]
        if any(
            r["url"] == match["url"]
            and r["author"] == match["author"]
            and str(r["date"])[:7] == match["date"]
            for r in holders
        ):
            continue
        failures += 1
        print(f'line {number}: MISMATCH  "{quote[:60]}…"')
        print(f'  cited as {match["author"]} {match["date"]} {match["url"]}')
        for record in holders[:3]:
            print(f'  text found in {record["author"]} {str(record["date"])[:7]} {record["url"]}')
        if not holders:
            print("  text appears in no corpus record")
    print(f"{checked} quotes checked, {failures} failed", file=sys.stderr)
    return failures


def strip(lines):
    """Remove quote lines, appending their URLs to the rule each block backed."""
    output = []
    urls = []

    def flush():
        if not urls:
            return
        links = " ".join(f"[{i}]({u})" for i, u in enumerate(urls, start=1))
        owner = next((i for i in range(len(output) - 1, -1, -1) if output[i].strip()), None)
        if owner is None or output[owner].lstrip().startswith("#"):
            output.append(f"Sources: {links}")
        else:
            output[owner] = output[owner].rstrip() + " " + links
        urls.clear()

    for line in lines:
        match = QUOTE_RE.match(line)
        if match:
            if match["url"] not in urls:
                urls.append(match["url"])
            continue
        flush()
        output.append(line)
    flush()
    return output


def main():
    if len(sys.argv) not in (3, 5) or (len(sys.argv) == 5 and sys.argv[3] != "--strip"):
        sys.exit(__doc__)
    draft_path, corpus_path = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])

    records = [
        json.loads(line)
        for line in corpus_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for record in records:
        record["normalized_body"] = normalize(record.get("body", ""))

    lines = draft_path.read_text(encoding="utf-8").splitlines()
    if verify(lines, records):
        sys.exit(1)

    if len(sys.argv) == 5:
        out_path = pathlib.Path(sys.argv[4])
        out_path.write_text("\n".join(strip(lines)) + "\n", encoding="utf-8")
        print(f"wrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
