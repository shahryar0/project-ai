# AI Employee: AWS first, Gemini fallback

**V2 Phase 2 is implemented:** saved drafts now enter human review, with exact-version approvals, human edits, change requests, bounded agent revisions and an audit trail. See [PHASE2_REPORT.md](PHASE2_REPORT.md) for the workflow and local setup.

FastAPI invokes a LangGraph hierarchy with separate system prompts and personalities:

```text
CEO
  -> social_media_manager tool / manager agent
     -> content_writer tool / content agent
        -> preview_facebook_post
        -> preview_instagram_post
        -> preview_x_post
        -> preview_linkedin_post
     -> brand_guardian tool / read-only review agent
CEO -> get_campaign_status (read-only saved state)
```

All platform tools are local renderers. There is no publishing, scheduling, account
connection, browsing or image generation. A visual suggestion is only a written idea.
Only the configured human bearer tokens can edit or decide draft approvals. Agents
cannot approve, schedule or publish.

## Setup and run on Windows

From `ai_employee`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

Add or update these settings, preserving any existing local keys:

```dotenv
MODEL_PROVIDER=bedrock
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=amazon.nova-micro-v1:0
AWS_BEARER_TOKEN_BEDROCK=
GOOGLE_API_KEY=your_actual_google_ai_studio_key
GEMINI_MODEL=gemini-3.5-flash-lite
AI_EMPLOYEE_OWNER_TOKEN=choose-a-long-random-local-secret
AI_EMPLOYEE_APPROVER_TOKEN=choose-another-long-random-local-secret
AI_EMPLOYEE_TENANT_ID=local
```

Keep the two review tokens only in ignored `ai_employee/.env` or your terminal
environment. The configured token determines its role; an `agent` or `system`
identity cannot pass the human approval routes. The local default tenant is `local`.

The empty AWS bearer-token field uses your existing AWS CLI credentials. Add
`AWS_PROFILE=your-profile-name` if needed. In CLI credential mode, check the identity
with `aws sts get-caller-identity`. Alternatively, enter a Bedrock bearer token in
`AWS_BEARER_TOKEN_BEDROCK`; it takes priority over an explicit profile. Expired
short-term tokens must be replaced locally. Never put a real token in `.env.example`.

Gemini's key is from [Google AI Studio](https://aistudio.google.com/apikey).
`GEMINI_API_KEY` is accepted as a fallback when `GOOGLE_API_KEY` is not set.
Terminal environment variables take precedence over `.env`. AWS success does not
require a Gemini key; fallback does. To explicitly bypass AWS, use `MODEL_PROVIDER=gemini`.

```powershell
.\.venv\Scripts\python.exe run.py
```

Restart the server after changing `.env`. Open <http://127.0.0.1:8000/docs>, expand
**POST /chat -> Try it out**, and send:

```json
{
  "query": "Create launch posts for our planning app. Do not invent prices or dates.",
  "brand": {
    "name": "Focus Studio",
    "description": "An app that helps freelancers organize their working day.",
    "audience": "Freelancers",
    "tone": "Warm, practical and confident",
    "language": "English"
  },
  "platforms": ["facebook", "instagram", "x", "linkedin"]
}
```

For a basic connection check, use `{"query":"What is the capital of France?"}`.
The CEO answers ordinary questions directly with empty preview and call lists.

## Response contract

- `answer`: exact platform previews rendered for the owner.
- `previews`: platform, text, written media suggestion, character count, warnings,
  an approval state, `connector_status: "not_connected"`, and `published: false`.
- `tool_calls`: actual agent/tool names and completion status, without model reasoning.
- `provider`: `bedrock` or `gemini`, whichever completed the workflow.
- `model_id`: actual model used, not just the configured primary.
- `fallback_used`: true when Bedrock failed and Gemini completed the request.
- `provider_attempts`: ordered success/failure records with sanitized failure reasons.

`GET /health` checks the API only and reports configured provider preference.
It does not test keys, AWS credentials, model access or quota. `/` and `/favicon.ico`
are not defined, so their 404 responses are expected.

## Human review workflow

