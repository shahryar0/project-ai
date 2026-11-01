# AI Employee backend with Gemini

The active path is **FastAPI -> LangGraph -> Gemini Developer API**.
The graph is `START -> model -> END`, with a simple assistant prompt and one
independent question per request. CEO and social agents remain for later.

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
{"query": "What is the capital of France?"}
```

Or use a second terminal while the server is running:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/chat -Method Post -ContentType 'application/json' -Body '{"query":"What is the capital of France?"}'
```

A successful response includes an `answer` about Paris and
`model_id: gemini-3.5-flash-lite`. The text comes from Gemini.
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
The shared model factory caps output at 1024 tokens and uses a 30-second timeout
with one retry. It leaves generation parameters such as temperature at the model default.

## Local checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Normal tests mock the Gemini SDK, exercising LangGraph and the real LangChain
Gemini adapter without sending requests. The future CEO smoke test runs against
Gemini only when `RUN_LIVE_MODEL_TESTS=1` is explicitly set and a key is configured.

References: [Gemini model](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite),
[API key setup](https://ai.google.dev/gemini-api/docs/api-key),
[LangChain Gemini integration](https://docs.langchain.com/oss/python/integrations/chat/google_generative_ai),
[API troubleshooting](https://ai.google.dev/gemini-api/docs/troubleshooting).
