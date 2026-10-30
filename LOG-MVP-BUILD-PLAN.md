# LOG App MVP — Build Plan and Current Status

Last reconciled: 2026-10-19.

## Objective and scope

Open a project, talk to an AI grounded in its files, and approve updates without losing previous versions. LOG Specification v0.2 remains the broader product specification; v0.1 preserves the original requirements. Neither specification is a delivery-status report.

The current app is for one person on their Mac. It runs at http://127.0.0.1:8765 and reads `/Users/loghlenrickard/Desktop/LOG`. The app code is in `/Users/loghlenrickard/Desktop/LOG/log-app`. `Open LOG.command` in the Desktop LOG folder starts or opens it, together with the LOG connection on 127.0.0.1:8766. Family Holidays and Italy Trip remain fictional demonstration projects.

## Current status

**Working core prototype; original minimum viable LOG incomplete; long-term memory promise unproven.** Milestone headings below describe scoped implementation work, not full acceptance of the original specification. Use the [requirements and acceptance checklist](/Users/loghlenrickard/Desktop/LOG/LOG-REQUIREMENTS-CHECKLIST.md) as the requirement-by-requirement baseline (canonical location: Desktop/LOG/LOG-REQUIREMENTS-CHECKLIST.md).

The core workflow is implemented and the user has confirmed it works: read project context, discuss it, propose file changes, review and approve them, then recover the saved information in a fresh conversation. OpenAI connection persistence is implemented using macOS Keychain, and the user confirmed setup worked.

There is one Send button. Enter sends; Shift + Enter adds a line. Questions receive answers; requests to update project information can produce reviewable proposals. Sending a message never approves a file change.

## Milestone 1 — Project browser: partial against original requirements

Discover local projects, navigate parent/child folders, display summaries and pending decisions from control files, preview text, and view Markdown as rendered text or source. Missing control files produce warnings. The overview reflects recorded information; it does not independently validate completeness or accuracy.

The folder hierarchy is read from disk. Plain-text search of project names and text files was added on 2026-10-19 (MVP-11). An in-app folder picker and an arbitrary nested-folder browser are not implemented.

## Milestone 2 — Revision-backed editing: delivered for app-managed Markdown

Create projects and child projects with the three LOG files. Edit Markdown, preserve local Git checkpoints, compare revisions, restore earlier text as a new revision, and block stale saves. Edits made outside LOG are checkpointed before the next app edit, not continuously watched.

Git history is local; no GitHub synchronization is configured. Revision identifiers are commit IDs, not automatic major.minor.patch filenames. Commits identify LOG Local rather than authenticated individual collaborators. Ordinary binary files can live in the folders, but the app does not interpret them or automatically version every arbitrary artifact.

## Milestone 3 — Project-aware AI: partial

OpenAI chat includes the active project's three control files, selected additional text files, and recent conversation history. Parent control files are explicitly opt-in. Sources are cited and their hashes retained with conversations. The user has confirmed live OpenAI use.

The connection is saved in macOS Keychain and restored on startup. Forget saved connection removes the saved credential. Keys are excluded from project files, Git, browser storage, and API responses.

The current provider is OpenAI. A provider-selection interface and progressive retrieval of only relevant sections are not implemented. All selected source files are loaded within a fixed context limit. This is single-user context scoping, not a multi-user permission framework.

## Milestone 4 — Reviewed AI edits: delivered for existing selected Markdown

AI proposals include the target path, reason, complete before/after text, and highlighted differences. Review changes opens Approve and save this file, Reject change, or Review later. Approval applies to one file at a time and checks the original content hash. Stale proposals are blocked. Previous contents remain in history.

Only existing supplied Markdown files directly in the active project are eligible. Parent sources remain read-only. The AI cannot create, delete, rename, or automatically approve files. Pending and reviewed proposals persist in conversations. Approved contents and the review record are committed together; tested persistence failures roll back both. A machine/process crash during multiple file writes is not a filesystem-wide atomic transaction.

## Milestone 5 — Parent context and memory: partial

Delivered: opt-in parent context, saved conversations, user-requested proposals to update current status and durable memory, and continuity in a fresh conversation, confirmed by the user.

Delivered now: a dedicated Review project memory workflow using the current selected files and up to five explicitly selected project conversations. It proposes current-status updates, durable knowledge, and stale/conflicting-context corrections for per-file approval, and can suggest child projects in its answer. It starts a separate saved review conversation. Only LOG_STATUS.md and LOG_PROJECT.md can be changed through this review. Oversized input selections are rejected visibly.

Still deferred: systematic automatic end-of-session reviews, background maintenance, automatic archiving, and creation of suggested child projects. Important information left only in a conversation is not automatically added to project memory. The new workflow has automated and disposable browser verification, and the user confirmed a successful live run. Limited synthetic acceptance tests now cover relevance, classification and staged exact-copy promotion; review coverage and broader reliability remain incomplete. There is no durable record of which evidence has already been reviewed or still needs attention.

## Milestone 6 — Connected AI: built and tested locally, not online

Delivered: the LOG connection, an MCP server (protocol 2025-11-25) with OAuth 2.1 sign-in, built with the Python standard library. Any assistant that supports MCP can list, open, read and search the projects the user turns on, and propose file changes, memory updates (staged exact-copy promotion) and new child projects. It cannot write files. Proposals go through the same review dialog, review records and Git history as the built-in chat, from a new Connected AI page that also handles sign-in codes, project access, the connection password and disconnecting.