In `/docs`, select **Authorize** and enter `Bearer <your owner token>`. A completed
campaign's drafts enter `pending_review` only when deterministic QA has no blocking
issues. Each approval is bound to the displayed draft version and content hash.
Human edits create a new immutable version and void any older approval.

Use `POST /drafts/{draft_id}/request-changes` with a comment, then
`POST /drafts/{draft_id}/revise` to let the Writer revise that draft. The Guardian
checks each saved revision; code caps agent revisions at two. To edit text yourself,
use `PATCH /drafts/{draft_id}`. Approve or reject with the exact current `version`
and `content_hash` via `/approve` or `/reject`. Review history is available at
`GET /audit?tenant_id=local`; `GET /drafts/{draft_id}` shows approval requests and
all saved versions.

Approval does not publish. Scheduling and publishing endpoints, OAuth, and social
connectors are not implemented in this phase.

## How AWS fallback works

The supported Converse, bearer-token and adaptive-retry ideas from `txtbase.txt`
are implemented using `ChatBedrockConverse`. Nova Micro uses the Converse API rather
than an assumed OpenAI-compatible `/v1` endpoint. AWS retries are bounded to two
SDK attempts per call, with 10-second connect and 30-second read timeouts. These
settings cannot increase an AWS quota or clear a daily quota rejection.

`app/runner.py` starts the entire hierarchy on Bedrock. AWS initialization,
credentials, token expiry, access rejection, throttling, connection/service failure
or empty generation can trigger a new Gemini workflow with the original query and
brand context. This also covers AWS failure inside the manager or writer.
Partial AWS messages/previews are discarded. The Gemini graph is created lazily.
If Gemini also fails, the HTTP error reports both providers safely. Request validation
and graph step limits are reported directly rather than triggering provider fallback.

Each model run is independent, with brand/preferences passed through an authoritative CampaignBrief. Draft history is persisted.
CEO short-term memory and durable history are not enabled. Graphs are cached per
provider, but request messages and drafts are not shared. The CEO output cap is 1024,
the manager 1536, and the writer 4096 tokens. Gemini has a 30-second timeout and one
retry. A campaign usually takes several model calls, and an AWS failure may add latency.

Fallback is safe to restart here because every tool is a local preview. Real publishing
must be a separate delivery step before social connectors are enabled.

## Content behavior

`brand` and `platforms` are optional. An explicit platform list is enforced by the
tools. Without it, code resolves platform keywords in the original query, defaulting to all
four when none are named. Twitter means X. Send the full brief and brand on each request.

Facebook uses a community voice, Instagram a visual caption, X a concise message,
and LinkedIn a professional business voice. Internal editorial budgets are 1200,
1800, 260 and 2000 characters respectively. These are writing targets, not official
platform API validation. Character counts use Python string length; future connectors
will need platform-specific URL, media and text validation.

## Troubleshooting and checks

- Missing module: install requirements and start `run.py` with the same `.venv` Python.
- AWS failure with successful fallback: inspect `provider_attempts[0].reason`.
- AWS initialization failure: check the CLI profile or bearer token and restart.
- Daily token quota: check the account's applied Bedrock quotas. Repeated retries
  do not create more allowance; the configured Gemini fallback handles the request.
- Both providers failed: verify both credentials, model IDs and project/account quotas.
- HTTP 429: Gemini fallback is also rate/quota limited.
- HTTP 503: missing credentials, access denial, connection or temporary provider failure.
- HTTP 502: invalid model/request, empty output or graph step limit.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Normal tests stub Bedrock and mock Gemini SDK responses while executing the actual
agent graphs and preview tools. The live test is opt-in with `RUN_LIVE_MODEL_TESTS=1`.

References: [Bedrock API keys](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys-use.html),
[Bedrock Converse integration](https://docs.langchain.com/oss/python/integrations/chat/bedrock),
[AWS retries](https://docs.aws.amazon.com/sdkref/latest/guide/feature-retry-behavior.html),
[token accounting](https://docs.aws.amazon.com/bedrock/latest/userguide/quotas-token-burndown.html),
[Gemini keys](https://ai.google.dev/gemini-api/docs/api-key).

Review the [agent hierarchy, instructions, tools and edit locations](AGENT_HIERARCHY.md).
