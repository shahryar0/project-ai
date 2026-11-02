# V2 Phase 2: human review and bounded revisions

Status: implemented. This phase adds human review to the persisted draft workflow. It
does not add social publishing, scheduling, OAuth, connected accounts, or a review UI.

## What changed

- The additive schema migration advances the local database to v2 and backfills
  eligible completed Phase 1 drafts into `pending_review`. It does not reset saved
  campaigns or versions.
- Drafts without blocking QA issues enter `pending_review` after campaign completion.
  Drafts with blocking issues remain `draft` until corrected.
- The approval service supports owner edits, change requests, exact-version approval
  and rejection. Approval requires both the current version number and its SHA-256
  content hash. A human edit creates a new immutable version and voids prior approval.
- Each state change is recorded in `audit_events`; audit reads are tenant scoped.
- Human API roles are derived from configured bearer secrets. `owner` can edit;
  `owner` and `approver` can request changes and decide approval. Agent/system
  identities are not accepted by these routes. The configured token is bound to
  `AI_EMPLOYEE_TENANT_ID` (default `local`).
- The manager has a `brand_guardian` tool. Its reviewer can read only the campaign's
  authoritative brand and saved draft versions; its verdict is parsed against a
  Pydantic schema. It cannot edit or approve drafts.
- The CEO has `get_campaign_status`, which reads actual campaign and draft states.
  The API also replaces unsupported positive claims that a post was published,
  scheduled, posted, or approved when no saved state supports them.
- `POST /drafts/{id}/request-changes` records the owner's comment.
  `POST /drafts/{id}/revise` runs the Writer against only that draft, then reviews
  each revision with the Guardian. The database caps agent revisions at two per
  draft. Human edits are not counted as agent revisions.
- `PATCH /drafts/{id}`, `POST /drafts/{id}/approve`, `POST /drafts/{id}/reject`,
  `GET /drafts/{id}`, `GET /campaigns/{id}`, and `GET /audit` are available to
  authenticated local human roles. The approval remains `approved` while the
  connector status remains `not_connected`.

## Local token setup

Add secrets to ignored `ai_employee/.env` or PowerShell environment variables:

```dotenv
AI_EMPLOYEE_OWNER_TOKEN=use-a-long-random-secret
AI_EMPLOYEE_APPROVER_TOKEN=use-a-different-long-random-secret
AI_EMPLOYEE_TENANT_ID=local
```

Restart `run.py`. In Swagger `/docs`, select **Authorize** and enter
`Bearer <token>`. These shared local tokens are a development authentication
mechanism; use an identity provider before exposing the API to multiple users or
the public internet.

## Review sequence

1. Create a campaign with `POST /chat`; eligible drafts return as `pending_review`.
2. Read `/drafts/{draft_id}` to get its current version, hash, and review state.
3. Approve or reject with that exact version and hash, or edit using `PATCH`.
4. To request an agent revision, call `/request-changes` with a human comment and
   then `/revise`. The Writer creates a new version; the Guardian reviews it.
5. Review `/audit?tenant_id=local` for the append-only event history.

The revision endpoint uses the provider configured by `MODEL_PROVIDER`. Unlike the
initial campaign runner, it does not restart on the other provider if a revision
call fails. A failed revision request returns an error; any version already saved
by its preview tool remains visible in draft history and still requires human review.

## Safety and boundaries

- No LLM-accessible tool approves, schedules, publishes, deletes or connects accounts.
- Human approval is a review state only. There is no publisher or schedule endpoint.
- `get_campaign_status` is read-only and tenant scoped.
- A revision targets exactly one `draft_id` and platform. The preview tool rejects
  attempts to save to another platform.
- Guardian failure is not a pass. Blocking issues remain visible, and QA controls
  whether a version can enter `pending_review`.
- Phase 3 (Visual Designer) and Phase 4 (connectors and publisher) were not started.

## Verification

Completed: **95 passed, 1 optional live-provider test skipped**. The tests cover
exact-version/hash approvals, edits voiding prior approval, change-request audit,
two-round revision cap, agent/system rejection, forbidden tool introspection,
unsupported status-claim sanitization, prompt-injection boundaries, and Phase 1
persistence/fallback behavior. Tests use local SQLite and mocked provider responses;
no live provider request or social API call was made.

Run from `ai_employee`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```
