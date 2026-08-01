#!/usr/bin/env python3
"""Render a self-contained HTML report for one hotspot-rec recommendation.

Usage:
  python3 report_html.py analysis.json rec.json -o report.html [--title "..."]

analysis.json comes from `forensics.py --json`. rec.json is written by the
agent (schema in SKILL.md): the recommendation fields plus a focused
before/after diagram of the PROPOSED CHANGE — never the whole system.
Stdlib only; output works offline, light and dark.
"""
import argparse
import html
import json
import math
from pathlib import Path

from forensics import assign_package, build_packages, code_root, dir_distance
from pack import C, pack_siblings, enclose

E = html.escape

BINS = [(0, "h0"), (3, "h1"), (8, "h2"), (15, "h3"), (30, "h4"), (10**9, "h5")]
BIN_LABELS = ["0", "1–3", "4–8", "9–15", "16–30", "31+"]
TEST_SEGMENTS = {"test", "tests", "spec", "specs", "__tests__", "testing"}


def bin_class(commits):
    if commits == 0:
        return "h0"
    for hi, cls in BINS[1:]:
        if commits <= hi:
            return cls
    return "h5"


def is_test(path):
    parts = path.lower().split("/")
    if any(s in TEST_SEGMENTS for s in parts[:-1]):
        return True
    base = parts[-1]
    stem = base.rsplit(".", 1)[0]
    return (base.startswith("test_") or stem.endswith("_test")
            or ".spec." in base or ".test." in base or base == "conftest.py")


def packages_of(data):
    """The boundaries forensics.py settled on, so the drawn circles and the
    cross-boundary edges mean the same thing. Older analysis files predate the
    field; fall back to detecting them the same way."""
    if data.get("packages"):
        return data["packages"]
    paths = [f["path"] for f in data["files"]]
    return build_packages(paths, code_root(paths))


# ------------------------------------------------------- enclosure layout ----

def pack_layout(data, group_key, canvas=(960, 720), margin=12):
    groups = {}
    for f in data["files"]:
        if is_test(f["path"]) or f["loc"] < 10:
            continue
        groups.setdefault(group_key(f["path"]), []).append(f)

    gcircles = []
    for g in sorted(groups):
        fs = sorted(groups[g], key=lambda f: f["path"])
        cs = [C(math.sqrt(f["loc"]) + 0.7, f) for f in fs]
        pack_siblings(cs)
        cx, cy, R = enclose(cs)
        for c in cs:
            c.x -= cx
            c.y -= cy
        gcircles.append(C(R + 4, {"name": g, "files": cs}))

    gcircles.sort(key=lambda c: -c.r)
    pack_siblings(gcircles)
    rx, ry, rootR = enclose(gcircles)

    W, Hgt = canvas
    s = (min(W, Hgt) / 2 - margin) / rootR
    cx0, cy0 = W / 2, Hgt / 2
    out = []
    for gc in gcircles:
        gx, gy = cx0 + (gc.x - rx) * s, cy0 + (gc.y - ry) * s
        files = [{
            "path": c.payload["path"], "loc": c.payload["loc"], "commits": c.payload["commits"],
            "x": gx + c.x * s, "y": gy + c.y * s, "r": max(1.0, (c.r - 0.7) * s),
        } for c in gc.payload["files"]]
        out.append({"name": gc.payload["name"], "x": gx, "y": gy, "r": gc.r * s, "files": files})
    return {"W": W, "H": Hgt, "cx": cx0, "cy": cy0, "R": rootR * s, "groups": out}


