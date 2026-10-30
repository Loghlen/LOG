# LOG Specification v0.2

Revision date: 2026-10-19

This version extends v0.1 with requirements for configurable architecture, storage access, optional Git collaboration, document revisions, evidence-based comparisons, retention, generated views, and concurrent editing. LOG-SPEC-v0.1.md remains a separate historical document.

In this specification, MUST indicates a requirement, SHOULD indicates a recommended default, and MAY indicates an optional capability. Requirements explicitly scoped to versioned or Git-backed operation do not require Basic LOG to implement revision history.

## 1. Overview

LOG is a file-based organization and memory system for AI-assisted work.

The purpose of LOG is to make projects understandable, portable, and persistent across time, people, and AI systems.

AI users can create large amounts of work very quickly, but that work often becomes fragmented across conversations, tools, documents, and models. LOG provides a common project structure that keeps the important context organized and understandable.

A LOG project should be readable by:

- A human
- An AI assistant
- A different AI assistant than the one that created it
- Another collaborator joining the project later
- Software that indexes, visualizes, or searches the project

The canonical source of truth in LOG is its project files and their declared authoritative storage locations. These may be local folders, repository files, or cloud-hosted folders and documents. Indexes and generated views remain secondary representations.

LOG may use databases, indexes, embeddings, caches, or other infrastructure for performance, but these are secondary representations.

If the database disappears, the LOG project should still make sense.

---

# 2. Core Principles

## 2.1 Files are the source of truth

Projects are folders.

Knowledge is primarily represented through normal files.

Examples:

- Markdown
- CSV
- PDF
- DOCX
- XLSX
- PPTX
- Images
- Code
- JSON
- Audio
- Video
- Other native file formats

LOG should not require important project information to exist only inside a proprietary database.

---

## 2.2 Human readable by default

A person should be able to open a LOG project folder and understand:

- What the project is
- Why it exists
- What is happening now
- What has happened historically
- What remains unresolved
- What files matter
- What related projects exist

The user should not need the LOG application to understand their project.

---

## 2.3 AI independent

Project context belongs to the project, not the AI provider.

A user should be able to work with:

- ChatGPT
- Claude
- Gemini
- Local models
- Future AI systems

without rebuilding the project's context from scratch.

An AI opening a LOG project should be able to reconstruct enough context from the project files to continue useful work.

---

## 2.4 Progressive memory

LOG should not treat all information equally.

Information moves through different levels of relevance.

The core model is:

Raw information → Current context → Durable knowledge

LOG therefore distinguishes between:

1. Raw project artifacts
2. Short-term project memory
3. Long-term project memory

---

## 2.5 Projects should self-organize

Projects should remain understandable as they grow.

When a project becomes too large, complicated, repetitive, or conceptually distinct, LOG should encourage or automatically suggest creating child projects.

A project should not become an infinitely growing folder or markdown file.

---

# 3. The Project

The fundamental unit in LOG is a Project.

A Project is represented as a directory.

Example:

```text
Apartment-Search/
```

Every active LOG Project should contain, at minimum:

```text
Apartment-Search/
    LOG_README.md
    LOG_STATUS.md
    LOG_PROJECT.md
```

Additional files and directories may be added freely.

Example:

```text
Apartment-Search/
    LOG_README.md
    LOG_STATUS.md
    LOG_PROJECT.md

    listings.csv
    budget.xlsx

    research/
    conversations/
    documents/
    images/
```

---

# 4. Project Identity

Every Project has:

- Title
- Purpose
- Parent
- Optional children
- Owner
- Optional collaborators
- Status
- Creation date
- Optional completion date
- Access rules
- Relevant relationships to other projects
- Project-scoped assistant context and delegated access
- User-dependent information-sharing rules for parent, child, and related projects

A Project should have exactly one primary parent unless it is the root LOG project.

A Project may reference other projects without making them parents. Relationships establish routes for information requests, not automatic access grants. Section 40 defines the permission and information-sharing framework.

---

# 5. Parent and Child Projects

Projects form a hierarchy.

Example:

```text
Scott/
    Expenses/
        2026/
            January/
            February/
            March/
```

Another example:

```text
Scott/
    To-Do/
        Taxes/
            2025 Taxes/
            2026 Taxes/

        Find NYC Apartment/
```

Parent-child relationships represent organizational ownership, not necessarily file dependencies.

A parent project should provide broader context.

A child project should represent a more focused unit of work.

---

## 5.1 When to create a child project

A child project should be considered when:

- The work has its own clear objective
- The work has its own lifecycle
- The project contains too much information to remain easily understandable
- A recurring activity produces multiple instances
- Different collaborators own different parts of the work
- Different permissions are required
- A major workstream can be understood independently
- The project needs its own LOG_STATUS.md

Example:

