# AI Employee backend with Gemini

The active path is **FastAPI -> LangGraph -> Gemini Developer API**.
The active graph is a stateless hierarchy with tool-based delegation:

```text
CEO (owner-facing assistant)
  -> social_media_manager tool / manager agent
     -> content_writer tool / content agent
        -> preview_facebook_post
        -> preview_instagram_post
        -> preview_x_post
        -> preview_linkedin_post
```

Each agent has its own system prompt and role personality in `app/prompts/`.
Only the content writer has platform tools; every platform tool renders a local
draft. There are no social API calls, account connections, publishing or scheduling.

## Setup on Windows

Open PowerShell in `ai_employee` and run:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

Create a key in [Google AI Studio](https://aistudio.google.com/apikey), then add
or update these settings in your local `.env`:

```dotenv
GOOGLE_API_KEY=your_actual_google_ai_studio_key
GEMINI_MODEL=gemini-3.5-flash-lite
```

The default model is Gemini 3.5 Flash-Lite. Change `GEMINI_MODEL` if your Google
project uses a different supported text model. `GEMINI_API_KEY` is also accepted
as a fallback when `GOOGLE_API_KEY` is not set. Environment variables already
set in the terminal take precedence over `.env` values.

Your API key stays on your PC. Git ignores `.env`; do not put a real key in
`.env.example`, source code, or a commit. AWS credentials are not required.
The original `txtbase.txt` is kept only as a reference to the earlier Bedrock example.

## Run and test

```powershell
.\.venv\Scripts\python.exe run.py
```

Open <http://127.0.0.1:8000/docs>, expand **POST /chat -> Try it out**, and send:

```json
{
  "query": "Draft launch posts for our planning app. Do not invent prices or dates.",
  "brand": {
    "name": "Focus Studio",
    "description": "A planning app for organizing a freelancer's working day.",
    "audience": "Freelancers",
    "tone": "Warm, practical and confident",
    "language": "English"
  },
  "platforms": ["facebook", "instagram", "x", "linkedin"]
}
```

Or use a second terminal while the server is running:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/chat -Method Post -ContentType 'application/json' -Body '{"query":"What is the capital of France?"}'
```

A successful response includes `answer`, `model_id`, `mode`, `previews` and
`tool_calls`. Every preview includes its exact `text`, a written
`media_suggestion`, `character_count`, editorial `warnings`, `status: "draft"`,
`published: false`, and `connector_status: "not_connected"`. These flags are
set by code, and the displayed text comes from real preview tool results.

The call trace contains tool names, agent roles and completion status; it does
not expose model reasoning or credentials. The normal path is CEO calling the
manager, manager calling the writer once for the batch, and the writer calling
one preview tool per requested platform. Agents may make revision calls.

`brand` and `platforms` are optional. An explicit platform list is enforced even
if the model attempts an extra platform. Without a list, agents follow platforms
mentioned in the brief, defaulting to all four when none are mentioned. Twitter
is treated as X. Brand preferences reach all three agents through per-request
context. Supply the preferences and full revision brief on each request; chat
memory is not enabled and requests do not share drafts.

Facebook uses a conversational/community voice, Instagram a visual caption,
X a concise message, and LinkedIn a professional/business voice. Internal
editorial budgets are 1200, 1800, 260 and 2000 characters respectively; these
are draft-writing targets, not platform API validation. Character counts use
Python string length. Actual media generation, URL handling and platform-specific
validation will belong to future connectors.

For the original connection check, send only
`{"query": "What is the capital of France?"}`. The CEO answers directly; preview
and call lists are empty. The PowerShell example above runs this simple check.
`GET /health` checks only the API and does not validate your key or model access.
The model is created on the first `/chat` request. Restart the server after
changing `.env`. Press `Ctrl+C` to stop the server.

## Troubleshooting

- `ModuleNotFoundError`: install `requirements.txt` using the `.venv` Python above,
  and use that same Python to start `run.py`.
- HTTP 503 with a missing key: set `GOOGLE_API_KEY` in `ai_employee/.env` and restart.
- HTTP 503 with key/access rejection: check the key, its project permissions,
  and Gemini Developer API access in AI Studio.
- HTTP 429: your Google project has hit a Gemini rate or quota limit. Check the
  project's limits and availability; switching providers does not guarantee unlimited quota.
- HTTP 502 with an unavailable model: check `GEMINI_MODEL` against models your key can access.
- HTTP 502 with a rejected request: check the API key, model ID, and request settings.
- HTTP 502 with empty text: the model returned no visible answer (for example,
  generation was blocked or used its output budget); check the prompt and model settings.
- HTTP 503 connection/service error: check your connection and the Gemini service status.

`/` and `/favicon.ico` are not defined, so 404 responses for those URLs are expected.
The CEO caps output at 1024 tokens, the manager at 1536, and the content writer
at 4096 for a batch of four posts. Each Gemini call uses a 30-second timeout and
one retry. Social campaigns require multiple calls. Each agent has a graph step
limit to bound repeated tool execution. Temperature uses the model default.

## Local checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Normal tests mock the Gemini SDK, exercising nested agent/tool calls, the real
Gemini adapter, brand context propagation, preview-only guarantees, platform
selection, and isolation between requests. The optional CEO smoke test runs against
Gemini only when `RUN_LIVE_MODEL_TESTS=1` is explicitly set and a key is configured.

References: [Gemini model](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite),
[API key setup](https://ai.google.dev/gemini-api/docs/api-key),
[LangChain Gemini integration](https://docs.langchain.com/oss/python/integrations/chat/google_generative_ai),
[agent delegation pattern](https://docs.langchain.com/oss/python/langchain/multi-agent/subagents),
[API troubleshooting](https://ai.google.dev/gemini-api/docs/troubleshooting).