def map_svgs(data, layout, group_key, picked, max_pairs=80):
    base, labels = [], []
    base.append(f'<circle class="root-circle" cx="{layout["cx"]:.1f}" cy="{layout["cy"]:.1f}" r="{layout["R"] + 6:.1f}"/>')
    for g in layout["groups"]:
        base.append(f'<circle class="grp-circle" cx="{g["x"]:.1f}" cy="{g["y"]:.1f}" r="{g["r"]:.1f}" '
                    f'data-tip="{E(g["name"])} — {len(g["files"])} files"/>')
        for f in g["files"]:
            cls = bin_class(f["commits"])
            pick = " picked" if f["path"] in picked else ""
            tip = f'{f["path"]} — {f["loc"]:,} lines, {f["commits"]} commits'
            base.append(f'<circle class="fc c-{cls}{pick}" data-f="{E(f["path"])}" cx="{f["x"]:.1f}" '
                        f'cy="{f["y"]:.1f}" r="{f["r"]:.1f}" data-tip="{E(tip)}"/>')
            name = f["path"].rsplit("/", 1)[-1]
            if f["path"] in picked:
                rank = picked[f["path"]]
                mark = f"{rank}. {name}" if len(picked) > 1 else name
                labels.append(f'<text class="pick-label" x="{f["x"]:.1f}" y="{f["y"] - f["r"] - 5:.1f}">{E(mark)}</text>')
            elif f["r"] >= 15 and int(2 * f["r"] * 0.82 / 5.9) >= 6:
                maxc = int(2 * f["r"] * 0.82 / 5.9)
                if len(name) > maxc:
                    name = name[: maxc - 1] + "…"
                labels.append(f'<text class="fc-label cl-{cls}" x="{f["x"]:.1f}" y="{f["y"] + 3.2:.1f}">{E(name)}</text>')
        if g["r"] >= 34:
            name = g["name"]
            maxc = int(2 * g["r"] / 5.4)
            if len(name) > maxc:
                name = name[: maxc - 1] + "…"
            labels.append(f'<text class="grp-name" x="{g["x"]:.1f}" y="{g["y"] - g["r"] - 4:.1f}">{E(name)}</text>')

    hmap = (f'<svg viewBox="0 0 {layout["W"]} {layout["H"]}" role="img" aria-label="Hotspot map">'
            + "".join(base).replace(' data-f="', ' data-x="')  # hotspot map needs no ids
            + "".join(labels) + "</svg>")

    fpos = {f["path"]: f for g in layout["groups"] for f in g["files"]}
    pairs = [r for r in data["pairs"]
             if not is_test(r["a"]) and not is_test(r["b"])
             and r["a"] in fpos and r["b"] in fpos][:max_pairs]
    edges, plabels = [], []
    if pairs:
        minn = min(r["n"] for r in pairs)
        maxn = max(r["n"] for r in pairs)
        for r in sorted(pairs, key=lambda r: r["n"]):
            a, b = fpos[r["a"]], fpos[r["b"]]
            x1, y1, x2, y2 = a["x"], a["y"], b["x"], b["y"]
            dx, dy = x2 - x1, y2 - y1
            dist = math.hypot(dx, dy) or 1
            qx = (x1 + x2) / 2 - dy / dist * dist * 0.12
            qy = (y1 + y2) / 2 + dx / dist * dist * 0.12
            w = 1 + (r["n"] - minn) / max(1, maxn - minn) * 5
            cross = r.setdefault("cross", group_key(r["a"]) != group_key(r["b"]))
            dirs = r.setdefault("dirs", dir_distance(r["a"], r["b"]))
            scope = "same directory" if dirs == 0 else f"{dirs} directory levels apart"
            tip = (f'{r["a"]} ↔ {r["b"]} — changed together {r["n"]}× '
                   f'({r["degree"]}% coupling, {scope})')
            d = f'M{x1:.1f},{y1:.1f} Q{qx:.1f},{qy:.1f} {x2:.1f},{y2:.1f}'
            edges.append(f'<g class="edge{" cross" if cross else ""}" data-n="{r["n"]}" '
                         f'data-a="{E(r["a"])}" data-b="{E(r["b"])}">'
                         f'<path class="wire" d="{d}" style="stroke-width:{w:.1f}"/>'
                         f'<path class="hit" d="{d}" data-tip="{E(tip)}"/></g>')
        for p in sorted({p for r in pairs for p in (r["a"], r["b"])}):
            f = fpos[p]
            name = p.rsplit("/", 1)[-1]
            plabels.append(f'<text class="pl hidden" data-f="{E(p)}" x="{f["x"] + f["r"] + 3:.1f}" '
                           f'y="{f["y"] + 3:.1f}">{E(name[:30])}</text>')
        controls = (f'<div class="filter-row"><label for="thr">Show pairs that changed together at least</label>'
                    f'<input type="range" id="thr" min="{minn}" max="{maxn}" value="{minn}" step="1">'
                    f'<output id="thr-out" class="thr-out"></output>'
                    f'<span class="pair-count" id="pair-count"></span></div>')
    else:
        controls = ""
    cmap = (f'<svg id="cmap" viewBox="0 0 {layout["W"]} {layout["H"]}" role="img" aria-label="Coupling map">'
            + "".join(base) + "".join(edges) + "".join(plabels) + "</svg>")
    return hmap, controls, cmap, pairs