```text
Taxes/
    2025 Taxes/
    2026 Taxes/
```

"Taxes" is ongoing.

"2026 Taxes" has a specific lifecycle and completion condition.

---

# 6. Required Project Files

Every LOG Project contains three primary control files.

```text
LOG_README.md
LOG_STATUS.md
LOG_PROJECT.md
```

Each has a distinct purpose.

They should not become interchangeable.

---

# 7. LOG_README.md

## Purpose

`LOG_README.md` defines the identity, scope, rules, ownership, and structure of the Project.

It should change relatively infrequently.

It answers:

> What is this project?

---

## Recommended structure

```markdown
# Project Title

## Purpose

Why this project exists.

## Owner

Primary owner.

## Collaborators

People or agents involved.

## Parent Project

Reference to parent.

## Child Projects

References to known children.

## Scope

What belongs inside this project.

## Out of Scope

What should not be stored here.

## Permissions

Who can:
- View
- Edit
- Contribute
- Use information from this project

## Project Assistant

Default project context, operating instructions, and delegated access scope.

## Related Projects

References to related projects and the purpose of each relationship.

## Information Sharing

Rules for information entering or leaving this project, including:
- The authenticated users or groups to whom each rule applies.
- Source and destination projects, permitted relationship routes, and allowed information scope.
- Separate permissions to discover, read, use, persist or share, and write information.
- Permitted destination audiences and any conditions on derived summaries.
- Explicit delegation for broader user-scoped retrieval, if enabled.

These declarations follow section 40 and cannot expand permissions granted by the underlying storage. Unspecified cross-project access is denied by default.

## Expected Structure

Any expected files, directories, or child projects.

## Operating Rules

Rules that humans and AI systems should follow when working with this project.

## Created

YYYY-MM-DD
```

---

# 8. LOG_STATUS.md

## Purpose

`LOG_STATUS.md` represents the project's short-term working memory.

It contains the information someone needs to understand what is happening right now.

It should be concise enough that an AI or human can read it frequently.

It answers:

> What is currently going on?

---

## LOG_STATUS.md should contain

- Current summary
- Recent important activity
- Current priorities
- Active tasks
- Open questions
- Pending decisions
- Decisions requiring human confirmation
- Blockers
- Relevant deadlines
- Recently changed information
- Immediate next actions
- Important temporary context

---

## Recommended structure

```markdown
# Current Status

## Summary

Short description of the current state of the project.

## Current Priorities

- Priority 1
- Priority 2
- Priority 3

## Recent Developments

- Development
- Development

## Pending Decisions

- Decision requiring confirmation

## Open Questions

- Question

## Blockers

- Blocker

## Next Actions

- Action
- Action

## Relevant Current Files

- [File](path)
- [File](path)

## Recently Updated

YYYY-MM-DD HH:MM
```

---

# 9. LOG_PROJECT.md

## Purpose

`LOG_PROJECT.md` represents the durable memory of the Project.

It contains information that remains useful beyond the current working session.

It answers:

> What do we know about this project over its lifetime?

---

## LOG_PROJECT.md should contain

- Important historical context
- Major milestones
- Confirmed decisions
- Important facts
- Lessons learned
- Key assumptions
- Long-term project structure
- Important references
- Significant changes
- Links to important artifacts
- Relationships to subprojects

It should not contain every conversation or every minor event.

---

## Recommended structure

```markdown
# Project History

## Overview

Durable summary of the project.

## Important Facts

- Fact
- Fact

## Decisions

### YYYY-MM-DD: Decision Title

Decision:

Reason:

Impact:

## Milestones

### YYYY-MM-DD

Milestone description.

## Key Learnings

- Learning
- Learning

## Important Artifacts

- [Document](path)
- [Dataset](path)

## Child Projects

- [Child Project](path)

## Historical Notes

Relevant durable project history.
```

---

# 10. Memory Model

LOG uses three primary memory layers.

## Layer 1: Raw Memory

Raw project information.

Examples:

- Conversations
- Files
- Meeting transcripts
- AI outputs
- Research
- Emails
- Documents
- Drafts
- Data
- Images

Raw memory preserves source material.

It does not imply importance.

---

## Layer 2: Short-Term Memory

Stored primarily in:

```text
LOG_STATUS.md
```

This contains information relevant to the present state of the Project.

Short-term memory should be actively maintained.

Old or irrelevant information should be:

- Removed
- Archived
- Promoted to LOG_PROJECT.md
- Moved into a child project

---

## Layer 3: Long-Term Memory

Stored primarily in:

```text
LOG_PROJECT.md
```

Long-term memory contains information judged to be durable.

Examples:

- Important facts
- Confirmed decisions
- Significant outcomes
- Long-term preferences
- Project history
- Reusable knowledge

---

# 11. Information Lifecycle

Information should move through LOG deliberately.

