# project-ai

**V2 Phase 1 is now implemented:** saved draft versions, typed briefs, code-owned platform selection and QA. See the [Phase 1 report](ai_employee/PHASE1_REPORT.md) for the current contract and how to test persistence. Later phases are not active.

- `ai_employee/`: FastAPI and LangGraph agents, using **AWS Bedrock first** and **Gemini fallback**.
- `cognitive/`: Next.js frontend scaffold, to connect in a later step.

The hierarchy is **CEO -> Social Media Manager -> Content Writer -> Platform Preview Tools**.
It creates draft previews for Facebook, Instagram, X and LinkedIn. Social connectors
and publishing are future work; no social account is contacted.

## Clone and install

Use Python 3.11 or newer. Node.js 20.9 or newer is needed only for the optional frontend.

```powershell
git clone https://github.com/shahryar0/project-ai.git
cd project-ai\ai_employee
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

For an existing clone, run `git pull`, install the updated requirements using the
project's `.venv` Python, then add these settings to your existing local `.env`:

```dotenv
MODEL_PROVIDER=bedrock
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=amazon.nova-micro-v1:0
# Optional: leave empty to use your AWS CLI credentials.
AWS_BEARER_TOKEN_BEDROCK=
# Optional for a named AWS CLI profile:
# AWS_PROFILE=your-profile-name
GOOGLE_API_KEY=your_actual_google_ai_studio_key
GEMINI_MODEL=gemini-3.5-flash-lite
```

Bedrock uses your configured AWS credentials, or the bearer token when supplied.
Short-term tokens expire; replace them locally and restart the server.
See [AWS bearer-token setup](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys-use.html).
The Gemini fallback key comes from [Google AI Studio](https://aistudio.google.com/apikey).
A successful AWS request does not need a Gemini key. Both providers require model
access and available quota. Set `MODEL_PROVIDER=gemini` to use Gemini directly.
Keep real keys only in `.env`, which Git ignores; `.env.example` remains empty.

## Run and request previews

From `ai_employee`:

```powershell
.\.venv\Scripts\python.exe run.py
```

Keep this terminal open. Open <http://127.0.0.1:8000/docs>, expand **POST /chat ->
Try it out**, and execute:

```json
{
  "query": "Draft launch posts for our planning app. Do not invent prices or dates.",
  "brand": {
    "name": "Focus Studio",
    "description": "A planning app that helps freelancers organize their working day.",
    "audience": "Freelancers",
    "tone": "Friendly, practical and confident",
    "language": "English"
  },
  "platforms": ["facebook", "instagram", "x", "linkedin"]
}
```

`brand` and `platforms` are optional. Code resolves platforms named in the query,
or all four when none are named. An explicit platform list is enforced by tools.
Each model run is independent; drafts are persisted. Supply the brand and full brief for each new campaign.
For the simple model check, send `{"query":"What is the capital of France?"}`.

The response contains `answer`, structured `previews`, and actual `tool_calls`.
Every preview is a draft with `published: false` and `connector_status: "not_connected"`.
`provider`, `model_id`, `fallback_used`, and `provider_attempts` identify which model
completed the request. An AWS quota failure followed by Gemini success, for example,
returns `provider: "gemini"`, `fallback_used: true`, and both attempt statuses.

## AWS retry and fallback behavior

AWS uses Converse with adaptive retries and at most two total SDK attempts per call,
with 10-second connect and 30-second read timeouts. These settings follow the supported
parts of the reference in `ai_employee/txtbase.txt`. A short delay or different URL
cannot clear an exhausted daily quota; an AWS model failure triggers Gemini instead.

Fallback restarts the entire hierarchy from the original brief and brand context,
including when AWS fails inside a child agent. Partial AWS messages/previews are not
mixed into the Gemini result. Gemini is constructed only when needed. Invalid request
bodies and graph step-limit errors are reported directly. If both providers fail,
the error names both failures without returning raw provider messages or credentials.

`GET /health` reports API status and configured provider preference only, without
checking either provider. Restart after changing `.env`; press `Ctrl+C` to stop.
Social campaigns require multiple model calls. All tools currently render local previews;
future publishing must be implemented as a separate delivery step.

## Checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests stub Bedrock and mock Gemini, exercising provider selection, fallback inside
nested agents, brand context, platform selection, request isolation, and real preview
tools without model requests. The optional live test requires `RUN_LIVE_MODEL_TESTS=1`.

- HTTP 429: fallback is also quota/rate limited.
- HTTP 503: credentials, access, connection or service unavailable after fallback.
- HTTP 502: invalid model/request settings, empty generation or graph step limit.

See [the backend README](ai_employee/README.md) for implementation details.

## Optional frontend

From the project root, open another terminal:

```powershell
cd cognitive
npm ci
npm run dev
```

Open <http://localhost:3000>. Use `/docs` on port 8000 for the model workflow.
The root `.gitignore` excludes `.env`, installed dependencies, caches, build output
and local credentials, while keeping dependency files and environment templates.

Review the [agent hierarchy, instructions, tools and edit locations](ai_employee/AGENT_HIERARCHY.md).
