# V2 Phase 1: persistence and structured briefs

Status: implemented for review. This phase does not add approval, Guardian/Designer
agents, scheduling, publishing, OAuth, or social connectors. The three existing agents
and AWS-first/Gemini fallback remain active.

## What changed

- `app/briefs.py` builds an authoritative `CampaignBrief` with run/tenant IDs and the
  owner's exact original text. Topic, extra facts and call-to-action may be supplied
  explicitly; the code does not infer new business facts.
- Platform selection is code-owned: explicit list, else query keywords (Twitter -> X),
  else all four. Delegation tools accept a typed brief and reject changed fields.
- Brand information is stored as an immutable snapshot inside each campaign brief,
  including optional `forbidden_claims`; a tenant-wide profile editing API is not added.
- `app/storage/` provides a repository interface, SQLAlchemy implementation, initial
  additive schema migration, and read views. Tables store tenants, campaigns, drafts,
  and immutable draft versions. SQLite is the default.
- Preview tools save versions and return `draft_id`, `version`, `content_hash`,
  `qa_issues`, `hashtag_count`, and the existing preview fields. Exact repeated saves
  reuse the current version; text or visual-idea edits create a new version.
- `app/qa/` flags unsupplied URLs, prices, dates, phone numbers and handles, configured
  forbidden claims, and some common exaggerated claims. Editorial length and repeated
  hashtag issues are warnings. Empty/unrequested drafts are rejected before saving.
- AWS fallback deletes versions from the failed attempt before starting Gemini under
  the same campaign/run. A fully failed run is marked failed and its partial drafts
  are removed. No failed-provider drafts appear in the final saved campaign.

## Install and run

From `ai_employee`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

The SQLite database is created lazily at `ai_employee/data/ai_employee.db`.
The folder and SQLite files are ignored by Git. Saved content belongs to that laptop
and is not transferred by cloning the repository. `DATABASE_URL` can override the path
in local `.env`; other database drivers must be installed separately if using them.

## Test a persisted campaign

In `/docs`, POST `/chat` with:

```json
{
  "query": "Create launch posts for our planning app. Do not invent prices or dates.",
  "run_id": "planning-launch-001",
  "tenant_id": "local",
  "brand": {
    "name": "Focus Studio",
    "audience": "Freelancers",
    "tone": "Warm and practical",
    "language": "English",
    "forbidden_claims": ["guaranteed results"]
  },
  "platforms": ["facebook", "instagram", "x", "linkedin"]
}
```

The existing `query`-only request still works. Run/tenant IDs are optional; a new run
ID is generated when omitted and tenant defaults to `local`.

The response adds `campaign_id`, `run_id`, `tenant_id`, and `replayed`. Each preview
has a saved ID/version/hash and QA results. Every draft still has `state="draft"`,
`status="draft"`, `published=false`, `connector_status="not_connected"`.

Read saved results, including after a server restart:

```text
GET /campaigns/{campaign_id}?tenant_id=local
GET /drafts/{draft_id}?tenant_id=local
```

Campaign reads include the authoritative brief and drafts. Draft reads include the
current preview and complete version history. Missing records or records outside the
requested tenant scope return 404.

## Idempotency and fallback

A `run_id` is scoped to a tenant. Repeating the identical completed brief with the
same run ID returns the saved result (`replayed=true`) without another model call.
Its tool trace is the recorded trace of the original run. Use a new run ID for a new
campaign or a changed brief. An active duplicate or changed brief with an existing
run ID returns 409. A failed run can be retried with the same brief and run ID.

Fallback keeps the same campaign/run IDs but removes failed-attempt draft versions
before the second provider starts. Short DB transactions are used for individual
writes; no database transaction is held open while waiting for a model response.

## Hash and QA boundaries

The hash is SHA-256 over a canonical JSON tuple of platform, NFC-normalized text with
normalized newlines, and an empty media-asset hash. Actual media assets arrive in a
later phase. Written visual suggestions are versioned but are not publishable assets.

QA is conservative lexical checking, not full semantic fact verification. It can flag
legitimate rephrasing and cannot catch every invented claim or negated instruction.
The default date/currency patterns focus on English dates and common currency forms;
additional language rules can be added later. Hashtags are counted and duplicate tags
warned about; no official platform hashtag limit is invented. Internal character
budgets remain editorial guidelines, not connector/API validation.

Phase 1 tenant filtering is not authentication. Client-supplied tenant IDs are for local
development; authenticated tenant/role enforcement belongs to Phase 2. A process killed
mid-generation can leave a `running` campaign; use a new run ID while recovery/leases are
not yet implemented. Only completed campaigns are final results. There are no human
edit/approval endpoints in this phase and no draft can be published.

## Verification

Completed: **87 tests passed, 1 optional live-provider test skipped**. `pip check`
reported no dependency conflicts. No live provider requests were made for this phase.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The test suite covers deterministic platforms and unchanged owner text, QA fact checks,
disk persistence, immutable versions, read views, tenant-scoped repository lookups,
concurrent run claiming, idempotent replay, conflicting run IDs, failed-run retry,
changed delegation briefs, and deletion of partially persisted AWS drafts before
Gemini starts (I7, I8, I10). Provider requests are stubbed/mocked. Live-provider tests
remain opt-in. Approval and publishing invariants are for their later phases.

Stop here for the owner's review before Phase 2.