The basic process is:

```text
New information
      ↓
Raw source
      ↓
Evaluate relevance
      ↓
Currently important?
      ↓
LOG_STATUS.md
      ↓
Durable?
      ↓
LOG_PROJECT.md
```

Not all raw information should be summarized.

Not all short-term information should become long-term memory.

---

# 12. Memory Promotion

LOG should periodically evaluate short-term information.

Possible outcomes:

### Keep in LOG_STATUS.md

The information remains currently relevant.

### Promote to LOG_PROJECT.md

The information has lasting value.

### Archive

The information may matter historically but is no longer immediately useful.

### Delete

The information has no ongoing value and is safe to remove.

### Move to a child project

The information belongs to an emerging independent workstream.

---

# 13. Human Confirmation

AI systems must distinguish between:

- Observations
- Suggestions
- Inferences
- Confirmed facts
- Confirmed decisions

An AI should not silently convert a suggestion into a confirmed decision.

Example:

```markdown
## Pending Decisions

- APPROVAL REQUIRED: Increase annual software budget to $20,000.
```

Once confirmed:

```markdown
## Decisions

### 2026-10-19: Software Budget

Approved annual software budget of $20,000.
```

This distinction is critical.

---

# 14. Fact Handling

LOG should attempt to preserve provenance.

Important facts should ideally reference their source.

Example:

```markdown
- Office lease expires March 31, 2027.
  Source: `documents/lease.pdf`
```

Where appropriate, LOG should distinguish:

```text
FACT
ASSUMPTION
INFERENCE
SUGGESTION
DECISION
QUESTION
```

These do not necessarily need to be implemented as visible labels everywhere, but the underlying distinction should exist.

---

# 15. Versions

## 15.1 Operating modes

LOG MUST support a basic file-and-folder structure without requiring Git, a database, or document revision history.

Three configurations are defined:

- **Basic LOG:** Ordinary project files and folders. Revision history may be disabled explicitly; rollback is then not guaranteed.
- **Versioned LOG:** Previous document contents are preserved through revision files, snapshots, or a storage provider's revision mechanism, without requiring Git.
- **Git-backed LOG:** Project files are maintained in a Git repository. GitHub MAY provide remote storage and collaboration, but GitHub is not required to use Git.

LOG editing clients SHOULD enable version preservation by default. A project may explicitly opt out. The active mode and retention policy MUST be discoverable in project files, such as the Operating Rules section of `LOG_README.md`.

## 15.2 Preserve revisions during work

When versioning is enabled, a client MUST preserve the previous contents before replacing a document with a meaningful saved edit. A meaningful saved edit is an accepted AI edit, explicit user save, or configured autosave checkpoint; it does not require a new version for every keystroke.

Each revision MUST have a unique reference, a timestamp, its predecessor reference when available, and the responsible user or agent identity when known. Unknown authorship MUST be identified as unknown rather than inferred. A change summary SHOULD accompany each revision.

A revision identifier alone is not preservation: the referenced content MUST remain recoverable under the declared retention policy. If preservation fails, the client MUST not silently overwrite the previous version.

## 15.3 Document version numbering

User-facing document versions SHOULD use three nonnegative integer components: `major.minor.patch`.

- **Major:** A substantial change in purpose, structure, or an established baseline. Increment major and reset minor and patch to zero.
- **Minor:** A substantive addition or revision within the same overall purpose. Increment minor and reset patch to zero.
- **Patch:** A small correction or refinement. Increment patch only.

Example working sequence: `1.1.0` → `1.1.1` → `1.1.2` → `1.2.0`.

These are document conventions, not a claim of software API compatibility. Version numbers MUST not be reused for different contents of the same document. Concurrent drafts MUST also have distinct revision identifiers; a version label alone is insufficient to identify them.

Draft, approved milestone, and superseded are separate document states. Increasing a version number MUST NOT imply human approval. Document state is distinct from the project lifecycle in section 20.

## 15.4 Filenames and current versions

The canonical control filenames MUST remain `LOG_README.md`, `LOG_STATUS.md`, and `LOG_PROJECT.md`. Their history may be stored separately or in Git.

Working documents MAY use versioned filenames, for example `proposal-v1.1.2.md`, or a stable current filename with separately preserved revisions. The project MUST identify the current working revision and, when applicable, the approved milestone revision through readable project files or a revision manifest. The newest timestamp MUST NOT automatically imply approval.

## 15.5 Comparison and restoration

Versioned clients MUST allow users to retrieve, compare, and restore retained revisions, and inspect available authorship and timing information.

Comparisons MUST use the actual stored contents of both identified revisions. AI may explain a computed comparison but MUST NOT use conversation memory as evidence of what changed. A comparison MUST identify its two source revisions. If a format cannot be compared reliably, the client MUST state that limitation and provide the originals; it MUST NOT invent a detailed difference.

