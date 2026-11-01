# AI Employee backend

First step: **FastAPI -> LangGraph -> Amazon Bedrock** for a basic question and
answer. The graph is `START -> model -> END`.

The default is `amazon.nova-micro-v1:0` in `us-east-1`, from the second example
in `txtbase.txt`. Change `BEDROCK_MODEL_ID` in `.env` to select another model.

## Run on Windows (PowerShell)

On another laptop, first clone a repository containing these updated backend
files. Local edits must be committed and pushed before a clone can include them.
AWS credentials and virtual environments are configured separately on each PC.

Open PowerShell in the cloned `ai_employee` folder. On a fresh clone, create
the virtual environment first:

```powershell
python -m venv .venv
```

Then install dependencies and start the server (adjust the folder path to your clone):

```powershell
cd D:\B-I-FYP\ai_employee
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# First time only, if .env does not exist:
Copy-Item .env.example .env
.\.venv\Scripts\python.exe run.py
```

The model uses your existing AWS credentials. For a named AWS CLI profile,
uncomment `AWS_PROFILE` in `.env` and enter its name. Sign in using the method
already configured for that profile (SSO, console login, or access keys).
The selected AWS identity needs permission to invoke your Bedrock model.

Check the default AWS identity from the same terminal:

```powershell
aws sts get-caller-identity
```

This should return your account and ARN. If an SSO session has expired, run
`aws sso login` and retry. For a named profile, add `--profile your-profile-name`
to those AWS commands and set the same `AWS_PROFILE` in `.env`.

## Ask the first question

Open <http://127.0.0.1:8000/docs>, expand **POST /chat**, click **Try it out**,
and execute:

```json
{"query": "What is the capital of France?"}
```

Or run this in a second PowerShell terminal while the server is running:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/chat -Method Post -ContentType 'application/json' -Body '{"query":"What is the capital of France?"}'
```

Expected response shape (the wording comes from the model):

```json
{
  "answer": "The capital of France is Paris.",
  "model_id": "amazon.nova-micro-v1:0"
}
```

`GET /health` checks the API only. The first `/chat` request creates the model
and tests the AWS connection. Missing credentials return HTTP 503; a Bedrock
rejection returns HTTP 502 with the AWS error.
A successful `/chat` response with an answer about Paris confirms the API,
LangGraph, and live Bedrock model are connected. Keep the server terminal open;
press `Ctrl+C` to stop it.

## Scope and checks

The CEO, social agents, tools, memory, MCP, and database files are kept for
later. This endpoint uses a simple assistant prompt and each question is
independent. The server listens on localhost for this initial connection test.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The API tests use stubbed Bedrock responses, without making AWS requests. The
existing CEO smoke test runs only if `BEDROCK_MODEL_ID` is explicitly exported
in your shell; that test exercises the separate CEO path.

References: [LangGraph graph API](https://docs.langchain.com/oss/python/langgraph/graph-api),
[Bedrock integration](https://docs.langchain.com/oss/python/integrations/chat/bedrock),
[FastAPI request bodies](https://fastapi.tiangolo.com/tutorial/body/).
