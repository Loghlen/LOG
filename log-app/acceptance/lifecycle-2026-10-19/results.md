# Lifecycle acceptance — 2026-10-19

MVP-08: demonstrated for the local app. Codex implemented and tested the user-approved status workflow. Tests use disposable projects, not holiday data.

- Full automated suite: 74 passing tests, including eight lifecycle tests.
- All five states save and reread through the catalog, retain unrelated content and Git history, and permit reopening archived projects.
- Preview alone makes no edits. A stale preview cannot overwrite external changes. Simulated commit failure preserves the previous status.
- Missing/unknown/duplicate lifecycle sections are recognized; legacy “Active — early planning” reads as active. Unsupported values and heading injection in the reason are rejected. Fenced examples remain unchanged.
- Search hides archived projects and their own files unless Show archived is enabled. Active children remain searchable when a parent is archived.
- Browser fixture: pending, blocked, completed, archived and active transitions; separate review and approval; default archive hiding after reload; active child remains visible; Show archived and reopening; cancellation; changing the reason invalidates the preview. No browser JavaScript errors.

The browser fixture used actual app routes on port 8799. The automated suite uses real temporary files and Git. No OpenAI calls were made. Production project statuses were not changed for testing.

Archiving is a visibility setting, not file relocation, deletion or access control. Direct links and explicit reads still work. A refresh loads outside edits. Parent/child state is intentionally independent. All existing limitations around concurrent external editors and multi-file crash atomicity still apply.