Restoring an earlier revision SHOULD create a new current revision recording the restoration rather than erase later history.

## 15.6 Finalization and retention

During active work, LOG SHOULD preserve frequent checkpoints. When work is finalized or summarized into durable memory, LOG MAY reduce visible draft clutter and highlight approved milestones.

A configurable policy may show three milestone versions while archiving intermediate drafts. Three is an example preference, not a fixed limit. Archiving or hiding revisions MUST be distinguished from deleting their recoverable contents.

Summarizing a document into `LOG_PROJECT.md` MUST NOT itself authorize deletion of its revisions. Destructive pruning requires an explicit retention policy or user instruction and MUST disclose its effect on rollback. Ordinary Git cleanup MUST NOT rewrite committed history merely to reduce visible draft clutter.

---

# 16. AI Project Opening Procedure

When an AI begins working on a LOG project, it should not immediately load every file.

Required access precondition: Before loading project content, LOG MUST establish the authenticated user, active project, session audience, and assistant delegation through its access layer. A name stated in a prompt is not authentication. Only authorized content may enter the session. See section 40.

Recommended process:

### Step 1

Read:

```text
LOG_README.md
```

Understand identity, scope, ownership, assistant instructions, and information-sharing rules. Metadata informs the workflow; the access layer enforces permissions.

### Step 2

Read:

```text
LOG_STATUS.md
```

Understand current state.

### Step 3

Read relevant sections of:

```text
LOG_PROJECT.md
```

Understand durable context.

### Step 4

Inspect the files relevant to the user's current task.

### Step 5

Request relevant information from parent, child, or related projects only when necessary and authorized under section 40. Do not load entire related projects merely because a relationship exists.

This creates progressive context loading rather than blindly filling the AI context window.

---

# 17. AI Project Closing Procedure

After meaningful work, the AI should evaluate whether LOG needs updating.

Questions:

1. Did the current state change?
2. Was a decision made?
3. Was an important fact discovered?
4. Was a new file created?
5. Did a task become blocked?
6. Was a task completed?
7. Should something move from LOG_STATUS.md to LOG_PROJECT.md?
8. Does the project now need a child project?
9. Is anything in LOG_STATUS.md stale?

The AI should update the appropriate files.

---

# 18. Context Portability

A key requirement of LOG is AI portability.

A different AI should be able to enter an existing project and continue working without access to the previous model's internal memory.

Therefore:

Important project context must not exist exclusively in:

- Chat history
- Model memory
- Hidden prompts
- Embeddings
- Application databases

Anything required to continue the project should eventually be represented in the LOG filesystem.

---

# 19. Links Between Projects

Projects may reference other projects.

Example:

```markdown
## Related Projects

- [2026 Taxes](../Taxes/2026/)
- [NYC Apartment Search](../Apartment-Search/)
```

A link does not imply parent-child ownership.

Relationships may eventually support types such as:

```text
parent
child
related
depends-on
blocked-by
source
supersedes
```

Only `parent` and `child` are required for v0.2.

---

# 20. Project Status

Every project should have a lifecycle state.

Initial supported statuses:

```text
active
pending
blocked
completed
archived
```

### Active

Currently being worked on.

### Pending

Waiting for a future event, person, or condition.

### Blocked

Cannot currently proceed.

### Completed

The objective has been achieved.

### Archived

No longer active but retained for historical or reference purposes.

---

# 21. Recurring Projects

Some projects repeat indefinitely.

Example:

```text
Taxes/
```

with children:

```text
2025 Taxes/
2026 Taxes/
2027 Taxes/
```

The parent remains active while individual instances can be completed.

Other examples:

```text
Expense Reports/
Weekly Planning/
Annual Insurance Renewal/
Hiring/
```

---

# 22. Temporary Projects

Some projects exist only until a condition is met.

Example:

```text
Find NYC Apartment/
```

Possible lifecycle:

```text
active
→ pending
→ active
→ completed
→ archived
```

Completion occurs when the user finds and secures an apartment.

---

# 23. Root LOG Project

Every LOG environment has one root project.

Example:

```text
LOG/
```

The root is the ancestor of all primary projects.

It may contain:

```text
LOG/
    LOG_README.md
    LOG_STATUS.md
    LOG_PROJECT.md

    Work/
    Personal/
    Finance/
    Projects/
```

The root LOG project should provide a high-level view of the user's entire system.

---

# 24. LOG Manager

The LOG Manager is the system responsible for understanding and maintaining the project hierarchy.

Responsibilities may include:

- Creating projects
- Creating child projects
- Updating project files
- Finding relevant projects
- Searching files
- Surfacing important information
- Detecting stale projects
- Detecting duplicate projects
- Suggesting restructuring
- Promoting memory
- Archiving stale information
- Maintaining cross-project awareness