def edge_legend(pairs):
    n_cross = sum(1 for r in pairs if r["cross"])
    share = f"{100 * n_cross / len(pairs):.0f}%" if pairs else "0%"
    return ('<div class="ramp-legend">'
            '<span class="ramp-item"><span class="wire-key wk-in"></span>within a package</span>'
            '<span class="ramp-item"><span class="wire-key wk-cross"></span>crosses a package boundary'
            f' — {n_cross} of {len(pairs)} drawn pairs ({share})</span></div>')


def ramp_legend():
    out = ['<div class="ramp-legend"><span class="ramp-title">commits in window</span>']
    for cls, lab in zip([b[1] for b in BINS], BIN_LABELS):
        out.append(f'<span class="ramp-item"><span class="swatch sw-{cls}"></span>{lab}</span>')
    out.append("</div>")
    return "".join(out)


# ------------------------------------------------------- change diagram ------

def change_panel(spec, side):
    boxes = spec.get("boxes", [])
    edges = spec.get("edges", [])
    rows = {}
    for b in boxes:
        rows.setdefault(b.get("row", 0), []).append(b)
    W = 440
    pos = {}
    parts = []
    y = 8
    for r in sorted(rows):
        row = rows[r]
        widths = [max(80, 7 * len(b["label"]) + 22) for b in row]
        heights = [40 if b.get("note") else 26 for b in row]
        total = sum(widths) + 14 * (len(row) - 1)
        x = max(6, (W - total) / 2)
        rh = max(heights)
        for b, w, h in zip(row, widths, heights):
            pos[b["id"]] = (x, y, w, h)
            parts.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{h}" rx="6" class="cbox"/>'
                         f'<text x="{x + w / 2:.1f}" y="{y + 17}" text-anchor="middle" class="cbox-label">{E(b["label"])}</text>')
            if b.get("note"):
                parts.append(f'<text x="{x + w / 2:.1f}" y="{y + 33}" text-anchor="middle" class="cbox-note">{E(b["note"])}</text>')
            x += w + 14
        y += rh + 44
    Hgt = y - 30
    eparts, lparts = [], []
    for e in edges:
        if e["from"] not in pos or e["to"] not in pos:
            continue
        x1, y1, w1, h1 = pos[e["from"]]
        x2, y2, w2, h2 = pos[e["to"]]
        if abs(y1 - y2) < 1:
            p1 = (x1 + w1, y1 + h1 / 2) if x1 < x2 else (x1, y1 + h1 / 2)
            p2 = (x2, y2 + h2 / 2) if x1 < x2 else (x2 + w2, y2 + h2 / 2)
            d = f'M{p1[0]:.1f},{p1[1]:.1f} L{p2[0]:.1f},{p2[1]:.1f}'
            mx, my = (p1[0] + p2[0]) / 2, y1 - 6
        else:
            src, dst = ((x1, y1, w1, h1), (x2, y2, w2, h2)) if y1 < y2 else ((x2, y2, w2, h2), (x1, y1, w1, h1))
            xa, ya = src[0] + src[2] / 2, src[1] + src[3]
            xb, yb = dst[0] + dst[2] / 2, dst[1]
            d = f'M{xa:.1f},{ya:.1f} C{xa:.1f},{ya + 18:.1f} {xb:.1f},{yb - 18:.1f} {xb:.1f},{yb:.1f}'
            mx, my = (xa + xb) / 2, (ya + yb) / 2
        cls = "hot" if e.get("hot") else "plain"
        marker = "arrh" if e.get("hot") else "arrp"
        eparts.append(f'<path d="{d}" class="cedge {cls}" marker-end="url(#{marker})"/>')
        if e.get("label"):
            lparts.append(f'<text x="{mx:.1f}" y="{my:.1f}" text-anchor="middle" class="cedge-label">{E(e["label"])}</text>')
    return (f'<div class="panel"><h4>{E(side)}</h4>'
            f'<p class="panel-cap">{E(spec.get("caption", ""))}</p>'
            f'<svg viewBox="0 0 {W} {max(Hgt, 60)}">'
            '<defs>'
            '<marker id="arrp" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L8,4 L0,8 z" class="head-plain"/></marker>'
            '<marker id="arrh" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L8,4 L0,8 z" class="head-hot"/></marker>'
            '</defs>'
            + "".join(eparts) + "".join(parts) + "".join(lparts) + "</svg></div>")


