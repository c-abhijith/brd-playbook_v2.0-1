# Large files

The agent can only work with a few hundred KB of text at a time and has no terminal, so it cannot read a huge file in one go or split it itself.

## 1. Limits
- **Large:** over **1 MB** or over **20,000 lines**. It must be split before it is read.
- **Not large:** read in full in consecutive ranges, from line 1 to the last line, updating the reading ledger after each range (`reading-protocol.md`).

## 2. When a large file is found (stop-now question)
At the start of `/brd-memory-build` or `/brd-memory-update`, list every large file with its size and line count and stop:

```
These files are too large to read and must be split first (logically, not by size alone):
  sources/metadata/sqlserver_Sales_Q4_definitions.csv   52.4 MB
Run for each:  python tools/split-large-files/split_export.py <file>
Then run /brd-memory-build again; it continues where it stopped.
```

## 3. How split files are used
- The split tool writes `<file>.parts/` next to the original, with the parts and an index `<stem>.index.md`. The original is not changed.
- When a `.parts/` folder with an index exists for a file, the agent **ignores the original** and reads the parts.
- The original file is registered as **one evidence item**; its location is given as the part and the object or section (`EV-012, part 07, object sales.usp_calc_rebate`).
- The index tells the agent which part holds which schema, business group, object or section. Use it to read only what a stage needs and to follow references between parts.
- A part flagged "larger than the limit" holds a single unit (for example one very long procedure). Read it in slices, keeping the slices of one object together in the same stage.

## 4. Splitting is logical
Never by size alone; a unit is never cut (details in `tools/split-large-files/README.md`):
- code and metadata exports: one object per unit, grouped by schema, then business group
- documents: one section per unit, parts never mix chapters
- job and pipeline definitions: one job or pipeline per unit

## 5. Files that cannot be split or read
Word, PDF, Excel, images: ask for a Markdown or CSV version (`tools/word-conversion/README.md`) and list the file as waiting.
