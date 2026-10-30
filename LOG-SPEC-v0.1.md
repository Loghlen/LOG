# LOG Specification v0.1

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

The canonical source of truth in LOG is the filesystem.

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

A Project should have exactly one primary parent unless it is the root LOG project.

A Project may reference other projects without making them parents.

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

LOG should support multiple versions of documents.

The exact implementation is not prescribed in v0.1.

Acceptable approaches may include:

- Git
- Versioned filenames
- Filesystem snapshots
- Application-level version history

The following must be possible:

- View previous versions
- Know when something changed
- Know who or what changed it
- Restore an earlier version
- Compare versions

The latest file remains the canonical current version unless otherwise specified.

---

# 16. AI Project Opening Procedure

When an AI begins working on a LOG project, it should not immediately load every file.

Recommended process:

### Step 1

Read:

```text
LOG_README.md
```

Understand identity, scope, ownership, and rules.

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

Inspect child projects if necessary.

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

Only `parent` and `child` are required for v0.1.

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
14. Preserve document history
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

# 32. v0.1 Philosophy

LOG is not trying to replace the filesystem.

LOG makes the filesystem intelligent.

It adds enough structure that humans and AI systems can maintain shared understanding across time without turning the user's work into an opaque database.

The filesystem remains the durable layer.

AI provides interpretation.

LOG provides organization.