The LOG Manager itself should not become the sole source of truth.

Its understanding should be recoverable from the project filesystem.

---

# 25. Organization vs Database

LOG may use a database.

However:

The database is an index.

The files are the knowledge.

For example, a database might contain:

```text
project_id
project_title
status
owner
file_path
last_modified
embedding
relationships
```

But deleting that database should not destroy the logical meaning of the project.

It should be possible to rebuild the database from the files.

---

# 26. Search

LOG should eventually support search across:

- File names
- File contents
- Projects
- LOG_STATUS.md
- LOG_PROJECT.md
- Raw artifacts
- Metadata
- Related projects

Search may use:

- Traditional text search
- Structured filters
- Semantic search
- Embeddings
- AI interpretation

Search infrastructure is not part of the canonical storage format.

---

# 27. Visualization

LOG should provide visual representations of the underlying filesystem.

Possible views:

### Project Tree

```text
LOG
├── Work
│   ├── Company
│   └── Hiring
├── Finance
│   ├── Expenses
│   └── Taxes
└── Personal
    └── Apartment Search
```

### Current Work

Projects grouped by status.

### Project Graph

Shows relationships between projects.

### Timeline

Shows project activity over time.

### Pending Decisions

Shows decisions requiring human input.

### Recent Changes

Shows what changed across LOG.

These are visualizations of project state.

They are not the canonical project state.

Projects MAY have multiple simultaneous views, including dashboards, observatories, generated reports, and static HTML. A view MAY use a fixed application, a template, or an AI-generated design requested for a particular task. No single framework, database, or visualization is required. Section 37 defines refresh and provenance requirements.

---

# 28. Minimum Viable LOG

The first usable implementation should support:

1. Create Project
2. Create child Project
3. Generate LOG_README.md
4. Generate LOG_STATUS.md
5. Generate LOG_PROJECT.md
6. Store arbitrary files
7. Browse project folders
8. Update project status
9. Summarize project state
10. Identify pending decisions
11. Search projects
12. Allow an AI to read project context
13. Allow an AI to update project context
14. Preserve document history when versioning is enabled (the default for editing clients)
15. Navigate parent and child projects

Everything beyond this can be layered on later.

---

# 29. Example Project

```text
Find-NYC-Apartment/
│
├── LOG_README.md
├── LOG_STATUS.md
├── LOG_PROJECT.md
│
├── listings.csv
├── budget.xlsx
│
├── listings/
│   ├── 123-west-12th.md
│   ├── 81-irving-place.md
│   └── 44-west-87th.md
│
├── documents/
│   ├── employment-letter.pdf
│   └── bank-statement.pdf
│
└── research/
    └── neighborhoods.md
```

Example `LOG_STATUS.md`:

```markdown
# Current Status

## Summary

Searching for a one-bedroom apartment in Manhattan.

Target move date is December 1.

Currently comparing three apartments.

## Current Priorities

1. View West 12th Street apartment.
2. Confirm total monthly cost for Irving Place.
3. Decide whether Upper West Side should remain in search.

## Pending Decisions

- Whether to increase maximum rent from $4,500 to $4,800.

## Next Actions

- Schedule West 12th viewing.
- Contact Irving Place broker.
```

When the apartment is secured:

```text
status = completed
```

Important lessons, final costs, selected apartment, and decisions move into `LOG_PROJECT.md`.

The project can then be archived.

---

# 30. Design Constraints

LOG should optimize for:

- Understandability
- Portability
- Recoverability
- AI interoperability
- Human inspection
- Version history
- Incremental context loading
- Long-term durability

LOG should avoid:

- Hidden critical state
- Mandatory proprietary formats
- Infinite context files
- AI-specific lock-in
- Dumping every conversation into long-term memory
- Treating every piece of information as equally important

---

# 31. Core Product Promise

LOG should make the following interaction possible:

A user works on a project for six months using multiple AI systems.

They stop working on it for three months.

They return using a completely different AI.

The AI opens the LOG Project, reads the project structure and memory files, and can accurately answer:

- What is this?
- Why are we doing it?
- What has happened?
- What matters right now?
- What decisions have been made?
- What decisions remain?
- What should happen next?

without requiring the user to manually reconstruct the history.

If LOG can reliably do that, the core system is working.

---

# 32. LOG Philosophy

LOG is not trying to replace the filesystem.

LOG makes the filesystem intelligent.

It adds enough structure that humans and AI systems can maintain shared understanding across time without turning the user's work into an opaque database.

The filesystem remains the durable layer.

AI provides interpretation.

LOG provides organization.

---

# 33. Independent Architecture Layers

LOG separates four independently configurable responsibilities:

