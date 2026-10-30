# LOG local app

App source, tests and evidence live here. The canonical workspace is `/Users/loghlenrickard/Desktop/LOG`.

## Start

Open `../Open LOG.command`, or run `python3 server.py` from this folder. Open http://127.0.0.1:8765. Python 3 and Git are required; no third-party Python packages are needed. `--root` selects another data folder and `--port` selects another local port. Use `--init-history` only when initializing a new LOG-managed history.

## Use

Select a project to browse its files or open Chat. Enter sends; Shift+Enter adds a newline. Questions receive answers; requested edits produce proposals. Review the diff before approving each file. Sending never approves changes. Source selection is fixed for a conversation; start a new chat to change it. Parent context is opt-in.

Use Search in the sidebar to find project names and words in any text file in the LOG folder (.md, .txt, .csv and .json up to 1 MB), including specifications and saved conversations. Matching is plain text, ignoring case and extra spaces; nothing is sent to OpenAI. Results show the project, file and matching lines, and open the file when clicked. Files that are not searched are listed under the results. Search reads the files on disk each time, so changes made outside the app appear immediately.

Use Review project memory with up to five selected conversations. For promotion, approve the durable copy, then choose Review status cleanup and approve its separate diff. See the [promotion workflow and limits](../LOG-MEMORY-PROMOTION-RETEST-2026-10-19.md).

File history supports comparison and restoration as a new revision. Rejections are retained in project-local `reviews/` files. Exact repeated rejected edit patterns are blocked unless you explicitly select reconsideration. This is not semantic duplicate detection. Reversal annotations preserve the original approval and identify the later undo; they do not turn it into a rejection.

OpenAI settings saves the key and model in macOS Keychain. Startup restores them; Forget saved connection removes them. Credentials are not stored in project files, Git, browser storage or API responses. A restored credential is not automatically network-verified. Environment configuration is supported, with saved Keychain configuration taking precedence.

## Project status

Use Change status on a project overview, select Active, Pending, Blocked, Completed or Archived, and optionally explain why. Review the exact diff, then approve saving. This updates Lifecycle and Recently Updated in LOG_STATUS.md with recoverable history. A changed source blocks stale saves. Unknown or duplicate lifecycle sections are flagged; duplicate sections require a manual correction.

Archived projects and their own files are hidden from navigation and search by default. Select Show archived to find and reopen them. Active child projects remain visible; a parent status change does not alter children. Archiving does not move or delete any files, and existing direct links remain usable. This is a visibility preference, not an access restriction.

## Folders, new projects and decisions

- **Folders:** Project files lists folders that are not projects themselves. Text files (.md, .txt, .csv, .json) preview in LOG. Documents, images and media can be opened in their own app on the Mac. Any file can be shown in Finder. LOG never opens scripts, apps or installers.
- **New projects:** the New project dialog asks for an owner, filled in from the parent or root project. Under More details it also takes collaborators, scope and out of scope. The README records these with permissions, expected structure, a link to LOG's AI rules and the creation date.
- **Pending decisions:** the sidebar page lists each project's items under Pending Decisions in LOG_STATUS.md, with decided items from LOG_PROJECT.md. Pending items worded like a recorded decision are flagged for checking. It follows Show archived.

## Boundaries

This is a single-user local prototype. Keep it on loopback. There is no multi-user permission enforcement, remote synchronization, web research, automatic archival or history pruning. Selected control files and extra text are sent to OpenAI only on request, using Responses with `store: false`; this does not establish zero retention under all API policies. Context limits are 60,000 source characters, 24,000 history characters, 40 saved turns, and 16,000 output tokens for proposals. No streaming, cancellation or automatic retries are implemented.

AI edits target existing supplied Markdown files directly in the active project; parent files are read-only. Text/CSV/JSON preview is available up to 1 MB; binary interpretation is absent. The app checks file versions and rolls back handled save failures. External editors do not share its lock; multi-file writes are not crash-atomic. Git records the application identity, not authenticated individual collaborators. External edits are checkpointed at the next app save, not continuously watched.

The AI receives the local date and verified Git-enabled status. Historical decisions still require source dates. Memory review also flags known no-Git-history statements deterministically. Broader consistency remains subject to review. The itinerary card recognizes common outline headings and falls back to tables with City, Destination or Overnight base alongside Nights columns.

## Connected AI

The LOG connection lets any AI assistant that supports MCP (the Model Context Protocol) work with LOG: ChatGPT, Claude, Gemini, Cursor and others. Start LOG with `--connection` (the launcher does this); it listens on 127.0.0.1:8766 alongside the app. Only this port is meant to be published, for example through a Cloudflare Tunnel, with `--public-url https://your.domain` so sign-in addresses are correct. Never publish the app's own port (8765): it has no sign-in.

What a connected assistant can do:
- see only the projects ticked under **Connected AI → Projects AIs can see** (stored in `LOG-ACCESS.json`, versioned in Git)
- read LOG's rules for AI assistants (`LOG-AI-RULES.md`) with `get_rules`, whatever projects are on; the rules are also sent when an assistant connects, but some assistants, such as ChatGPT, do not pass those on to the model
- list and open those projects, read their text files and search them
- propose a file change, a memory update (exact-copy promotion rules apply) or a new child project
- propose a session record at the end of a conversation (summary, decisions the user confirmed, open questions, next steps). Once approved, it is saved as `conversations/session-<date>-<title>.md` in the project. It never changes the status or memory files.

It can never write files. Proposals appear under **Connected AI → Waiting for your approval** and use the same review dialog, review records and history as the built-in chat. A new project can be made visible to AIs as you approve it.

Sign-in uses OAuth 2.1 with PKCE and dynamic client registration. The assistant opens a LOG sign-in page; you enter the connection password, then the 6-digit code shown on the Connected AI page. Access tokens last an hour and refresh tokens rotate; a reused refresh token disconnects that assistant. Five wrong passwords, or ten wrong codes in an hour, lock sign-in for 15 minutes. Changing the connection password signs out every connected assistant. The password and tokens are stored only as hashes in `~/Library/Application Support/LOG/connection.json` (outside the LOG folder, readable only by you), with an activity log beside it. Disconnect any assistant from the Connected AI page.

Limits: single user; the Mac must be awake with LOG running; return addresses must be plain https addresses (or http on localhost), so app addresses such as `cursor://` are not accepted; Client ID Metadata Documents are not supported (assistants register themselves instead); responses are plain JSON (no streaming). Someone who finds the address can delay new sign-ins with wrong passwords; connected assistants keep working. Each assistant can have at most 25 proposals waiting. Evidence: [acceptance results](acceptance/connection-2026-10-19/results.md).

## Verification and status

Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s . -p 'test_*.py' -v` from this folder. Tests use disposable projects, mocked OpenAI transport and real Git. Live model checks are separate evidence, not a guarantee of judgment quality.

See the single [build plan](../LOG-MVP-BUILD-PLAN.md) for current status and latest test results, and the [requirements checklist](../LOG-REQUIREMENTS-CHECKLIST.md) for outstanding work. Detailed historical acceptance reports remain in the workspace root; do not copy their contents into this README.
