#!/usr/bin/env python3
"""Tornhill-style code forensics: hotspots, temporal coupling, fan-out.

Language independent (works on `git log --numstat`), stdlib only.

Keep the output neutral — tables, no superlatives. A label like "the widest
coupling" pre-adjudicates the pick for whoever reads it. Don't add one.
"""
import argparse
import subprocess
from collections import Counter
from itertools import combinations
from pathlib import Path

MONTH = 30.44 * 24 * 3600

LOCKFILE_NAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "cargo.lock",
    "poetry.lock", "uv.lock", "gemfile.lock", "composer.lock", "go.sum",
}
NOISE_SEGMENTS = {"node_modules", "vendor", "third_party", ".yarn"}
TEST_SEGMENTS = {"test", "tests", "spec", "specs", "__tests__", "testing"}

def is_test(path):
    parts = path.lower().split("/")
    if any(s in TEST_SEGMENTS for s in parts[:-1]):
        return True
    base = parts[-1]
    stem = base.rsplit(".", 1)[0]
    return (base.startswith("test_") or stem.endswith("_test")
            or ".spec." in base or ".test." in base or base == "conftest.py")


def is_noise(path):
    parts = path.lower().split("/")
    return parts[-1] in LOCKFILE_NAMES or any(s in NOISE_SEGMENTS for s in parts)


def wanted(path, exts):
    """Opt-in: only the source extensions the caller named.

    Excluding known non-source cannot work — every repo carries text formats
    that are not code (generated SVG, .ai, .po, minified bundles) and each
    outranks real source on line count. Naming the language's extensions is the
    only rule that holds across repos.
    """
    return not is_noise(path) and any(path.endswith(e) for e in exts)


ROOT_SHARE = 0.6      # a single top dir holding this much of the code is a wrapper
MAX_PACKAGES = 60     # above this the map stops being readable
OTHER = "(other)"     # files loose at the repo top, belonging to no package


def code_root(paths):
    """The directory the codebase actually starts at, or "" for the repo top.

    Repos wrap their code in src/, packages/, lib/ and hang config, CI and docs
    off the top level; splitting from the true top would put the whole codebase
    in one package and every supporting file in its own. Only ONE level is
    stripped — a second dominant directory below it is the largest package, not
    another wrapper, and descending into it buries the rest of the tree in a
    single leftover bucket.
    """
    code = [p for p in paths if not is_test(p)]
    tops = Counter(p.split("/")[0] for p in code if "/" in p)
    if not tops:
        return ""
    top, n = tops.most_common(1)[0]
    return top if n >= ROOT_SHARE * len(code) else ""