1. **Information structure:** Project folders, control files, relationships, provenance, and memory-management rules.
2. **Storage:** The authoritative locations holding project files and documents.
3. **AI interaction:** Assistants and workflows that read, interpret, propose changes, and maintain information.
4. **Presentation:** Views generated from authorized project information.

Changing an AI provider or presentation MUST NOT require changing the canonical LOG structure. Storage integrations MUST preserve that structure or provide a documented, human-readable mapping and export.

AI interaction policies MAY differ by project, including when to summarize, when to request human decisions, and when to generate views. Those policies MUST remain discoverable in project files and MUST respect storage permissions and the distinction between suggestions and confirmed decisions.

---

# 34. Storage Connectors and Hosted Access

## 34.1 Hosting model

The LOG web interface, its processing service, and project storage MAY be hosted separately. A hosted service accesses user-selected storage through an authorized connector; it does not gain access merely because a folder exists on a user's computer.

Supported architectural integration targets are:

| Storage | Access model |
|---|---|
| Local folders | A desktop client or local service authorized to access the selected project root |
| Company file server | A service running where that filesystem is accessible, under the company's access rules |
| Git repository / GitHub | An authorized repository connection; a GitHub App is a possible hosted integration |
| Google Drive | An authorized connector for files and folders, with explicit handling for native Google documents |
| SharePoint / OneDrive | An authorized connector for document libraries, folders, and files |

A deployment MAY implement a subset of these targets. Defining the integration contract does not require implementing all providers in the initial release.

## 34.2 Connector contract

A connector MUST declare which operations it supports, including:

- Listing folders and identifying files by stable provider identifiers where available.
- Reading content and returning its source location and revision token or content hash.
- Creating files and saving changes against an expected prior revision.
- Retrieving history, comparing versions, and restoring revisions where supported.
- Detecting changes through notifications or polling where supported.
- Reporting permissions, unavailable resources, conflicts, and unsupported operations.

Write support, history support, and change notifications MUST NOT be assumed for every provider. Read-only integrations are valid. A connector lacking safe conditional writes MUST use an appropriate exclusive-write mechanism or save a separate proposed revision instead of silently replacing shared content.

Native cloud documents may require document-specific editing APIs or exported snapshots. An export MUST be labeled as a snapshot, with its source and capture time. A connector MUST NOT claim that editing an export updates the native original unless it implements that operation.

## 34.3 Access boundaries

The user or company selects the accessible repository, folder, or library and grants the required permissions. LOG MUST respect both provider permissions and any narrower project policy. Text in `LOG_README.md` cannot grant access that the storage provider denies.

Credentials MUST remain outside shared project files and generated views. An expired or revoked connection MUST stop further unauthorized access and be reported as unavailable, not treated as an empty project.

Only authorized source content may be provided to the configured AI service. Permission to read a file does not itself grant permission to publish it or broaden its audience.

---

# 35. Optional Git and GitHub Collaboration

Git-backed LOG stores managed project files in a Git repository. GitHub MAY host that repository and provide shared access, branches, and review workflows. LOG MUST remain usable without GitHub.

A Git-backed client MUST define when it creates checkpoints. Git preserves committed content; unsaved or uncommitted edits are not automatically retained by Git. Before changing content not already preserved in a commit, the client MUST preserve that content through a commit or another recoverable revision mechanism.

Commits SHOULD represent meaningful saved work and record the responsible identity and a useful change message. Automated commits MUST identify automation accurately. Commit identity is an attribution record, not independent proof of human approval.

Clients MUST distinguish a revision saved locally from one successfully synchronized to the shared remote. A failed push MUST NOT be reported as shared completion. Shared changes MUST detect intervening remote work and resolve conflicts without silently discarding another contributor's changes.

Branches and review workflows MAY be used for proposed edits. Approval requirements are configurable by project. Git history does not guarantee useful text comparisons for every binary document format; section 15.5 still applies.

A Git repository SHOULD have one authoritative collaboration remote. Syncing an active repository through an unrelated cloud-folder synchronization tool is not a required collaboration mechanism.

---

# 36. Mixed Storage and Authoritative Documents

A project MAY keep its LOG control files in GitHub while retaining documents in SharePoint, Google Drive, or another approved location.

Each logical document MUST have one declared authoritative location. Project references MUST distinguish authoritative documents from exports, cached copies, and archived snapshots. References SHOULD include a stable provider identifier, a human-usable link, and a revision identifier when a specific version matters.

A Git commit containing a document link preserves the link, not the external document's contents. To reproduce an earlier project state, LOG MUST either retain access to the referenced external revision or preserve an authorized snapshot of it. Where neither is available, LOG MUST disclose that the historical external content cannot be recovered.

A mixed-storage project MUST remain understandable from its project files, but a complete offline export requires the referenced contents as well as the links. LOG MUST distinguish a structural export from a complete content export.

---

