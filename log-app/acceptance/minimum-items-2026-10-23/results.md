# Minimum items acceptance — 2026-10-23

Requirements: MVP-07 (browse project folders), MVP-03 (generate LOG_README.md) and MVP-10 (identify pending decisions). See the [requirements checklist](../../../LOG-REQUIREMENTS-CHECKLIST.md).

**Result: passed on a copy of the LOG folder** in a headless browser, with no browser errors. The page also fits a phone-width screen (390 px) with no sideways scrolling. The script that ran the checks is [run_minimum_items_acceptance.py](run_minimum_items_acceptance.py).

## MVP-07: Browse project folders

| Step | Expected | Observed |
|---|---|---|
| Add `documents/` and `research/2026/` to Italy Trip, with a Markdown note, a PDF, a CSV and a shell script | Folders listed under Project files; child projects, hidden folders and linked folders are not | `conversations/`, `documents/`, `research/` (with `2026/`) and `reviews/` listed ([screenshot](1-folders.png)) |
| Open `documents/booking-notes.md` and `research/2026/fares.csv` | Previews | Both previewed ([screenshot](2-preview.png)); going back kept the open folders open |
| A PDF | An explicit native-file action | **Open** and **Show in Finder** offered |
| A shell script | Never run from LOG | Only **Show in Finder** offered; asking LOG to open it is refused |

**Not yet checked on the Mac:** in the test machine (Linux), Open and Show in Finder answer "Opening files in their own apps works on a Mac". The request path, its checks and the macOS command it sends are covered by automated tests.

## MVP-03: Generate LOG_README.md

Created **Taxes 2026** through the New project dialog. The owner was filled in from the root project's README, and collaborators and scope were entered under More details ([screenshot](3-new-project.png)). The [created README](3-README-created.md) has these sections:

- Purpose
- Owner
- Collaborators
- Parent Project
- Child Projects
- Scope
- Out of Scope
- Permissions
- Information Sharing
- Expected Structure
- Operating Rules
- Created

Together they cover title, purpose, scope, owner, creation date and parent (v0.1 §4 and §7). Collaborators and access are stated explicitly, either as entered or as "None recorded" / "no separate access is configured". Operating Rules links to the AI rules file. Every link in the file resolves.

## MVP-10: Identify pending decisions

A fixture project, Decision Test, had three items:
- one suggestion, under Suggestions in its status file
- one unanswered choice, under Pending Decisions
- one approved decision, in LOG_PROJECT.md

| Expected | Observed |
|---|---|
| Only the unanswered choice is shown as pending | "Which weekend should the move happen?" listed, with its file and line |
| The approved decision stays decided | "2026-10-23: Use a removal company" listed under Decided |
| The suggestion is not treated as a decision | "Maybe hire a van instead" appears nowhere on the page |

The new **Pending decisions** page in the sidebar shows this for every visible project, with a count ([screenshot](4-pending-decisions.png)). An item still listed as pending that closely matches a recorded decision is flagged for checking: the status file may simply not have caught up.

## Automated tests

Fourteen new tests, all failing on the code before the change:

- `test_folders.py` (4):
  - which folders are listed
  - nested previews
  - Open and Show in Finder, including refusing scripts, hidden files, links and paths outside the folder
  - same-origin protection for the open request
- `test_readme_template.py` (4):
  - every section
  - owner taken from the parent, then the root
  - given details
  - no root project
  - input checks
  - links that resolve
- `test_decisions.py` (6):
  - the acceptance fixture
  - the stale-pending flag
  - a related but different question not flagged
  - prose and fenced sections
  - archived projects
  - the HTTP route

The full suite has 128 passing tests.

## Limits

- Pending decisions are read from the Pending Decisions section. A choice discussed only in a conversation is not found until someone records it. Session records and memory review exist for that.
- The "already decided?" flag compares wording, so it can miss a decided item phrased differently, or rarely flag a related one. It only asks for a check; it changes nothing.
- Folder listings show up to 300 files per folder and six levels deep.
- New READMEs record ownership and access as text. Multi-user permissions are still not enforced (ORG-06).
