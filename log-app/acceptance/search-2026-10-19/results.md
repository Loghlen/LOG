# Search acceptance — 2026-10-19

Requirements: MVP-11 (search projects) and ORG-04 (broader search). See the [requirements checklist](../../../LOG-REQUIREMENTS-CHECKLIST.md).

**Result: passed.** Run in a headless browser against a copy of the LOG folder at commit 27f7f1a plus the search change. No browser errors.

| Step | Expected | Observed |
|---|---|---|
| Search a known project name: "Italy Trip" | The project appears and opens | 1 project and 18 files found; clicking the project opened Italy Trip ([screenshot](1-project-name.png)) |
| Search a unique phrase in a control file: "fictional household, consisting of two adults" | Only that file, with the matching line; it opens | 1 result, `Family Holidays/LOG_README.md` line 20, highlighted; clicking opened the file and it contains the phrase ([screenshot](2-phrase.png)) |
| Search a nonexistent term: "zebra-free phrase" | An explicit empty state | "No matches", plus the number of files searched and the formats ([screenshot](3-empty.png)) |
| Search one character: "a" | A clear message, no search | "Type at least 2 characters." |
| Search while editing with unsaved changes | Draft protected | "Discard your unsaved changes?" was shown; dismissing it kept the editor open |
| Phone width (390 px) | No sideways scrolling | Page width stayed at 390 px |

Automated tests (`test_search.py`, 12 tests on real files and folders) cover:
- project names
- case and spacing differences
- an empty result
- hidden files, `.git` and symbolic links never searched
- unsupported, unreadable and over-1 MB files reported as not searched
- conversations searched once through their readable copy
- ranking
- changes made outside the app found on the next search
- input limits
- result limits
- long lines trimmed
- file-name matches
- the HTTP route

The full suite has 63 passing tests.

Script: [run_search_acceptance.py](run_search_acceptance.py). It expects a LOG app running on port 8798 and an output folder argument.

## Limits

- Plain text matching only. It finds the words typed, not their meaning; semantic search is optional in the spec and not built.
- Formats searched: .md, .txt, .csv and .json up to 1 MB. Other files (code, PDFs, images, Word or Excel files) are listed as "not searched".
- Results are capped at 200 matching lines, and 5 lines are shown per file.
- Every search reads the folder from disk. That is fast at the current size; a much larger folder may eventually need an index.

## Search corrections — 2026-10-19

Codex reproduced and fixed two edge cases: ordinary JSON files were skipped whenever a same-name Markdown file existed; Unicode case folding could position long-line snippets away from their match. Deduplication is now limited to recognized generated conversation/review copies with a readable Markdown twin. Unicode positions map back to the original text.

Three regression tests cover independent JSON twins (including in a conversations folder), an unreadable generated twin, and Unicode expansion before/inside matches. All 66 tests passed. The running app was restarted; Italy returned Italy Trip and 19 matching files over HTTP. No new live AI requests were made.