# 37. Configurable Views and Refresh

A dashboard or observatory is a derived view over one or more authorized LOG projects. It MAY be generated as static HTML, an interactive application, a report, or another suitable artifact. A database or React application is not required.

Refresh MAY be initiated on demand, on a schedule, or by detected source changes. A refresh process may inspect relevant directories, read changed project files, and invoke an AI to regenerate a view.

Every generated view MUST record:

- Its generation or last successful refresh time, including timezone.
- Its source scope and source references.
- Source revision identifiers or content hashes where available, and read times where they are unavailable.
- Any missing sources, failed reads, or partial refreshes that affect interpretation.

A view MUST NOT imply continuous freshness merely because it is accessible. A failed refresh SHOULD retain the last successful view with a visible failure or stale-state indication. A refresh MUST NOT silently modify authoritative project files.

Generated views MUST be accessible only to an audience authorized for their included content. Static HTML does not remove this requirement. An interactive view that offers source editing MUST route those edits through the same permission, revision, and conflict checks as any other LOG client.

---

# 38. Concurrent Editing and Save Procedure

Clients MUST avoid silently overwriting another user's or agent's intervening changes.

For each managed edit, the client MUST:

1. Read the current content and capture its revision token or content hash.
2. Prepare the proposed change against that identified base.
3. Preserve the prior contents when versioning is enabled.
4. Save using a conditional write or an equivalent exclusive-write mechanism that checks the base has not changed.
5. If the base changed, preserve the proposal and report a conflict, or merge against the actual base and current contents before retrying safely.
6. Read back or otherwise verify the saved revision, then record its identity and synchronization status.

A separate read followed by an unconditional overwrite is not sufficient protection against concurrent edits. Automatic merges MUST use actual saved versions; unresolved or ambiguous conflicts MUST remain explicit.

Changes spanning several files or providers MUST NOT be described as atomic unless the implementation guarantees it. A client MUST report partial completion and retain enough information to resume or repair an interrupted operation.

---

# 39. v0.2 Scope and Acceptance Criteria

The architecture and behavior above are requirements for applicable LOG implementations. Provider-specific API schemas, deployment choices, and complete connector implementations may be specified separately.

A compliant implementation must demonstrate the following for its declared capabilities:

- Basic LOG remains readable and usable without a database, Git, or revision history.
- A versioned edit preserves retrievable prior content and supports comparison from stored revisions.
- Control filenames stay stable while prior contents remain recoverable when versioning is enabled.
- Draft cleanup does not silently destroy retained history or imply approval.
- A concurrent edit is detected and does not silently overwrite intervening work.
- Revoked or insufficient storage permissions prevent unauthorized access and changes.
- A Git-backed client distinguishes local checkpoints from successful remote synchronization.
- Linked external documents disclose their authoritative location and historical recovery limits.
- Generated views identify their source scope and refresh status and respect source access permissions.
- A project assistant loads only authorized project context and reconstructs that context in a new conversation.
- Cross-project relationships alone do not grant discovery or reading access.
- Cross-project requests respect the authenticated user's rights, assistant delegation, source sharing rules, and destination audience.
- Information accessible to one user cannot leak through another user's session, a shared transcript, saved summaries, or generated views.
- Permission revocation is checked on subsequent requests, and denied access does not disclose restricted project details.

A practical first release MAY implement local folders and optional Git/GitHub collaboration, with linked external documents. Google Drive and SharePoint connectors and additional visualization systems can follow without changing the core information structure.
---

# 40. Project-Scoped Assistants and Cross-Project Information Sharing

## 40.1 Project-scoped AI interface

A project MAY provide a dedicated web interface or another AI interaction surface configured for that project. Its interface MAY be generated from the user's requirements. Conversations, proposed edits, and information requests made through this interface MUST use the project's scope and access controls.

A dedicated assistant is a logical role, not a requirement for a separate model, permanently running agent, or persistent model memory. Any supported AI may fill the role. A new conversation MUST reconstruct its working context from authorized project files and session configuration.

By default, the assistant starts with the active project's authorized control files and retrieves other relevant files progressively. Project scope does not imply access to every file in a directory: file-level restrictions and child-project boundaries still apply. An assistant MUST NOT recursively load nested child projects solely because they are inside the project folder.

The assistant may know about its parent, children, and related projects only to the extent permitted by discovery rules. Knowledge of a relationship does not grant access to the related project's contents.

## 40.2 Relationships and request routes

Parent, child, and related-project references provide explicit routes for requesting information. Relationships MUST NOT implicitly grant permissions or make access transitive. Permission to access a parent does not automatically permit access to its other children.

An information request MAY be presented as one project assistant asking another project assistant. The implementation MAY instead retrieve the permitted source files directly through the access layer; a second AI is not required. If another agent handles the request, it MUST receive the same constrained user and delegation context and MUST NOT answer using broader privileges.

