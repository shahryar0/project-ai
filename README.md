# project-ai

- `ai_employee/`: FastAPI -> LangGraph -> Google Gemini backend.
- `cognitive/`: Next.js frontend scaffold, to connect in a later step.

The current step is a basic model connection: ask **What is the capital of France?**
The CEO hierarchy, social agents, tools, memory, and other integrations remain for later.

## Clone on your laptop

Install Git and Python 3.11 or newer. Node.js 20.9 or newer is needed only for
the optional frontend.

```powershell
git clone https://github.com/shahryar0/project-ai.git
cd project-ai
```

For an existing clone, run `git pull` instead.

## Install the backend dependencies

From the project root:

```powershell
cd ai_employee
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create a virtual environment separately on each laptop. Run the backend with
its `.venv` Python so it uses the dependencies installed for this project.

## Configure Gemini

Create an API key in [Google AI Studio](https://aistudio.google.com/apikey).
Create `ai_employee/.env` if it does not exist:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

If you already have `.env`, add or update these two settings:

```dotenv
GOOGLE_API_KEY=your_actual_google_ai_studio_key
GEMINI_MODEL=gemini-3.5-flash-lite
```

Save the file. The API key stays in your local `.env`, which Git ignores.
The backend uses the Gemini Developer API with this key. Your Google project
must have access and available quota for the selected model. You can change
`GEMINI_MODEL` to another text model available to your key.

## Run and ask the first question

From `ai_employee`:

```powershell
.\.venv\Scripts\python.exe run.py
```

Keep the terminal open. Open <http://127.0.0.1:8000/docs>, expand **POST /chat**,
click **Try it out**, and execute:

```json
{"query": "What is the capital of France?"}
```

Expected response shape (the model's wording may vary):

```json
{
  "answer": "The capital of France is Paris.",
  "model_id": "gemini-3.5-flash-lite"
}
```

A successful response confirms FastAPI, LangGraph, and the live Gemini model
are connected. <http://127.0.0.1:8000/health> checks the API only; it does not
contact Gemini or verify the key. Press `Ctrl+C` to stop the server.

Restart the server after changing the key or model in `.env`.

## Checks and errors

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The normal tests mock the Gemini SDK and do not make model requests. The CEO
smoke test calls the live model only when `RUN_LIVE_MODEL_TESTS=1` is explicitly
set in your terminal and a valid key is configured.

- HTTP 429: Gemini quota or rate limit reached; check your AI Studio project limits.
- HTTP 503: missing key, access denied, connection problem, or temporary service failure.
- HTTP 502: invalid key/request settings, unavailable model, or no text returned by the model.

See [the backend README](ai_employee/README.md) for more details.

## Optional frontend

Open another terminal in the project root:

```powershell
cd cognitive
npm ci
npm run dev
```

Open <http://localhost:3000>. The frontend is currently a starter page; use
`/docs` on port 8000 to test the model.

The root `.gitignore` excludes `.env`, virtual environments, `node_modules`,
caches, generated build files, and local credentials. The dependency files and
`.env.example` are included so each laptop can install its own environment.
