#!/usr/bin/env python3
"""
Split a large source file into logical parts the agent can read.

Run by a person (the agent has no terminal). Never changes the original file.

    python split_export.py <file> [--max-kb 800]

Output: a folder "<file>.parts/" next to the file, holding the parts and an index
"<stem>.index.md". The agent reads the index and the parts, and ignores the original.

Logical units (a unit is never cut):
  CSV metadata exports   one object (schema + object): every row of it, in original order
                         (for code exports: every chunk of one procedure / view / function)
  Markdown documents     one section under a level-1 or level-2 heading
  JSON                   one element of the top-level list (for example one job or pipeline)

Units are grouped logically before packing:
  CSV        by schema, then by business group (from the object name, e.g. usp_rebate_calc -> rebate)
  Markdown   in document order (a part never mixes two level-1 chapters)
  JSON       in original order

A part never mixes two schemas (CSV) or two chapters (Markdown). A unit larger than the
limit gets a part of its own and is flagged in the index (the agent reads it in slices).
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import OrderedDict

SCHEMA_COLS = ["schema_name", "table_schema", "specific_schema", "volume_schema", "referencing_schema",
               "source_schema", "object_schema"]
OBJECT_COLS = ["object_name", "table_name", "procedure_name", "routine_name", "specific_name",
               "referencing_object", "referencing_entity_name", "job_name", "pipeline_name", "name"]
PREFIXES = ["usp_", "sp_", "proc_", "p_", "vw_", "v_", "fn_", "f_", "udf_", "tvf_", "tbl_", "t_", "tr_", "trg_",
            "dim_", "fact_", "fct_", "stg_", "stage_", "rpt_", "tmp_", "ref_", "lkp_", "map_", "hist_", "load_", "etl_"]


def business_group(name):
    if not name:
        return "other"
    n = name.strip().strip("[]").lower()
    for p in PREFIXES:
        if n.startswith(p) and len(n) > len(p):
            n = n[len(p):]
            break
    n = re.sub(r"([a-z])([A-Z])", r"\1_\2", n)
    tokens = [t for t in re.split(r"[_\-\s\.]+", n) if t and not t.isdigit()]
    return tokens[0] if tokens else "other"


def safe(s):
    s = re.sub(r"[^A-Za-z0-9]+", "-", str(s)).strip("-").lower()
    return (s or "x")[:40]


def pick(cols, candidates):
    low = {c.lower(): c for c in cols}
    for c in candidates:
        if c in low:
            return low[c]
    return None


def pack(groups, max_bytes, boundary_key):
    """groups: list of (boundary, group_name, [units]); unit = (label, size, payload).
    Returns parts: list of dict(boundary, groups=set, units=[...], size, oversize)."""
    parts, cur = [], None

    def close():
        nonlocal cur
        if cur and cur["units"]:
            parts.append(cur)
        cur = None

    for boundary, gname, units in groups:
        gsize = sum(u[1] for u in units)
        if cur and (cur["boundary"] != boundary or cur["size"] + gsize > max_bytes):
            close()
        for u in units:
            if u[1] > max_bytes:
                close()
                parts.append({"boundary": boundary, "groups": {gname}, "units": [u], "size": u[1], "oversize": True})
                continue
            if cur and cur["size"] + u[1] > max_bytes:
                close()
            if cur is None:
                cur = {"boundary": boundary, "groups": set(), "units": [], "size": 0, "oversize": False}
            cur["groups"].add(gname)
            cur["units"].append(u)
            cur["size"] += u[1]
    close()
    return parts


def split_csv(path, max_bytes):
    csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)
    scol, ocol = pick(header, SCHEMA_COLS), pick(header, OBJECT_COLS)
    si = header.index(scol) if scol else None
    oi = header.index(ocol) if ocol else None
    units = OrderedDict()
    for i, r in enumerate(rows):
        sch = r[si] if si is not None and si < len(r) else ""
        obj = r[oi] if oi is not None and oi < len(r) else f"row{i+1}"
        units.setdefault((sch, obj), []).append(r)

    def rowsize(r):
        return sum(len(x.encode("utf-8")) + 3 for x in r) + 2

    by = OrderedDict()
    for (sch, obj), rs in units.items():
        g = business_group(obj) if oi is not None else "rows"
        by.setdefault((sch, g), []).append(((sch, obj), sum(rowsize(r) for r in rs), rs))
    groups = [(k[0], k[1], v) for k, v in sorted(by.items(), key=lambda kv: (kv[0][0].lower(), kv[0][1]))]
    hsize = rowsize(header)
    parts = pack(groups, max_bytes - hsize, "schema")
    rule = f"one object per unit (schema column: {scol or 'none'}, object column: {ocol or 'none'}); " \
           f"grouped by schema, then business group"
    return header, parts, rule, (scol, ocol)


def split_markdown(path, max_bytes):
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines(keepends=True)
    sections, cur, fence, chapter = [], {"chapter": "(start)", "title": "(start)", "lines": []}, False, "(start)"
    for ln in lines:
        if ln.lstrip().startswith("```"):
            fence = not fence
        m = None if fence else re.match(r"^(#{1,2})\s+(.*)", ln)
        if m:
            if cur["lines"]:
                sections.append(cur)
            if m.group(1) == "#":
                chapter = m.group(2).strip()
            cur = {"chapter": chapter, "title": m.group(2).strip(), "lines": []}
        cur["lines"].append(ln)
    if cur["lines"]:
        sections.append(cur)
    by = OrderedDict()
    for s in sections:
        text = "".join(s["lines"])
        by.setdefault(s["chapter"], []).append((s["title"], len(text.encode("utf-8")), text))
    groups = [(ch, ch, us) for ch, us in by.items()]
    return pack(groups, max_bytes, "chapter"), "one section under a level-1 or level-2 heading; parts never mix chapters"


def split_json(path, max_bytes):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    key = None
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        lists = [k for k, v in data.items() if isinstance(v, list) and v and all(isinstance(x, dict) for x in v)]
        if not lists:
            return None, None, "no list of items found; not split", data
        key = max(lists, key=lambda k: len(data[k]))
        items = data[key]
    else:
        return None, None, "not a list or object; not split", data
    units = []
    for i, it in enumerate(items):
        label = (it.get("name") or it.get("job_name") or it.get("pipeline_name") or it.get("id") or f"item{i+1}") \
            if isinstance(it, dict) else f"item{i+1}"
        units.append((str(label), len(json.dumps(it, ensure_ascii=False).encode("utf-8")) + 2, it))
    parts = pack([("all", "items", units)], max_bytes, "all")
    return parts, key, f"one element of the list{(' under key ' + key) if key else ''} per unit", data


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--max-kb", type=int, default=800, help="target size per part in KB (default 800)")
    a = ap.parse_args()
    path = os.path.abspath(a.file)
    max_bytes = a.max_kb * 1024
    stem, ext = os.path.splitext(os.path.basename(path))
    ext = ext.lower()
    outdir = path + ".parts"
    if os.path.exists(outdir) and os.listdir(outdir):
        sys.exit(f"{outdir} already exists and is not empty. Remove it first if you want to split again.")
    os.makedirs(outdir, exist_ok=True)
    size = os.path.getsize(path)
    index_rows, extra = [], []

    if ext == ".csv":
        header, parts, rule, (scol, ocol) = split_csv(path, max_bytes)
        lookup = []
        for n, p in enumerate(parts, 1):
            sch = p["boundary"] or "no-schema"
            grp = next(iter(p["groups"])) if len(p["groups"]) == 1 else "mixed"
            fname = f"{stem}_part{n:02d}_{safe(sch)}_{safe(grp)}.csv"
            with open(os.path.join(outdir, fname), "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(header)
                rows = 0
                for (label, _sz, rs) in p["units"]:
                    w.writerows(rs)
                    rows += len(rs)
            objs = [u[0][1] for u in p["units"]]
            for o in objs:
                lookup.append((sch, o, fname))
            index_rows.append((fname, os.path.getsize(os.path.join(outdir, fname)), f"{len(objs)} objects, {rows} rows",
                               sch, ", ".join(sorted(p["groups"])),
                               (", ".join(objs[:8]) + (f" … (+{len(objs)-8})" if len(objs) > 8 else "")),
                               "ONE OBJECT LARGER THAN THE LIMIT: read in slices" if p["oversize"] else ""))
        extra.append("## Where each object is\n\n| Schema | Object | Part |\n|---|---|---|\n" +
                     "\n".join(f"| {s} | {o} | {fn} |" for s, o, fn in lookup))
        boundary_word = "Schema"
    elif ext in (".md", ".markdown", ".txt"):
        parts, rule = split_markdown(path, max_bytes)
        for n, p in enumerate(parts, 1):
            fname = f"{stem}_part{n:02d}_{safe(p['boundary'])}.md"
            body = "".join(u[2] for u in p["units"])
            if not body.lstrip().startswith("# "):
                body = f"<!-- Part {n} of {os.path.basename(path)} · chapter: {p['boundary']} -->\n" + body
            with open(os.path.join(outdir, fname), "w", encoding="utf-8") as f:
                f.write(body)
            titles = [u[0] for u in p["units"]]
            index_rows.append((fname, os.path.getsize(os.path.join(outdir, fname)), f"{len(titles)} sections",
                               p["boundary"], "", "; ".join(titles[:6]) + (" …" if len(titles) > 6 else ""),
                               "ONE SECTION LARGER THAN THE LIMIT: read in slices" if p["oversize"] else ""))
        boundary_word = "Chapter"
    elif ext == ".json":
        parts, key, rule, data = split_json(path, max_bytes)
        if parts is None:
            os.rmdir(outdir)
            sys.exit(f"Not split: {rule}. Convert or split this file by hand, keeping each job or pipeline whole.")
        for n, p in enumerate(parts, 1):
            fname = f"{stem}_part{n:02d}.json"
            items = [u[2] for u in p["units"]]
            out = items if key is None else {**{k: v for k, v in data.items() if k != key}, key: items}
            with open(os.path.join(outdir, fname), "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=1)
            labels = [u[0] for u in p["units"]]
            index_rows.append((fname, os.path.getsize(os.path.join(outdir, fname)), f"{len(labels)} items", "", "",
                               ", ".join(labels[:8]) + (" …" if len(labels) > 8 else ""),
                               "ONE ITEM LARGER THAN THE LIMIT: read in slices" if p["oversize"] else ""))
        boundary_word = "—"
    else:
        os.rmdir(outdir)
        sys.exit("Only .csv, .md, .txt and .json can be split. Convert other formats first (see tools/word-conversion).")

    idx = os.path.join(outdir, f"{stem}.index.md")
    with open(idx, "w", encoding="utf-8") as f:
        f.write(f"# Split index: {os.path.basename(path)}\n\n")
        f.write(f"- Original: `{os.path.basename(path)}` ({size/1024/1024:.1f} MB), not changed\n")
        f.write(f"- Parts: {len(index_rows)}, target size {a.max_kb} KB each\n")
        f.write(f"- Unit rule: {rule}\n")
        f.write("- For the agent: register this index as the evidence item for the original file, read the parts "
                "instead of the original, and use the table below to find which part holds what.\n\n")
        f.write(f"| Part | Size (KB) | Contains | {boundary_word} | Business groups | First items | Notes |\n|---|---|---|---|---|---|---|\n")
        for r in index_rows:
            f.write(f"| {r[0]} | {r[1]//1024} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {r[6]} |\n")
        for e in extra:
            f.write("\n" + e + "\n")
    print(f"Split {os.path.basename(path)} into {len(index_rows)} parts in {outdir}")
    print(f"Index: {idx}")
    big = [r[0] for r in index_rows if r[6]]
    if big:
        print("Larger than the limit (kept whole): " + ", ".join(big))


if __name__ == "__main__":
    main()