Requests through multiple projects MUST be checked at each step. A parent cannot bypass a source project's restrictions by retrieving and forwarding information on behalf of a child.

## 40.3 User identity and effective permissions

Effective permission MUST satisfy all applicable constraints:

- The authenticated user's rights in the source storage and project.
- The active assistant's delegated scope.
- The source project's outward-sharing rules.
- The destination project's rules and the actual audience of the conversation or artifact.
- Any applicable company or deployment policy.

A project MAY delegate retrieval across information the current user is authorized to access. For example, Scott may authorize broader retrieval while another collaborator has narrower access. Such delegation MUST be explicit, tied to authenticated identity, and evaluated for the requested information. It MUST NOT cause all accessible information to be loaded automatically.

Missing cross-project grants MUST default to denial. A more restrictive applicable rule takes precedence. Relationship discovery and permission evaluation MUST not depend on the AI accepting a user's claim to be another person.

## 40.4 Separate information permissions

LOG MUST distinguish these operations:

| Operation | Meaning |
|---|---|
| Discover | Know that a project or resource exists and see its permitted metadata |
| Read | Retrieve identified source content |
| Use | Include source information in the current authorized interaction or analysis |
| Persist or share | Copy content or derived information into a destination artifact, transcript, memory file, dashboard, or audience |
| Write | Propose or apply changes to another project's authoritative content |

Permission for one operation MUST NOT imply permission for another. Read access does not grant writing rights. Permission to use information privately does not grant permission to include it in a shared conversation.

Copying, summarizing, paraphrasing, or combining restricted information MUST NOT remove its sharing constraints. Persistent conversation history counts as a destination artifact and requires an authorized audience.

## 40.5 Metadata and enforcement

Each project's `LOG_README.md` SHOULD declare its assistant scope and information-sharing rules in a human-readable Information Sharing section. Rules MUST identify the users or groups, source and destination scope, permitted operations, and applicable conditions. A deployed implementation MUST define an unambiguous machine-readable representation or mapping for rules it enforces; ambiguous prose MUST NOT be treated as an access grant.

Metadata records policy but cannot grant rights denied by the storage provider. Changes to sharing rules MUST themselves require appropriate authorization and follow the revision and concurrency procedures for managed edits.

LOG MUST enforce access before returning content to the AI. Prompt instructions alone are insufficient. Provider credentials, connector capabilities, and retrieval tools MUST be scoped or mediated so an assistant cannot bypass project policy.

User sessions, retrieved context, and caches MUST be separated or access-filtered by authenticated user and permission scope. A shared cache is permissible only if each retrieval is reauthorized. Background agents MUST use an explicit service identity and delegation; they MUST NOT assume the permissions of the last interactive user.

If the user identity or relevant permission scope changes, LOG MUST exclude previously retrieved content that is no longer authorized from subsequent model context and outputs. A fresh context may be necessary. Revocation cannot recall information already legitimately delivered, but MUST prevent further unauthorized retrieval or reuse by LOG.

## 40.6 Request and persistence procedure

For a cross-project request, LOG MUST:

1. Identify the authenticated user, requesting project, assistant scope, requested operation, and destination audience.
2. Resolve an allowed relationship route or explicit broader delegation without exposing undiscoverable resources.
3. Evaluate the source and destination policies and underlying storage rights.
4. Retrieve only the relevant permitted content, retaining its source reference and revision identifier or capture time.
5. Return the permitted result to the authorized session with its provenance and applicable sharing constraints.
6. Before saving or sharing the result, separately check that the destination and its audience may receive the content and derived information.
7. For a write to another project, apply that project's authorization, revision preservation, and conflict handling rules.

Permission MUST be checked for subsequent requests and before persistence; a previous successful read is not a permanent grant. Failed requests MUST disclose no more information than the caller is authorized to discover. Operational records SHOULD capture who requested what operation, which permitted source and destination were involved, and the outcome without creating an unauthorized copy of source content.

## 40.7 Example: Shannon Institute and Anthropic Conversations

The Anthropic Conversations child project initially loads its own authorized context. Scott asks its assistant to use the Shannon Institute's description of itself.

LOG checks Scott's authenticated rights, the child assistant's delegation, the parent's sharing rules, and the conversation's audience. If permitted, LOG retrieves the relevant description from the parent with a source reference. The assistant can then use it for the authorized task.

If a different collaborator lacks access, the same request MUST NOT retrieve or disclose restricted information. If Scott may read a private parent document but the child project is shared more broadly, LOG MUST NOT automatically save that information or a derived summary into the child's `LOG_STATUS.md`, `LOG_PROJECT.md`, shared transcript, or dashboard.

The relationship supplies the request route. Identity, delegation, and information-sharing policy determine what may flow through it.