# ----------------------------------------------------------------- page ------

def recommendations_of(rec):
    """Ranked list, best first. A rec.json written against the older
    single-recommendation schema still renders, as one entry."""
    if isinstance(rec.get("recommendations"), list):
        return rec["recommendations"]
    return [] if rec.get("verdict") == "no-change" else [rec]


def one_rec(rec, index, total):
    """The proposal first and largest; the material that backs it underneath."""
    def rows(fields):
        out = []
        for dt, key in fields:
            if rec.get(key):
                out.append(f'<dt>{E(dt)}</dt><dd>{E(rec[key])}</dd>')
        return "".join(out)

    lead = rows([("Long-term goal", "long_term_goal"),
                 ("Smallest meaningful step", "smallest_meaningful_step")])
    support = rows([("Why this step first", "why_this_step_first"),
                    ("Step done when", "step_done_when"),
                    ("Evidence", "evidence")])
    if rec.get("corroboration"):
        items = "".join(f"<li>{E(c)}</li>" for c in rec["corroboration"])
        support += f'<dt>Corroboration</dt><dd><ul class="cor">{items}</ul></dd>'
    support += rows([("Weaker than the above", "weaker_because")])

    diagram = ""
    if rec.get("diagram"):
        diagram = ('<div class="panels">'
                   + change_panel(rec["diagram"]["before"], "Before")
                   + change_panel(rec["diagram"]["after"], "After") + "</div>")

    rank = f'<span class="rank">{index + 1}</span>' if total > 1 else ""
    return (f'<div class="rec">{rank}<p class="rec-title">{E(rec.get("title", ""))}</p>'
            f'<dl class="rec-rows lead">{lead}</dl>{diagram}'
            f'<dl class="rec-rows">{support}</dl></div>')


def rec_block(rec, recs):
    cmp_html = ""
    if rec.get("candidates"):
        entries = "".join(
            f'<li><code>{E(c["file"])}</code> — {E(c["verified_diagnosis"])} '
            + (f'<em>{E(c["corroboration"])}</em>' if c.get("corroboration") else "")
            + f'<em> Improvement: {E(c.get("meaningful_improvement", ""))}</em></li>'
            for c in rec["candidates"])
        cmp_html = (f'<details class="cmp"><summary>Comparison table — candidates read before deciding</summary>'
                    f'<ul>{entries}</ul></details>')
    if not recs:
        return (f'<div class="card"><h3>No change recommended</h3>'
                f'<p class="rec-title">{E(rec.get("title", ""))}</p>'
                '<p class="verdict">Every candidate below was read in the code and dismissed on a '
                'named, verified ground — not for being large or hard.</p>'
                f'{cmp_html}</div>')
    head = "Recommendation" if len(recs) == 1 else f"{len(recs)} recommendations, ranked"
    body = "".join(one_rec(r, i, len(recs)) for i, r in enumerate(recs))
    return f'<div class="card"><h3>{head}</h3>{body}{cmp_html}</div>'


