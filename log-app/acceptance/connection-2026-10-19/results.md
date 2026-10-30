# Connected AI acceptance — 2026-10-19

Requirements: ORG-06 (access rules, for connected AI only). See the [requirements checklist](../../../LOG-REQUIREMENTS-CHECKLIST.md) and the [app README](../../README.md#connected-ai).

**Result: passed on this Mac's copy, not yet online.** A scripted assistant used the real sign-in pages in a headless browser against a copy of the LOG folder; no browser errors. It has not yet been tested with ChatGPT, Claude or Gemini, which needs the connection online first.

| Step | Expected | Observed |
|---|---|---|
| Set the connection password and turn on only Italy Trip | Saved; access recorded in `LOG-ACCESS.json` | `{"projects": ["Family Holidays/Italy Trip"]}` |
| Assistant registers and opens the sign-in page | Page names the assistant and where it returns | Shown ([screenshot](1-sign-in-page.png)) |
| Enter the password | A 6-digit code appears in the app, not on the sign-in page | Code shown on the Connected AI page ([app](2-code-in-app.png), [sign-in page](3-code-entry.png)) |
| Enter the code | Returned to the assistant, which gets a token | State matched; token issued |
| Register a deceptive return address (`https://evil.example\@claude.ai/...`) | Refused | Refused (400) |
| Strangers open the sign-in page 5 times | Nothing appears in the app | No sign-in cards |
| Assistant connects | Listed in the app without reloading | Listed |
| Connect and list projects | Only Italy Trip; LOG rules included in the connection instructions | As expected |
| Open the parent project; search a phrase only in the parent | Refused; no results | Refused; no results |
| Propose a change to Italy Trip's status | Waits; file unchanged | Waiting, badge 1, file unchanged ([screenshot](4-waiting-for-approval.png)) |
| Approve it in the app | Saved; the assistant sees the decision | Saved; the assistant saw "approved" ([review](5-review.png)) |
| Propose a new child project, approve, and turn it on | Created and visible to the assistant | Created and granted ([screenshot](6-new-project-review.png)) |
| Disconnect the assistant | Its token stops working | 401 ([before disconnecting](7-connected.png)) |
| Phone width (390 px) | No sideways scrolling | Page width stayed at 390 px |

Automated tests (`test_connection.py`, 37 tests, real HTTP and real Git) cover:
- discovery and the sign-in challenge
- the full sign-in
- password and code both required
- the lockout, including parallel guesses
- request, redirect and token checks
- refresh rotation and reuse
- expiry and disconnecting
- confidential clients
- origin, host, version and method checks
- project visibility, including letter-case and accent variants and one-letter project names
- archived projects left out of search unless the assistant asks
- the proposal and approval flow
- rejected repeats
- staged memory updates
- new projects
- the versioned access file
- hashed secrets
- strangers unable to fill up sign-in or registration
- a capped activity log
- a cap on waiting proposals, including parallel proposals
- single-message requests only (no batches) and a request limit on every call
- a limit on wrong codes across sign-ins
- registration limits per address
- identical answers for missing and hidden files
- signing everyone out when the password changes
- malformed requests
- invisible characters in assistant names and in repeated rejected edits

The full suite has 111 passing tests.

Script: [run_connection_acceptance.py](run_connection_acceptance.py).

## Security reviews

Before going online, the security code was reviewed twice by separate assistants that had not seen how it was built. Neither found a way to sign in, read or change anything without the password and the code shown in the app.

First review, fixed and covered by tests:
- Return addresses that Python and browsers read differently, which could have made the sign-in page name one site while sending the code to another; line breaks in a return address.
- On a Mac, a path differing only in letter case or accent form (`family/secret/...`) could open a child project that was not turned on.
- A one-letter project name was treated as part of the root project.
- Parallel wrong passwords could get past the lockout.
- Strangers could fill up sign-in requests and registrations.
- The activity log could grow from very large requests.
- One assistant could pile up unlimited waiting proposals.

Second review, fixed and covered by tests:
- A connected assistant could send thousands of requests in one message and exhaust the Mac's memory.
- Parallel proposals could get past the waiting limit.
- Someone who knew the password could keep guessing codes across new sign-ins.
- Strangers could push out an assistant that was part-way through signing in.
- A connected assistant could tell missing files from hidden ones, revealing names outside its projects, and hidden search matches could crowd out allowed ones.
- Changing the password did not sign anyone out.
- Some malformed requests dropped the connection instead of getting an error.
- Invisible or text-reversing characters were kept in assistant names, and could make a rejected edit look new.

Accepted: a connected assistant proposing a new project can learn whether a folder with that name already exists directly inside a project it may open. Child project names are normally listed in that project's README anyway.

## Session records, 2026-10-23

Requirement: MEM-04 (closing review), for assistants connected through the LOG connection.

| Step | Expected | Observed |
|---|---|---|
| A connected assistant proposes a session record for Italy Trip | Waits for approval; no file written | Nothing saved; it appeared as "Session record:" on the Connected AI page ([screenshot](8-session-record-waiting.png)) |
| Open it for review | The dialog says what approval does and offers no project-access option | Explained; the access option stayed hidden ([screenshot](9-session-record-review.png)) |
| Approve it | Saved as a new file in the project's conversations folder with the decisions as sent | Saved; contents matched |

The browser run used a disposable copy of the folder with the same script. Two automated tests also cover:
- the record is saved only on approval, and rejection saves nothing
- a second record with the same title the same day gets its own file
- the record is searchable and listed when the project is opened
- records for the root project
- projects not turned on are refused
- size and list limits
- invisible characters are removed and line breaks in list items become spaces
- a record whose stored location was changed after it was proposed is refused

The full suite has 114 passing tests.

The same run showed that the "Let connected AIs see the new project" option appeared in every review dialog, not just for new projects, because the page's styles overrode the hidden setting. That is fixed; the option now appears only for new projects.

## Limits

- Single user. Five wrong passwords or ten wrong codes in an hour lock new sign-ins for 15 minutes, so someone who finds the address can delay a new sign-in; assistants already connected keep working.
- The Mac must be awake with LOG running.
- Return addresses must be plain `https` addresses, or `http` on localhost. App addresses such as `cursor://` are not accepted.
- No streaming responses and no Client ID Metadata Documents. Assistants register themselves instead.
