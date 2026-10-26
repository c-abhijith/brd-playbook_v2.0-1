# Splitting large files (run by a person)

The agent can only read a few hundred KB of text at a time and has no terminal, so it cannot split files itself. When `/brd-memory-build` (or `/brd-memory-update`) finds a file that is too large, it stops and asks you to run this script on it. Then run the same command again: it continues where it stopped.

## When a file counts as large
Over **1 MB**, or over **20,000 lines**. The agent lists every such file with its size.

## Run it
Needs Python 3 (no extra packages).
```
python tools/split-large-files/split_export.py sources/metadata/sqlserver_Sales_Q4_definitions.csv
python tools/split-large-files/split_export.py sources/documents/operations-manual.md --max-kb 600
python tools/split-large-files/split_export.py sources/pipelines/all-jobs.json
```
It writes a folder next to the file, for example `sqlserver_Sales_Q4_definitions.csv.parts/`, with the parts and an **index** (`….index.md`). The original file is **not changed**; leave it where it is. The agent sees the `.parts` folder, reads the index and the parts, and ignores the original.

## How it splits (logically, never by size alone)
| File | One unit (never cut) | Grouped by | A part never mixes |
|---|---|---|---|
| CSV metadata export (objects, columns, keys, code, dependencies…) | one object: all its rows (for code: every chunk of one procedure, view or function, in order) | schema, then business group from the object name (`usp_rebate_calc` → *rebate*) | two schemas |
| Markdown document | one section under a `#` or `##` heading (headings inside code blocks are ignored) | chapter (`#` heading) | two chapters |
| JSON (jobs, pipelines) | one item of the main list (one job or pipeline) | original order | — |

- Every CSV part repeats the header row; no row is ever cut.
- Size (`--max-kb`, default 800) is only the ceiling. A single unit bigger than that (for example one 3,000-line procedure) gets a part of its own, flagged in the index; the agent reads it in slices.
- The index lists every part with its size, schema or chapter, business groups and contents, and (for CSV) a table of **which part holds which object**.

## Formats it cannot split
Word, PDF, Excel, images: convert to Markdown or CSV first (`tools/word-conversion/README.md`), then split if still large.