def build(analysis_path, rec_path, out_path, title):
    data = json.loads(Path(analysis_path).read_text())
    rec = json.loads(Path(rec_path).read_text())
    packages = packages_of(data)
    group_key = lambda path: assign_package(path, packages)
    recs = recommendations_of(rec)
    picked = {r["picked_file"]: i + 1 for i, r in enumerate(recs) if r.get("picked_file")}
    layout = pack_layout(data, group_key)
    hmap, controls, cmap, drawn = map_svgs(data, layout, group_key, picked)


    title = title or f'Hotspot report — {Path(data["repo"]).name}'
    meta = (f'{E(data["repo"])} @ {E(data["rev"])} — {data["total_commits"]:,} commits in window; '
            f'{len(data["files"]):,} tracked files in {len(packages)} packages.')
    body = f"""
<header><h1>{E(title)}</h1><p class="repo-meta">{meta}</p></header>
{rec_block(rec, recs)}
<div class="card"><h3>Hotspots — the evidence</h3>
<p class="cue">Every circle is a production file (tests excluded): size = lines, colour = commits in the window. The recommendation's target is outlined and named.</p>
{ramp_legend()}{hmap}</div>
<div class="card"><h3>Temporal coupling — the same map, with the wiring drawn in</h3>
<p class="cue">Lines connect files that changed in the same commit. Drag the slider: the pairs that survive are the coupling that costs you. <b>Dashed orange</b> leaves its package circle — a change the architecture claims is unrelated. Hover any line for how many directory levels apart the two files sit: the further apart, the more the co-change contradicts the structure. Same-directory pairs are often cohesion — unless the directory holds parallel implementations of one thing. Check by-design cases (a registry, an API and its consumers) before reading any of it as debt.</p>
{edge_legend(drawn)}{controls}{cmap}</div>
<footer><p>Generated by hotspot-rec from <code>git log --numstat</code>. Append <code>#dark</code> to the URL for a dark version.</p></footer>
"""
    Path(out_path).write_text(TEMPLATE.replace("__BODY__", body).replace("__TITLE__", E(title)))
    print(f"wrote {out_path} ({Path(out_path).stat().st_size / 1024:.0f} KB)")


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root { color-scheme: light;
  --surface:#fcfcfb; --page:#f9f9f7; --ink:#0b0b0b; --ink-2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --baseline:#c3c2b7; --border:rgba(11,11,11,.10); --accent:#2a78d6; --cross:#c2410c;
  --h0:#f0efec; --h1:#cde2fb; --h2:#9ec5f4; --h3:#5598e7; --h4:#256abf; --h5:#0d366b;
  --cink-h0:#52514e; --cink-h1:#0b0b0b; --cink-h2:#0b0b0b; --cink-h3:#0b0b0b; --cink-h4:#fff; --cink-h5:#fff;
  --chip-bg:#f0efec; }
@media (prefers-color-scheme: dark) { :root:where(:not([data-theme="light"])) {
  color-scheme: dark;
  --surface:#1a1a19; --page:#0d0d0d; --ink:#fff; --ink-2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --baseline:#383835; --border:rgba(255,255,255,.10); --accent:#3987e5; --cross:#fb923c;
  --h0:#383835; --h1:#0d366b; --h2:#184f95; --h3:#256abf; --h4:#3987e5; --h5:#86b6ef;
  --cink-h0:#fff; --cink-h1:#fff; --cink-h2:#fff; --cink-h3:#fff; --cink-h4:#0b0b0b; --cink-h5:#0b0b0b;
  --chip-bg:#232322; } }
:root[data-theme="dark"] {
  color-scheme: dark;
  --surface:#1a1a19; --page:#0d0d0d; --ink:#fff; --ink-2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --baseline:#383835; --border:rgba(255,255,255,.10); --accent:#3987e5; --cross:#fb923c;
  --h0:#383835; --h1:#0d366b; --h2:#184f95; --h3:#256abf; --h4:#3987e5; --h5:#86b6ef;
  --cink-h0:#fff; --cink-h1:#fff; --cink-h2:#fff; --cink-h3:#fff; --cink-h4:#0b0b0b; --cink-h5:#0b0b0b;
  --chip-bg:#232322; }
* { box-sizing:border-box; }
body { margin:0; background:var(--page); color:var(--ink);
  font:14px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif; }
main { max-width:1020px; margin:0 auto; padding:28px 16px 60px; }
h1 { font-size:22px; margin:0 0 4px; }
.repo-meta { color:var(--muted); font-size:12.5px; margin:0 0 12px; }
.card { background:var(--surface); border:1px solid var(--border); border-radius:10px;
  padding:18px 20px; margin:14px 0; }
h3 { font-size:15px; margin:0 0 8px; }
.cue { color:var(--ink-2); font-size:13px; margin:4px 0 12px; max-width:82ch; }
.rec-title { font-size:17px; font-weight:600; margin:0 0 10px; }
.rec + .rec { border-top:1px solid var(--border); margin-top:18px; padding-top:16px; }
.rank { display:inline-flex; align-items:center; justify-content:center; width:20px; height:20px;
  border-radius:50%; background:var(--accent); color:#fff; font-size:11.5px; font-weight:700;
  margin-right:7px; vertical-align:2px; }
.rec-rows.lead dd { font-size:15.5px; line-height:1.5; }
.rec-rows.lead dt { font-size:11px; }
.rec .panels { margin:14px 0 4px; }
.rec-rows { margin:0; font-size:13.5px; }
.rec-rows dt { font-size:10.5px; text-transform:uppercase; letter-spacing:.05em;
  color:var(--muted); margin-top:10px; }
.rec-rows dd { margin:2px 0 0; }
ul.cor { margin:2px 0 0; padding-left:18px; }
ul.cor li { margin-bottom:4px; }
.cmp { margin-top:10px; font-size:12px; }
.cmp summary { cursor:pointer; color:var(--muted); font-weight:600; }
.cmp ul { padding-left:18px; margin:6px 0 0; }
.cmp li { margin-bottom:7px; color:var(--ink-2); }
code { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.92em;
  background:var(--chip-bg); padding:1px 4px; border-radius:4px; }
svg { display:block; width:100%; height:auto; }
.root-circle { fill:none; stroke:var(--baseline); }
.grp-circle { fill:var(--page); stroke:var(--border); }
.fc { stroke:var(--surface); stroke-width:1; }
.fc.picked { stroke:var(--ink); stroke-width:2.5; }
.c-h0{fill:var(--h0);} .c-h1{fill:var(--h1);} .c-h2{fill:var(--h2);}
.c-h3{fill:var(--h3);} .c-h4{fill:var(--h4);} .c-h5{fill:var(--h5);}
.fc-label { font-size:10px; text-anchor:middle; pointer-events:none; }
.cl-h0{fill:var(--cink-h0);} .cl-h1{fill:var(--cink-h1);} .cl-h2{fill:var(--cink-h2);}
.cl-h3{fill:var(--cink-h3);} .cl-h4{fill:var(--cink-h4);} .cl-h5{fill:var(--cink-h5);}
.pick-label { font-size:11.5px; font-weight:700; text-anchor:middle; fill:var(--ink);
  paint-order:stroke; stroke:var(--surface); stroke-width:3px; }
.grp-name { font-size:10px; text-transform:uppercase; letter-spacing:.04em; fill:var(--muted);
  text-anchor:middle; paint-order:stroke; stroke:var(--surface); stroke-width:3px; }
.ramp-legend { display:flex; gap:14px; align-items:center; flex-wrap:wrap; margin:0 0 8px;
  font-size:12px; color:var(--ink-2); }
.ramp-title { color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.05em; }
.ramp-item { display:inline-flex; align-items:center; gap:5px; }
.swatch { width:14px; height:14px; border-radius:50%; display:inline-block; border:1px solid var(--border); }
.sw-h0{background:var(--h0);} .sw-h1{background:var(--h1);} .sw-h2{background:var(--h2);}
.sw-h3{background:var(--h3);} .sw-h4{background:var(--h4);} .sw-h5{background:var(--h5);}
#cmap .fc { opacity:.45; } #cmap .fc.live { opacity:1; }
#cmap .fc.picked { opacity:1; }
.filter-row { display:flex; gap:10px; align-items:center; flex-wrap:wrap; font-size:13px;
  color:var(--ink-2); margin-bottom:4px; }
.filter-row input[type=range] { width:220px; accent-color:var(--accent); }
.thr-out { font-weight:600; color:var(--ink); min-width:40px; }
.pair-count { color:var(--muted); }
.verdict { color:var(--ink-2); font-size:13px; margin:0 0 10px; max-width:82ch;
  border-left:3px solid var(--cross); padding-left:10px; }
.wire-key { width:22px; height:0; display:inline-block; vertical-align:middle;
  border-top:3px solid var(--accent); border-radius:2px; }
.wire-key.wk-cross { border-top:3px dashed var(--cross); }
.edge .wire { fill:none; stroke:var(--accent); stroke-linecap:round; opacity:.45; }
/* Coupling that escapes its package is the expensive kind — hue AND dash, so it
   survives greyscale and colour-blindness. */
.edge.cross .wire { stroke:var(--cross); opacity:.85; stroke-dasharray:7 4; }
.edge .hit { fill:none; stroke:transparent; stroke-width:13; pointer-events:stroke; }
.edge:hover .wire { opacity:1; }
.edge.hidden { display:none; }
.pl { font-size:9.5px; fill:var(--ink-2); paint-order:stroke; stroke:var(--surface);
  stroke-width:2.5px; pointer-events:none; }
.pl.hidden { display:none; }
.panels { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
@media (max-width:760px) { .panels { grid-template-columns:1fr; } }
.panel { background:var(--page); border:1px solid var(--border); border-radius:8px; padding:10px 14px; }
.panel h4 { margin:0 0 2px; font-size:12px; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); }
.panel-cap { font-size:12.5px; color:var(--ink-2); margin:0 0 8px; }
.cbox { fill:var(--surface); stroke:var(--border); }
.cbox-label { font-size:11.5px; font-weight:600; fill:var(--ink); }
.cbox-note { font-size:9.5px; fill:var(--muted); }
.cedge { fill:none; } .cedge.plain { stroke:var(--muted); stroke-width:1.4; opacity:.8; }
.cedge.hot { stroke:var(--accent); stroke-width:2.4; }
.head-plain { fill:var(--muted); } .head-hot { fill:var(--accent); }
.cedge-label { font-size:9.5px; fill:var(--muted); paint-order:stroke; stroke:var(--page); stroke-width:3px; }
footer { color:var(--muted); font-size:12px; margin-top:24px; }
#tip { position:fixed; pointer-events:none; background:var(--ink); color:var(--surface);
  font-size:12px; padding:5px 9px; border-radius:6px; max-width:440px; z-index:10;
  opacity:0; transition:opacity .08s; }
</style>
</head>
<body>
<main>__BODY__</main>
<div id="tip" role="status"></div>
<script>
(function () {
  if (location.hash === '#dark') document.documentElement.dataset.theme = 'dark';
  if (location.hash === '#light') document.documentElement.dataset.theme = 'light';
  var tip = document.getElementById('tip');
  document.addEventListener('pointermove', function (ev) {
    var el = ev.target.closest('[data-tip]');
    if (!el) { tip.style.opacity = 0; return; }
    tip.textContent = el.getAttribute('data-tip');
    tip.style.opacity = 1;
    var x = Math.min(ev.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
    var y = ev.clientY + 16;
    if (y + tip.offsetHeight > window.innerHeight - 8) y = ev.clientY - tip.offsetHeight - 10;
    tip.style.left = x + 'px'; tip.style.top = y + 'px';
  });
  var slider = document.getElementById('thr');
  if (slider) {
    var svg = document.getElementById('cmap');
    var out = document.getElementById('thr-out');
    var count = document.getElementById('pair-count');
    var edges = Array.prototype.slice.call(svg.querySelectorAll('.edge'));
    var labels = Array.prototype.slice.call(svg.querySelectorAll('.pl'));
    var circles = {};
    svg.querySelectorAll('.fc[data-f]').forEach(function (c) { circles[c.dataset.f] = c; });
    function apply() {
      var t = +slider.value, shown = 0, live = {};
      edges.forEach(function (e) {
        var on = +e.dataset.n >= t;
        e.classList.toggle('hidden', !on);
        if (on) { shown++; live[e.dataset.a] = 1; live[e.dataset.b] = 1; }
      });
      var labelsOn = shown <= 24;
      labels.forEach(function (l) { l.classList.toggle('hidden', !(labelsOn && live[l.dataset.f])); });
      Object.keys(circles).forEach(function (p) { circles[p].classList.toggle('live', !!live[p]); });
      out.textContent = t + '\\u00d7';
      count.textContent = shown + ' of ' + edges.length + ' pairs shown';
    }
    slider.addEventListener('input', apply);
    apply();
  }
})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("analysis")
    ap.add_argument("rec")
    ap.add_argument("-o", "--out", default="hotspot-report.html")
    ap.add_argument("--title", default=None)
    a = ap.parse_args()
    build(a.analysis, a.rec, a.out, a.title)