def build_packages(paths, root, max_packages=MAX_PACKAGES):
    """Package boundaries at adaptive depth: descend while a directory is
    oversized and can be split, so packages come out roughly comparable in size
    instead of at one fixed depth. `plugins/` holding several real packages gets
    opened up; a directory of many tiny siblings does not.

    Returns a sorted list of directory prefixes; assign_package matches the
    longest one. Deterministic — the agent overrides it with --packages.
    """
    limit = max(30, len(paths) // 25)
    groups, blocked = {}, set()
    for p in paths:
        groups.setdefault(_first_group(p, root), []).append(p)
    while True:
        splittable = {g: _split(g, fs) for g, fs in groups.items()
                      if g not in blocked and len(fs) > limit and len(_split(g, fs)) > 1}
        if not splittable:
            break
        g = max(splittable, key=lambda g: len(groups[g]))
        children = splittable[g]
        if len(groups) - 1 + len(children) > max_packages:
            # A directory of many small siblings (one per plugin, one per model)
            # blows the budget wholesale. Promote only the oversized children and
            # leave the tail in the parent, rather than keeping the lot as one.
            big = {k: fs for k, fs in children.items() if k != g and len(fs) > limit}
            rest = [f for k, fs in children.items() if k not in big for f in fs]
            if not big or len(groups) + len(big) > max_packages:
                blocked.add(g)
                continue
            groups[g] = rest
            groups.update(big)
            blocked.add(g)
            continue
        del groups[g]
        groups.update(children)
    return sorted(g for g in groups if g != OTHER)


def _first_group(path, root):
    """Top-level package before any splitting: a child of the code root, or a
    top-level directory outside it."""
    parts = path.split("/")
    if len(parts) == 1:
        return OTHER
    if root and path.startswith(root + "/"):
        return "/".join(parts[:2]) if len(parts) > 2 else root
    return parts[0]


def _split(group, files):
    """One level deeper: each subdirectory becomes a package, files sitting
    directly in `group` stay with it."""
    depth = len(group.split("/"))
    children = {}
    for f in files:
        parts = f.split("/")
        key = "/".join(parts[: depth + 1]) if len(parts) > depth + 1 else group
        children.setdefault(key, []).append(f)
    return children


def assign_package(path, packages):
    """Longest matching package prefix."""
    best = ""
    for pkg in packages:
        if len(pkg) > len(best) and (path.startswith(pkg + "/") or path == pkg):
            best = pkg
    return best or "(other)"


def read_package_list(path):
    lines = Path(path).read_text().splitlines()
    return sorted(l.strip().rstrip("/") for l in lines
                  if l.strip() and not l.lstrip().startswith("#"))


def dir_of(path):
    return path.rsplit("/", 1)[0] if "/" in path else "."


def dir_distance(x, y):
    """Directory levels between two files: 0 when they are siblings, otherwise
    how far up from the deeper one you must go to reach a common ancestor. The
    further up, the more a co-change contradicts the structure.
    """
    a, b = dir_of(x).split("/"), dir_of(y).split("/")
    common = 0
    for p, q in zip(a, b):
        if p != q:
            break
        common += 1
    return max(len(a), len(b)) - common


def extension_inventory(repo):
    """What the repo is actually made of, so the caller can name its source
    extensions. Extensionless files are listed under their own name."""
    tracked = subprocess.run(["git", "-C", repo, "ls-files"],
                             capture_output=True, text=True, check=True).stdout.splitlines()
    files, lines = Counter(), Counter()
    for path in tracked:
        if is_noise(path):
            continue
        base = path.rsplit("/", 1)[-1]
        key = "." + base.rsplit(".", 1)[1] if "." in base[1:] else base
        files[key] += 1
        lines[key] += line_count(repo, path) or 0
    return files, lines


def oldest_commit_ts(repo, rev):
    out = subprocess.run(
        ["git", "-C", repo, "log", rev, "--max-parents=0", "--format=%ct"],
        capture_output=True, text=True, check=True).stdout.split()
    return min(int(t) for t in out)


def window_for(repo, rev, rev_ts, exts, min_commits, min_months):
    """Smallest window back from `rev` holding both >= min_months and >= min_commits.

    Commit rate varies with team size, so a fixed period samples a busy repo and
    a quiet one very differently. A repo whose whole history is smaller than the
    floor contributes all of it.

    Returns (since, commits, months, hit_floor).
    """
    oldest = oldest_commit_ts(repo, rev)
    months = min_months
    while True:
        start = rev_ts - int(months * MONTH)
        since = "@" + str(start)
        commits = read_commits(repo, rev, since, exts)
        if len(commits) >= min_commits:
            return since, commits, months, True
        if start <= oldest:
            return since, commits, max(1, round((rev_ts - oldest) / MONTH)), False
        months *= 2


def read_commits(repo, rev, since, exts):
    out = subprocess.run(
        ["git", "-C", repo, "log", rev, f"--since={since}", "--numstat",
         "--format=^%H", "--no-renames"],
        capture_output=True, text=True, check=True).stdout
    commits, current = [], []
    for line in out.splitlines():
        if line.startswith("^"):
            if current:
                commits.append(current)
            current = []
        elif "\t" in line:
            p = line.split("\t")
            # git writes "-" for both counts on a binary file; a blob has no
            # lines, so it can never be a hotspot and its co-changes are noise.
            if len(p) == 3 and p[2] and p[0] != "-" and wanted(p[2], exts):
                current.append(p[2])
    if current:
        commits.append(current)
    return commits


def line_count(repo, path):
    """Text lines, or None when the file is gone at this revision or is binary.

    NUL-sniffed like git does: a PNG read as text yields tens of thousands of
    meaningless "lines" that then dominate a commits x lines ranking.
    """
    try:
        with (Path(repo) / path).open("rb") as fh:
            lines = 0
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                if b"\0" in chunk:
                    return None
                lines += chunk.count(b"\n")
            return lines
    except OSError:
        return None  # gone at this revision


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("repo")
    ap.add_argument("--rev", default="HEAD",
                    help="analyse the window before this commit; tree must be checked out at it")
    ap.add_argument("--since", default=None,
                    help="fixed window start (git date), overriding the --min-months/--min-commits floors")
    ap.add_argument("--ext", nargs="*", default=[],
                    help="source extensions to analyse, e.g. --ext .ts .tsx. Run without it to "
                         "list what the repo actually contains. Exact filenames work too "
                         "(--ext .go Dockerfile)")
    ap.add_argument("--packages", metavar="FILE",
                    help="file of directory prefixes, one per line, overriding the detected "
                         "package boundaries (# comments allowed)")
    ap.add_argument("--min-months", type=int, default=6,
                    help="window floor in months (0 disables both floors, giving a 12-month window)")
    ap.add_argument("--min-commits", type=int, default=5000,
                    help="widen the window past --min-months until it holds this many commits")
    ap.add_argument("--max-commit-files", type=int, default=30,
                    help="skip commits touching more files than this when counting pairs")
    ap.add_argument("--min-pair", type=int, default=5)
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--json", metavar="PATH",
                    help="also dump full data (all tracked files, pairs, partners) for report_html.py")
    a = ap.parse_args()

    try:
        rev_date = int(subprocess.run(
            ["git", "-C", a.repo, "log", "-1", "--format=%ct", a.rev],
            capture_output=True, text=True, check=True).stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        raise SystemExit(f"{a.repo}: no commit at '{a.rev}'. This needs a git repo with history.")

    if not a.ext:
        files, lines = extension_inventory(a.repo)
        if not files:
            raise SystemExit(f"{a.repo}: no tracked files to analyse.")
        print(f"== {a.repo} — what this repo contains ==")
        print(f"{'files':>8} {'lines':>10}  extension")
        for ext, n in files.most_common(30):
            print(f"{n:8d} {lines[ext]:10,d}  {ext}")
        print("\nName this codebase's source extensions and re-run with --ext.")
        print("A language often has several (.ts .tsx, .py .pyi, .c .h, .kt .kts);")
        print("leave out generated, data and prose formats, whatever their line count.")
        raise SystemExit(2)

    window = None
    if a.since is None:
        if a.min_months > 0:
            a.since, commits, months, hit_floor = window_for(
                a.repo, a.rev, rev_date, a.ext, a.min_commits, a.min_months)
            window = (months, hit_floor)
        else:
            a.since = "@" + str(rev_date - 365 * 24 * 3600)  # git's unix-timestamp date format
            commits = read_commits(a.repo, a.rev, a.since, a.ext)
    else:
        commits = read_commits(a.repo, a.rev, a.since, a.ext)
    freq = Counter()
    pairs = Counter()
    partners = {}
    for files in commits:
        freq.update(files)
        prod = sorted({f for f in files if not is_test(f)})
        if 1 < len(prod) <= a.max_commit_files:
            pairs.update(combinations(prod, 2))
            for f in prod:
                partners.setdefault(f, set()).update(x for x in prod if x != f)

    loc = {}
    for path in freq:
        loc[path] = line_count(a.repo, path)

    tracked = [p for p in subprocess.run(["git", "-C", a.repo, "ls-files"],
                                         capture_output=True, text=True, check=True).stdout.splitlines()
               if wanted(p, a.ext)]
    if a.packages:
        packages, root = read_package_list(a.packages), None
    else:
        root = code_root(tracked)
        packages = build_packages(tracked, root)
    pkg_of = {p: assign_package(p, packages) for p in set(tracked) | set(freq)}

    if a.json:
        import json
        rows = []
        for path in tracked:
            n = loc[path] if path in loc else line_count(a.repo, path)
            if n:
                rows.append({"path": path, "loc": n, "commits": freq.get(path, 0)})
        pair_rows = [
            {"a": x, "b": y, "n": n,
             "degree": round(100 * n / ((freq[x] + freq[y]) / 2), 1),
             "dirs": dir_distance(x, y),
             "cross": pkg_of[x] != pkg_of[y]}
            for (x, y), n in pairs.items() if n >= 2]
        pair_rows.sort(key=lambda r: (-r["n"], -r["degree"]))
        Path(a.json).write_text(json.dumps({
            "repo": a.repo, "rev": a.rev, "since": a.since, "packages": packages,
            "total_commits": len(commits), "files": rows, "pairs": pair_rows,
            "partners": {f: len(s) for f, s in partners.items()},
            "partners_out_of_dir": {
                f: sum(1 for p in s if dir_of(p) != dir_of(f)) for f, s in partners.items()},
        }))
        print(f"[json] wrote {a.json}")

    print(f"== {a.repo} @ {a.rev} — window: --since '{a.since}' ==")
    if window:
        months, hit_floor = window
        span = f"{months} months" if months < 24 else f"{months / 12:.1f} years"
        reached = (f"reached the {a.min_commits}-commit floor" if hit_floor
                   else f"whole history, still under {a.min_commits} commits")
        print(f"Window: {span} back from {a.rev} ({reached}).")
    print(f"{len(commits)} commits touching matched files; {len(freq)} distinct files changed")

    source = "from --packages" if a.packages else f"detected, code root '{root or '.'}'"
    sizes = Counter(pkg_of[p] for p in tracked)
    print(f"\n-- Packages ({len(packages)}, {source}) --")
    for pkg, n in sizes.most_common():
        print(f"{n:9d}  {pkg}")
    print("Override with --packages FILE if these boundaries misread the architecture.\n")

    prod_hot = [(f, n) for f, n in freq.items() if not is_test(f)]
    scored = sorted(prod_hot, key=lambda t: -(t[1] * (loc[t[0]] or 0)))
    print(f"-- Hotspots (production), top {a.top} by commits x current lines --")
    print(f"{'commits':>8} {'lines':>8} {'partners':>9} {'outside':>8}  file")
    stale = []
    for f, n in scored[: a.top]:
        if loc[f] is None:
            stale.append((f, n))
            continue
        ps = partners.get(f, ())
        outside = sum(1 for p in ps if dir_of(p) != dir_of(f))
        print(f"{n:8d} {loc[f]:8,d} {len(ps):9d} {outside:8d}  {f}")
    for f, n in stale:
        print(f"{n:8d} {'gone':>8} {'':9} {'':8}  {f}  (path does not exist at this revision — restructured; follow the coupling)")
    print("partners = distinct files co-changed with; outside = those in another directory.")

    test_hot = sorted(((f, n) for f, n in freq.items() if is_test(f) and loc.get(f)),
                      key=lambda t: -(t[1] * loc[t[0]]))[:3]
    if test_hot:
        note = ", ".join(f"{f} ({n} commits)" for f, n in test_hot)
        print(f"\nTest-file activity, top 3: {note}")

    print(f"\n-- Lockstep pairs (production, changed together >= {a.min_pair}x) --")
    print(f"{'together':>9} {'degree':>7} {'dirs':>5} {'scope':>6}  pair")
    rows = []
    for (x, y), n in pairs.items():
        if n < a.min_pair:
            continue
        degree = 100 * n / ((freq[x] + freq[y]) / 2)
        rows.append((n, degree, x, y))
    for n, degree, x, y in sorted(rows, reverse=True)[: a.top]:
        # A long window reaches back through restructurings, where a pair of
        # paths that no longer exist can outrank every live one.
        gone = [p for p in (x, y) if not loc.get(p)]
        suffix = f"  ({' and '.join(gone)} gone at this revision)" if gone else ""
        scope = "cross" if pkg_of[x] != pkg_of[y] else "in-pkg"
        print(f"{n:9d} {degree:6.1f}% {dir_distance(x, y):5d} {scope:>6}  {x}  <->  {y}{suffix}")
    print("dirs = directory levels between the two files (0 = same directory); "
          "scope = across the package boundaries listed above.")

    live = [(n, x, y) for n, _, x, y in rows if loc.get(x) and loc.get(y)]
    if live:
        spread = Counter(dir_distance(x, y) for _, x, y in live)
        summary = ", ".join(f"{spread[d]} at {d}" for d in sorted(spread))
        n_cross = sum(1 for _, x, y in live if pkg_of[x] != pkg_of[y])
        print(f"Of the {len(live)} lockstep pairs whose files both still exist: "
              f"{summary} directory levels apart; {n_cross} cross a package boundary.")

    print("\n-- Distinct co-change partners (production), top 10 --")
    print(f"{'partners':>9} {'outside':>8} {'commits':>8}  file")
    for f, s in sorted(partners.items(), key=lambda kv: -len(kv[1]))[:10]:
        gone = "  (gone at this revision)" if loc.get(f) is None else ""
        outside = sum(1 for p in s if dir_of(p) != dir_of(f))
        print(f"{len(s):9d} {outside:8d} {freq[f]:8d}  {f}{gone}")


if __name__ == "__main__":
    main()
