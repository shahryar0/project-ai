# B-I-FYP

This repository contains both parts of the project:

- `ai_employee/`: FastAPI backend with a basic LangGraph -> Amazon Bedrock model connection.
- `cognitive/`: Next.js frontend scaffold. It is not connected to the backend yet.

The current working step is asking the backend: **What is the capital of France?**
The CEO hierarchy, social agents, tools, memory, and other integrations remain for later.

## First push to GitHub

Extract the prepared `B-I-FYP-source.zip` and open PowerShell inside its
`B-I-FYP` folder. The ZIP contains both source folders without nested Git
metadata, installed dependencies, or local credentials.

Run these commands once from that extracted folder:

```powershell
git init
git add .
git commit -m "Set up frontend and FastAPI LangGraph backend"
git branch -M main
git remote add origin https://github.com/shahryar0/B-I-FYP.git
git push -u origin main
```

The root `.gitignore` excludes virtual environments, `node_modules`, build
output, caches, local `.env` files, and credentials. Dependency manifests,
`cognitive/package-lock.json`, and the backend `.env.example` are included.

## Clone on your home laptop

Install Git and Python 3.10 or newer. Node.js 20.9 or newer is needed only if
you also want to run the frontend.

```powershell
git clone https://github.com/shahryar0/B-I-FYP.git
cd B-I-FYP
```

## Install and run the backend

From the cloned `B-I-FYP` folder, run these first-time setup commands:

```powershell
cd ai_employee
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

The Python dependency versions in `requirements.txt` match the tested setup.
Create the virtual environment on each laptop; do not copy one from another PC.

Your local `.env` defaults to:

```dotenv
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=amazon.nova-micro-v1:0
```

The backend uses the AWS credentials configured on that laptop. Check your
default AWS identity from the same terminal:

```powershell
aws sts get-caller-identity
```

If you use SSO and the session has expired, run `aws sso login`. For a named
profile, set `AWS_PROFILE=your-profile-name` in `.env` and add
`--profile your-profile-name` to the AWS CLI commands. AWS settings are local
to each computer and are not included in the repository. The AWS identity
must have permission to invoke the selected Bedrock model.

Start the backend while inside `ai_employee`:

```powershell
.\.venv\Scripts\python.exe run.py
```

Keep this terminal open. On later runs, this is the only Python command needed.

## Check the live model connection

Open <http://127.0.0.1:8000/docs> in your browser. Expand **POST /chat**, click
**Try it out**, and execute:

```json
{"query": "What is the capital of France?"}
```

A successful HTTP 200 response should look like this (the exact wording can vary):

```json
{
  "answer": "The capital of France is Paris.",
  "model_id": "amazon.nova-micro-v1:0"
}
```

This confirms the API, LangGraph, and live Bedrock model are connected.
<http://127.0.0.1:8000/health> checks only whether the API is running.
Press `Ctrl+C` in the server terminal to stop it.

To check the Python logic with stubbed Bedrock responses, run from `ai_employee`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Install and run the frontend (optional)

Open another terminal in the cloned `B-I-FYP` root:

```powershell
cd cognitive
npm ci
npm run dev
```

Open <http://localhost:3000>. This currently displays the starter frontend;
use the backend API docs to test the model connection.

For more backend details, see [ai_employee/README.md](ai_employee/README.md).
