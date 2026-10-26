# Reading protocol — every file, every line

The memory must hold everything that is in `sources/`. A file that is only partly read is treated as **not read**.

## 1. Why this rule exists
Copilot's file-reading tool returns a file in slices (for example "lines 1 to 100"). Reading one slice does **not** read the file. The agent must keep requesting the next range until the end of the file. Search results, file names, the first lines, or "this file looks like the previous one" are never a substitute for reading.

## 2. How to read a file
1. Read in **consecutive ranges** from line 1 (for example 1–400, 401–800 …), with no gaps and no overlaps skipped.
2. Keep going until the **end of the file**: use the line count the tool reports, if it reports one; otherwise continue until a range returns no more lines.
3. Never stop early because the content seems repetitive, irrelevant or already known. Repetitive content is recorded as such in the digest, after it has been read.
4. Files over 1 MB or 20,000 lines are read as their split parts (`large-files.md`); **every part** is read in full, the same way.
5. CSV exports are read in full too (all rows of all parts). Very regular rows can be digested in summary form (counts, objects, patterns), but only after every row has been read.

## 3. Write the digest straight away
After each file (or each part) is fully read, and **before** reading the next one, write its digest: `<memory>/notes/EV-nnn.md` (`templates/file-digest.md`). The digest keeps everything the memory may need, with line references:
- what the file is about, state (current / future / unclear), date, origin
- every system, database, table, column, procedure, job, report and interface it mentions
- every process step, business rule, threshold, calculation, exception and control
- every business term and code value, with meanings
- every claim that could be checked against code or data
- every person, team or owner mentioned
- anything unclear, contradictory or referring to missing material
- a "nothing relevant" note for sections that hold nothing useful (so it is clear they were read)

Digests are the bridge between reading and understanding: later stages build the memory from the digests and the metadata, so nothing read is lost when the chat is reset or runs out of room.

## 4. The reading ledger: `<memory>/01-reading-ledger.md`
One row per file or part (`templates/reading-ledger.md`): evidence id, path, total lines, ranges read, **fully read (yes / no)**, digest written (yes / no), date.
- Update it after every range.
- A file is **fully read** only when the ranges cover line 1 to the last line without gaps.
- On resume (new chat or "Continue"), the ledger says exactly where to carry on.

## 5. Gates
- **Stage 1 of the memory build (and the reading step of an update) is complete only when the ledger shows every file fully read and digested**, apart from files the user explicitly excluded (recorded with name and reason) or files waiting for conversion or splitting (listed as stop-now problems).
- No later stage starts before that.
- The review page starts with **Reading coverage**: files and parts read in full / total, lines read / total, exclusions. Anything below 100% without an agreed exclusion blocks approval.

## 6. Checks
- **Self-check (stage 7):** for at least 10 files, pick content from the **second half and the last lines**, and confirm the digest and the memory reflect it. Any miss means that file is re-read and its digest redone.
- **Use check:** every digest is used by at least one memory statement, or is marked "no relevant content" with a reason. Unused digests are listed on the review page.
- **The BRD Reviewer** (`/brd-check`) re-checks a sample the same way.