Since then: online at https://log.aisteer.org through a Cloudflare Tunnel (2026-10-20); Claude, ChatGPT and Codex connected, and ChatGPT passed the handover test through it (2026-10-21 to 22); any assistant can read LOG's rules with get_rules (2026-10-23); connected assistants can send session records, saved after approval (2026-10-23). Gemini is not wanted for now. Not supported: Client ID Metadata Documents, streaming responses, more than one user. Details: [app README](log-app/README.md#connected-ai) and [acceptance results](log-app/acceptance/connection-2026-10-19/results.md).

## Milestone 7 — The rest of the minimum version: delivered 2026-10-23

Delivered:
- **Folders (MVP-07).** Folders that are not projects appear under Project files. Text files preview; documents, images and media open in their own app; any file can be shown in Finder; scripts and apps are never opened.
- **README for new projects (MVP-03).** New projects' READMEs record purpose, owner (from the parent or root), collaborators, parent, scope, out of scope, permissions, information sharing, expected structure, operating rules with a link to the AI rules, and the creation date.
- **Pending decisions (MVP-10).** A Pending decisions page lists each project's open decisions from its status file and its decided items from its project file, and flags pending items that look already decided.

With this, all 15 items of v0.1 §28 are demonstrated, several with stated limits. Details: [acceptance results](log-app/acceptance/minimum-items-2026-10-23/results.md).

## Original-spec coverage and remaining work

The file-based foundation, hierarchy, AI reading, approved AI updates, and recoverable history are working. The broader organization system remains incomplete:

- Plain-text search across project names and text files works (.md, .txt, .csv, .json up to 1 MB). Semantic search and searching inside PDFs or Office files are absent.
- Arbitrary document storage is supported by the filesystem; in-app import and binary-document understanding are absent.
- Lifecycle controls now cover active, pending, blocked, completed and archived, with reviewed file updates and archive visibility. Archiving retains the existing folders; broader archival policy remains future work.
- Files are portable. Any assistant that supports MCP can work with chosen projects through the LOG connection (not yet online); the built-in chat uses OpenAI only.
- Automatic memory promotion, stale-project detection, duplicate detection, and restructuring suggestions are absent.
- A root LOG project exists (2026-10-19); its LOG_STATUS.md is the current overview. A fuller system-wide memory view is absent.
- New projects record owners, collaborators and access as text; identity and permission enforcement are absent, except per-project access for connected AI assistants.
- The app has a project tree, project overview, folder browsing and a Pending decisions view, not a system-wide timeline or relationship graph.

## Next steps

Current priorities and next actions live in the root [LOG_STATUS.md](LOG_STATUS.md), following the plan agreed on 2026-10-19. Use the checklist IDs and record acceptance evidence before marking requirements complete.

More prominent active-project labels were suggested after the Family Holidays mix-up; the user elected to leave the interface as it is for now.

## Deferred broader capabilities

Multi-user collaboration, SSO, GitHub synchronization, Google Drive and SharePoint connectors, hosted access beyond the LOG connection, scheduled agents, generated dashboards, external actions, semantic version numbering, history pruning, and other AI providers inside the built-in chat.

## Verification and practical limits

- Latest completed automated run: 128 tests passed (2026-10-23), covering connection sign-in, tokens, project access, proposals and session records, lifecycle, search, real-Git saves, restoration, conflicts, scoped chat, proposal approval/rejection, duplicate approval, rollback, credential lifecycle behavior, and memory-review scope, limits, target enforcement, and duplicate-request handling. OpenAI transport is mocked in these tests.
- Browser checks verified editing/history, proposal review and approval on disposable data, the single Send button, Enter to send, Shift + Enter for a newline, and selected-conversation memory review returning pending proposals.
- Native macOS Keychain verification used a disposable dummy credential to test create, read from a separate process, replace, and remove.
- The user confirmed live OpenAI chat, the project-update workflow, fresh-conversation continuity, saved-connection setup, and a successful memory-review run. These checks are not a long-term or multi-provider evaluation of the original product promise.
- The accidental Family Holidays approvals were reversed; review records now retain the original approval with a dated reversal annotation. Parent budget references now link to the child’s authoritative files.

The app coordinates its own writes. External editors do not share its lock; avoid simultaneous saves through different applications. It is a local prototype, not a multi-user hosted service.

## Consistency corrections

Parent budget references now link to Italy’s authoritative files. Reversed approvals retain dated undo annotations. The Rome decision is dated from its original conversation; the AI now receives the local date and Git status, and memory review flags stale no-history claims. The itinerary card survives heading changes. Regression tests and a browser check passed. Maintain this single build plan; detailed evidence stays in the linked reports.

## Acceptance evidence

Historical reports: [initial memory evaluation](LOG-MEMORY-ACCEPTANCE-2026-10-19.md), [rejection persistence](LOG-REVIEW-RECORD-RETEST-2026-10-19.md), and [promotion workflow, tests and limits](LOG-MEMORY-PROMOTION-RETEST-2026-10-19.md). Earlier failures are historical; current scoped promotion and rejection guards have passing evidence. Review coverage, closing review and broader archival policy remain incomplete.
