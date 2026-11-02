# AI Cognitive Mesh: Frontend Master Plan
### Step-by-step build plan (functionality first, design later)

**For:** Codex / Claude Code (implementing agent) and the project owner.
**Backend:** Python/FastAPI, already in this repo (`ai_employee/`, `app/api/main.py`). See `AGENT_HIERARCHY.md` and `AGENT_HIERARCHY_V2_SPEC.md`.
**Frontend:** new Next.js app in `ai_employee/frontend/`.
**Auth:** Clerk (Google, GitHub, LinkedIn login + Organizations) + local DB owned by the backend.

---

## 0. Rules for the implementing agent (read first)

1. Work **one phase at a time**. At the end of each phase: run lint, typecheck, build, and the phase's acceptance checks, then **stop and report**. Do not start the next phase without the owner saying go.
2. **Minimal UI only.** Use ready-made **shadcn/ui** components with default styling. No custom visual design, no GSAP, no illustrations, no custom theme. Visual polish is a later project. Layout structure and working behaviour are the only goals.
3. **No frontend mock data.** Every page talks to the real FastAPI backend. If an endpoint does not exist yet, build it in the backend (even if it returns an empty list or seeded rows) and wire the page to it.
4. **Never read, print or commit env files** (`.env`, `.env.local`, backend `.env`). Ask the owner for any missing non-sensitive value (for example the Clerk issuer URL).
5. **Never expose secrets in client code** (`CLERK_SECRET_KEY`, connector tokens). Connector OAuth tokens live only in the backend.
6. Prefer **Server Components**; add `"use client"` only where interaction needs it.
7. Keep changes small and reviewable: one concern per commit.
8. If something in this plan conflicts with the current official Clerk, Next.js or shadcn docs, follow the official docs and tell the owner what differed.

The pages and folder structure recomeneded but you will followit on the bases of our backend 
the clerk has an offila promppt do follow it when implementing the clerk # Add Clerk Authentication to Next.js

Set up Clerk authentication in this Next.js project with the Clerk CLI.

## Existing authentication

Before `init`, inspect for existing auth — never env files. If found, stop and get approval for migrating users, passwords/OAuth, routes, tokens, sessions, and rollout. Until then, do not run `init` or change providers, middleware, or auth routes.

## Why the CLI

`npx -y clerk@latest init` needs no Clerk account. It detects agent environments and runs non-interactively, so no keys pass through the conversation. Signed out, it provisions a claimable application, writes dev keys to `.env.local`, and configures the SDK, provider, middleware, and auth routes. Signing in later claims it.

Before claiming, `npx -y clerk@latest enable orgs` and `npx -y clerk@latest config patch` work; Billing and some auth settings require claiming.

Agent mode installs Clerk agent skills globally and links supported agent tools.

## Quick setup

Show this checklist and wait for approval:

```
Here's what I'll do to get you set up with Clerk.

1. Set up Clerk in this project, or scaffold a new Next.js app with Clerk if this directory is empty
2. Start your app with Clerk installed.
3. Stay signed out and optionally sign in later to claim the app, or sign in first to use an existing Clerk application.

Shall I proceed?
```

## Step 1: Run the Clerk CLI

No install needed — run Clerk CLI commands through the project's package runner: `npx -y clerk@latest <command>`, `pnpm dlx clerk@latest`, `bunx clerk@latest`, or `yarn dlx clerk@latest` (yarn 2+ only).

## Step 2: Sign in to Clerk (optional)

Stay signed out by default. Sign in before `init` only to use an existing Clerk application:

```bash
npx -y clerk@latest auth login
```

Pause while the user completes the login flow.

Then run `npx -y clerk@latest apps list --json`, show the names and IDs, and ask which application to use. Never choose for them.

## Step 3: Initialize Clerk

If Step 2 selected an application, run:

```bash
npx -y clerk@latest init --app <application_id>
```

Otherwise, for an existing Next.js project, run:

```bash
npx -y clerk@latest init
```

`npx -y clerk@latest init` is the default setup action, signed in or not. It detects the framework and package manager and applies the Next.js setup described above. Do not pass `--framework` or `--pm` for existing projects unless the user explicitly wants to override detection or the CLI asks for those values.

If the directory is empty, ask the user which package manager they want to use. If they have no preference, use npm. Then scaffold a fresh Next.js app:

```bash
npx -y clerk@latest init --framework next --pm <package-manager>
```

If the directory has a leftover lockfile, match the package manager to it (`pnpm-lock.yaml` → `pnpm`, `yarn.lock` → `yarn`, `bun.lock`/`bun.lockb` → `bun`, `package-lock.json` → `npm`) instead of asking.

## Step 4: Fall back to manual setup when init is incomplete

Only do this if `npx -y clerk@latest init` has already run and failed — do not start here.

If `npx -y clerk@latest init` reports an error or does not finish the setup, finish manually: install `@clerk/nextjs`, create a middleware file that calls `clerkMiddleware()` from `@clerk/nextjs/server` (see Critical rules for the filename), and wrap the app with `<ClerkProvider>` as shown in Step 5.

## Step 5: Ensure clear auth controls are visible

Make sure the app has clear sign-in, sign-up, and signed-in user controls so the user can create and recognize their first account. Integrate them into the existing layout or navigation so they feel natural.

Use Clerk components from `@clerk/nextjs` such as `SignInButton`, `SignUpButton`, `Show`, and `UserButton`. Show sign-in and sign-up actions when signed out, and a user button when signed in. `<Show>` reads the request, so wrap it in `<Suspense>`. For example, in `app/layout.tsx`:

```tsx
import { ClerkProvider, SignInButton, SignUpButton, Show, UserButton } from '@clerk/nextjs'
import { Suspense } from 'react'
import './globals.css'

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ClerkProvider>
          <header>
            <Suspense>
              <Show when="signed-out">
                <SignInButton />
                <SignUpButton />
              </Show>
              <Show when="signed-in">
                <UserButton />
              </Show>
            </Suspense>
          </header>
          {children}
        </ClerkProvider>
      </body>
    </html>
  )
}
```

If clear auth controls already exist, reuse or adapt them instead of duplicating them.

## Step 6: Verify the setup

After `npx -y clerk@latest init` completes, run:

```bash
npx -y clerk@latest doctor
```

Then start the app, confirm the sign-in, sign-up, and signed-in user controls are visible, test the sign-in and sign-up flow, and fix any issues reported by the CLI.

Bot protection can block sign-ups in browsers you automate. If you test a new accountless app in one, run `npx -y clerk@latest users create --email <unique>+clerk_test@example.com --password <random-16-char-alphanumeric> --yes`, then sign in. If asked for a verification code, enter 424242. Tell the user you created this test user. For an existing app, ask the user before creating users. To test sign-up, use @clerk/testing: https://clerk.com/docs/guides/development/testing/playwright/overview.md

## Step 7: If using shadcn/ui

If `components.json` exists in the project root and Clerk components are used, install `@clerk/ui` with the project's package manager:

```bash
npm install @clerk/ui
```

Apply the theme in `app/layout.tsx`: import `shadcn` from `@clerk/ui/themes` and set `appearance={{ theme: shadcn }}` on `<ClerkProvider>`.

Add to global CSS:

```css
@import '@clerk/ui/themes/shadcn.css';
```

## Critical rules

- Setup is `npx -y clerk@latest init`, signed in or not. Do not install `@clerk/nextjs` or hand-write setup unless it has run and failed
- `npx -y clerk@latest init` writes `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and `CLERK_SECRET_KEY` to `.env.local`. Do not ask the user to copy keys
- Name the middleware file by the `next` version in `package.json`: `proxy.ts` on Next.js 16+, `middleware.ts` on 15 and below. The contents are identical; `npx -y clerk@latest init` creates it
- `auth()` from `@clerk/nextjs/server` is async. Always `await auth()`
- `ClerkProvider` goes inside `<body>`, not wrapping `<html>`
- When `next.config` sets `cacheComponents: true` (the `create-next-app` default), `next build` fails on request data read outside `<Suspense>`. Wrap `<Show>` in a Server Component and any Server Component that calls `auth()` or `currentUser()` in `<Suspense>`, as close to the auth-dependent UI as possible
- Never expose `CLERK_SECRET_KEY` in client code
- Use `@clerk/nextjs`, not `@clerk/clerk-react`
- Do not read or print existing environment variable files; ask the user for any missing non-sensitive configuration

Docs: https://clerk.com/docs/cli https://clerk.com/docs/llms.txt

## After setup

Have the user sign up as their first test user in the nav. After signup succeeds and a profile icon appears, congratulate them. If a "Configure your application" callout appears, tell them to click it. Then recommend exploring: Organizations (https://clerk.com/docs/guides/organizations/overview), Components (https://clerk.com/docs/reference/components/overview), Dashboard (https://dashboard.clerk.com/).

to let you know i have 3 oauth token  from google linkedin and github  so maek it accordingly the 
---

## 1. User journey (product flow)

| # | Step | Where |
| --- | --- | --- |
| 1 | Sign up / log in (Google, GitHub, LinkedIn, or email) | `/sign-in`, `/sign-up` |
| 2 | Organization setup: company + workspace profile | `/onboarding` |
| 3 | Connect accounts (LinkedIn, Gmail, Slack, ...)  Notion
Slack
Telegram
Custom webhook
RSS feeds
GitHub
Trello
Linear
Airtable LinkedIn, X, Facebook, Instagram, TikTok, WhatsApp Business  Google Drive
Google Docs
Google Sheets
Gmail
Google Calendar
Outlook
HubSpot
Jira
Composio| `/connectors` |
| 4 | Dashboard: overview of connected capabilities | `/overview` |
| 5 | Activate AI employees and agent swarms | `/employees`, `/swarms` |
| 6 | Create tasks; agents execute | `/tasks` |
| 7 | Owner approves sensitive actions | `/approvals` |
| 8 | Monitor results and history | `/activity`, `/history` |

**Important distinction:** "Sign in with LinkedIn" (Clerk, identity only) is **not** the same as the **LinkedIn connector** (backend OAuth with posting permissions). They are two separate OAuth apps and flows.

---

## 2. Information architecture

### 2.1 Sidebar (use shadcn `Sidebar`)

```
WORKSPACE
  Overview          /overview
  Connectors        /connectors
  AI Employees      /employees
  Agent Swarms      /swarms
  Tasks & Workflows /tasks
  Approvals         /approvals      (badge: pending count)

INSIGHTS
  Activity Monitor  /activity
  Execution History /history
  Usage & Analytics /analytics

PREFERENCES
  Settings          /settings
```

Sidebar header: Clerk `<OrganizationSwitcher />`. Sidebar footer: Clerk `<UserButton />`.

### 2.2 Phases (matches the owner's plan)

| Phase | Pages | Priority |
| --- | --- | --- |
| 0 | Scaffold, Clerk, shadcn, API plumbing | First |
| 1 | Sign in, Sign up, Organization setup | First |
| 2 | Connector Center + OAuth | First |
| 3 | Overview dashboard | First |
| 4 | AI Employees, Employee detail (+ CEO chat) | Second |
| 5 | Agent Swarms, Tasks & Workflows | Second |
| 6 | Approvals, Activity Monitor, History | Second |
| 7 | Analytics, Settings, Billing | Later |

---

## 3. Architecture

### 3.1 Repo layout

```
ai_employee/
  app/                      # existing FastAPI backend
  frontend/                 # new Next.js app (all Clerk/shadcn commands run here)
    src/
      app/
        (auth)/sign-in/[[...sign-in]]/page.tsx
        (auth)/sign-up/[[...sign-up]]/page.tsx
        onboarding/page.tsx
        (app)/layout.tsx            # sidebar shell, requires auth + org + onboarding done
        (app)/overview/page.tsx
        (app)/connectors/page.tsx
        (app)/employees/page.tsx
        (app)/employees/[id]/page.tsx
        (app)/swarms/page.tsx
        (app)/tasks/page.tsx
        (app)/tasks/[id]/page.tsx
        (app)/approvals/page.tsx
        (app)/approvals/[draftId]/page.tsx
        (app)/activity/page.tsx
        (app)/history/page.tsx
        (app)/analytics/page.tsx
        (app)/settings/page.tsx
      components/
        ui/                         # shadcn generated
        app-sidebar.tsx
        page-header.tsx
        empty-state.tsx
        error-state.tsx
      lib/
        api/client.ts               # typed fetch wrapper
        api/schema.d.ts             # generated from FastAPI OpenAPI
        api/queries.ts              # TanStack Query hooks
      proxy.ts or middleware.ts     # Clerk (name depends on Next version, see 4.2)
```

### 3.2 Stack

| Concern | Choice |
| --- | --- |
| Framework | Next.js (App Router), TypeScript strict |
| UI | shadcn/ui + Tailwind, `lucide-react` icons, `sonner` toasts |
| Auth | `@clerk/nextjs` (never `@clerk/clerk-react`) |
| Data fetching | Server Components for first load; TanStack Query for interactive/polled data |
| API types | `openapi-typescript` generated from FastAPI `/openapi.json` (script `gen:api`) |
| Forms | `react-hook-form` + `zod` via shadcn `Form` |
| Later (NOT now) | GSAP, custom theme, charts polish |

### 3.3 Auth bridge: Clerk to FastAPI to local DB

```
Browser (Clerk session)
   | Authorization: Bearer <Clerk session JWT>   (useAuth().getToken() client / auth().getToken() server)
   v
FastAPI dependency get_principal()
   - verifies JWT signature via Clerk JWKS (cached), checks issuer + expiry
   - reads user id and org id/role from claims (see note)
   - upserts local User + Organization rows on first request (lazy provisioning)
   - returns Principal{user_id, org_id, org_role}
   v
Every query is scoped by org_id (tenant_id)
```

Notes:
- **Claim shape:** Clerk session token versions name org claims differently. Check the current Clerk docs and implement **one** parser function `parse_org_claims(claims)`; do not guess in several places.
- **Roles:** map Clerk org roles to backend permissions: `org:admin` = owner/approver, `org:member` = can create tasks, cannot approve or connect accounts.
- **No org selected:** backend returns `403 {"error":{"code":"ORG_REQUIRED"}}`; frontend redirects to `/onboarding`.
- **Local DB** stores: `users`, `organizations` (clerk ids + workspace profile), `connected_accounts`, `employees`, `swarms`, `tasks`, `drafts`, `approvals`, `audit_events` (see V2 spec section 4.2). Clerk remains the source of truth for identity and membership; do not copy passwords or tokens.
- Webhooks (`/webhooks/clerk`, verified) for user/org deletion are **later**; lazy upsert is enough for now.

### 3.4 API conventions (backend and frontend must agree)

- Base path `/api/v1/...`; JSON only.
- Error shape: `{"error": {"code": "STRING", "message": "human readable", "details": {}}}`.
- Lists: `{"items": [...], "next_cursor": "..." | null}` (cursor pagination).
- Long operations return `202` with an id; the client polls `GET` on that id.
- Frontend rules: `401` -> redirect to `/sign-in`; `403 ORG_REQUIRED` -> `/onboarding`; other errors -> `error.tsx` / toast with `error.message`.
- CORS: allow only the frontend origin. Alternative: Next.js `rewrites` to proxy `/backend/*` to FastAPI. Pick one, document it in the README.

---

## 4. Phase 0: Preflight and scaffold

### 4.1 Preflight (follow the Clerk setup instructions)

1. **Check for existing auth** in the repo (code only, never env files). The backend currently has none. If any auth/provider/middleware is found, **stop and get the owner's approval** before running `init`.
2. **Show this checklist and wait for approval:**

```
Here's what I'll do to get you set up with Clerk.

1. Set up Clerk in the new frontend/ Next.js app (scaffold it if the directory is empty)
2. Start the app with Clerk installed
3. Stay signed out and optionally sign in later to claim the app, or sign in first to use an existing Clerk application

Shall I proceed?
```

3. Ask which package manager to use (default npm; if a lockfile exists, match it).
4. Ask whether to use an **existing Clerk application** (`npx -y clerk@latest auth login`, then `apps list --json`, let the owner choose; never choose for them) or a new claimable app.

### 4.2 Scaffold

From `ai_employee/frontend/`:

```bash
npx -y clerk@latest init --framework next --pm <package-manager>   # empty dir
# or, if a Next.js app already exists here:
npx -y clerk@latest init
# with a chosen existing app:
npx -y clerk@latest init --app <application_id>
```

- `init` writes keys to `.env.local` and sets up SDK, provider, middleware and routes. **Do not ask the owner to copy keys. Do not open `.env.local`.**
- Only if `init` fails, set up manually: install `@clerk/nextjs`, add `clerkMiddleware()` from `@clerk/nextjs/server`, wrap with `<ClerkProvider>`.
- **Middleware filename** depends on `next` version in `package.json`: `proxy.ts` on Next 16+, `middleware.ts` on 15 and below.
- `ClerkProvider` goes **inside `<body>`**, not around `<html>`.
- `auth()` is async: always `await auth()`.
- If `next.config` has `cacheComponents: true`, wrap request-reading UI (`<Show>`, anything calling `auth()`/`currentUser()`) in `<Suspense>` as close to that UI as possible, or `next build` fails.
- Run `npx -y clerk@latest doctor`, then start the app and confirm sign-in/sign-up/user controls render.

### 4.3 Enable Organizations and social login

```bash
npx -y clerk@latest enable orgs
```

- Enable social connections **Google, GitHub, LinkedIn (OIDC)** in the Clerk dashboard (SSO/Social connections). Some auth settings may require **claiming** the app: if so, ask the owner to sign in and claim it, or to toggle them in the dashboard. Check https://clerk.com/docs/cli for whether `clerk config patch` can do it.
- Make sure the session token includes organization id and role.

### 4.4 shadcn

```bash
npx shadcn@latest init
npx shadcn@latest add sidebar button card input badge table tabs dialog sheet dropdown-menu select skeleton sonner form label separator avatar switch textarea alert tooltip
```

- If `components.json` exists and Clerk components are used: install `@clerk/ui`, set `appearance={{ theme: shadcn }}` on `<ClerkProvider>` (`import { shadcn } from '@clerk/ui/themes'`), and add `@import '@clerk/ui/themes/shadcn.css';` to global CSS.

### 4.5 API plumbing

- Add `lib/api/client.ts`: typed wrapper that attaches `Authorization: Bearer <token>` and normalizes the error shape.
- Add `gen:api` script (OpenAPI to `schema.d.ts`) and `dev:all` note in README to run backend (`uvicorn`) and frontend together.
- Backend: add CORS, `app/auth/clerk.py` (`get_principal`), `GET /api/v1/me`. Ask the owner for the **Clerk issuer / Frontend API URL** (non-sensitive) and add it as backend config.
- Add a root `README` section: how to run both, required env var **names** (no values).

**Acceptance (Phase 0):**
- Frontend runs; `/sign-in` renders Clerk.
- Signed-in call to `GET /api/v1/me` returns the principal; unsigned call returns 401; bad token returns 401.
- `lint`, `typecheck`, `build` pass.

---

## 5. Phase 1: Login, Signup, Organization setup

### 5.1 Auth pages
- `/sign-in` and `/sign-up`: Clerk `<SignIn />` / `<SignUp />` centered, nothing else. Social buttons (Google, GitHub, LinkedIn) come from Clerk config. Email stays enabled as a fallback.
- Configure Clerk URLs through `ClerkProvider` props (`signInUrl`, `signUpUrl`, after-sign-in/up redirect to `/onboarding`). Do not read env files to do this.

### 5.2 Route protection (middleware)
- Public: `/sign-in(.*)`, `/sign-up(.*)`. Everything else requires auth.
- Signed in but **no active org** -> redirect to `/onboarding`.
- Signed in, org active, onboarding **not completed** (from `GET /me`) -> `/onboarding`.
- Keep middleware logic light: only the auth/org checks. The onboarding-completed check can live in the `(app)/layout.tsx` Server Component to avoid a backend call in middleware.

### 5.3 Onboarding (`/onboarding`, single page, 2 steps with shadcn `Tabs` or simple state)
1. **Organization:** Clerk `<CreateOrganization />` (or `<OrganizationList />` if the user already has orgs). After creation set the org active.
2. **Workspace profile** (shadcn `Form`): company description, industry, audience, tone, language, timezone. Save with `PUT /api/v1/workspace/profile`. This is the **brand profile** the agents use (`name` comes from the Clerk org name).
3. On save: backend sets `onboarding_completed=true`; redirect to `/connectors`.

### 5.4 Backend work
- `GET /api/v1/me` -> `{user, organization|null, role, onboarding_completed}`
- `GET/PUT /api/v1/workspace/profile` (admin only for PUT)
- Local DB tables: `users`, `organizations`, `workspace_profiles` (migrations).
- `/chat` becomes authenticated and org-scoped; brand profile is loaded from the DB instead of the request body (keep optional override for now).

**Acceptance (Phase 1):**
- New user signs up with Google, GitHub, LinkedIn and email, lands on `/onboarding`.
- Creating an org + saving profile redirects to `/connectors`.
- Revisiting `/` while signed out goes to `/sign-in`; signed in without org goes to `/onboarding`.
- Local DB has user, organization and profile rows. Org A cannot read org B's profile (backend test).
- Member role cannot `PUT` the profile (403 test).

---

## 6. Phase 2: Connector Center

### 6.1 UI (reference screenshot: "Apps and integrations")
Page title **Connectors**, subtitle "Extend and automate your workflows with integrations".
- Top bar: search input, **Filter** (category, status), **Sort by** (name, status).
- Responsive card grid (4 columns on desktop, 1 on mobile). Each shadcn `Card`:
  - logo (simple image or lucide icon placeholder), external-link icon (provider docs)
  - name, short description (2 to 3 lines)
  - footer: **Manage** (outline button with gear icon) and either **Connect** (primary) or **Connected** (outline with check icon)
  - Status `Badge` for `needs_reauth`, `error`, `coming_soon`
- **Manage** opens a shadcn `Sheet`: account name, status, connected by, connected at, scopes, **Disconnect** (confirm `Dialog`), **Reconnect**.
- Group by category with a `Tabs` row or section headings.

### 6.2 Categories and catalog

| Category | Platforms |
| --- | --- |
| Social Media | LinkedIn, Instagram, Facebook, Threads |
| Communication | Gmail, Slack, Discord |
| Productivity | Google Drive, Notion |
| CRM | HubSpot, Salesforce |
| Marketing | Meta Ads |

The catalog is **defined in the backend** (not hardcoded in the UI). Each entry has `availability: "live" | "coming_soon"`. Start with only **LinkedIn** as `live`; the rest render with a disabled **Coming soon** button. Next live connectors are added by flipping availability once their backend adapter exists (order set by the owner; suggested: LinkedIn, Facebook, Instagram, Gmail, Slack).

### 6.3 OAuth flow (backend-driven)

```
UI Connect click
  -> POST /api/v1/connectors/{id}/oauth/start       (admin only)
  <- {authorization_url}
Browser redirects to provider
Provider -> GET /api/v1/connectors/{id}/oauth/callback?code&state   (backend)
  - validates signed `state` (contains org id, user id, nonce, expiry)
  - exchanges code, stores tokens encrypted (token_ref pattern), creates connected_account
  - redirects to {FRONTEND_URL}/connectors?connected={id}
UI shows toast and refetches list
```

- Frontend never sees provider tokens or client secrets.
- `state` is single-use, expires in minutes, bound to the org and user.
- Failure redirects to `/connectors?error={code}` and shows an `Alert`.
- Only `org:admin` can connect, reconnect or disconnect; members see a read-only grid.

### 6.4 Backend work
- Endpoints: `GET /connectors` (catalog + this org's status), `GET /connectors/{id}`, `POST /connectors/{id}/oauth/start`, `GET /connectors/{id}/oauth/callback`, `DELETE /connectors/{id}` (disconnect/revoke), `POST /connectors/{id}/reconnect`.
- Tables: `connector_definitions` (or code registry), `connected_accounts` (`org_id`, `platform`, `external_account_id`, `display_name`, `token_ref`, `scopes`, `status`, `connected_by`).
- Token storage: encrypted at rest; DB holds a reference or ciphertext only. Never log tokens.
- First adapter: **LinkedIn** (posting scopes, separate from Clerk's login OAuth app). Verify scopes and app review requirements in the current LinkedIn docs.

**Acceptance (Phase 2):**
- Grid renders from the backend catalog; search, filter, sort work.
- LinkedIn Connect completes the full flow against a test account; card flips to **Connected** after redirect.
- Disconnect revokes and updates the card.
- Member cannot start OAuth (403). Org B cannot see Org A's connections.
- Tokens never appear in any API response or log (test).

---

## 7. Phase 3: Overview (dashboard)

Single backend aggregate to avoid request waterfalls: `GET /api/v1/overview`.

```json
{
  "connectors": {"connected": 1, "total_live": 1, "needs_attention": 0},
  "employees": {"active": 3, "total": 3},
  "approvals": {"pending": 4},
  "tasks": {"running": 1, "awaiting_approval": 2, "failed_24h": 0},
  "recent_activity": [{"id","at","actor","summary","status"}]
}
```

UI (shadcn `Card` x4 + one `Table`): connected capabilities, active employees, pending approvals (links to `/approvals`), running tasks, recent activity list. Empty-state card when no connector is connected: "Connect an account" button to `/connectors`.

**Acceptance:** numbers match DB state; each card links to its page; loads with one request; skeleton while loading.

---

## 8. Phase 4: AI Employees and Employee detail

### 8.1 List (`/employees`)
Table or cards from `GET /employees`: name, role, reports to, status (`active/inactive/error`), required connectors (chips; red if missing), toggle **Activate** (admin only).

Seed the default team from the agent hierarchy: **CEO**, **Social Media Manager**, **Content Writer** (and later Brand Guardian, Visual Designer). Seeded per org on first access.

### 8.2 Detail (`/employees/[id]`)
Tabs: **Overview** (role, description, tools, requirements), **Chat** (CEO only for now), **Activity** (recent runs).

**CEO chat (first real end-to-end agent feature):**
- Textarea + send; calls the existing `POST /chat` (authenticated, org-scoped, brand from DB).
- Show the returned `answer`, `previews` (platform, text, character count, visual idea, warnings, draft flags) and `tool_calls` trace in a collapsible `Accordion`.
- Show a clear **"Draft: not published"** label. No publish buttons here.
- Disable send and show a spinner while the request is running; handle timeouts with an `Alert`.

### 8.3 Backend work
- `GET /employees`, `GET /employees/{id}`, `PATCH /employees/{id}` (`enabled`).
- Block activation if required connectors are missing (return a clear error code `MISSING_CONNECTOR`).
- `/chat` must persist drafts per V2 spec phase 1 (draft ids, versions) so previews can flow into `/approvals`.

**Acceptance:** toggling persists; CEO chat returns real previews from the agents; drafts appear in the DB with `pending_review`-ready state.

---

## 9. Phase 5: Agent Swarms and Tasks & Workflows

### 9.1 Swarms (`/swarms`)
Minimal CRUD: name, objective, member employees (multi-select), status. A swarm is a **named group of employees with a shared objective**; execution still goes through the CEO/Manager orchestration. Keep to a table + create `Dialog`.

### 9.2 Tasks (`/tasks`, `/tasks/[id]`)
- List table: title, assigned to (employee or swarm), status, created, updated. Filters: status. Cursor pagination.
- **New task** `Dialog`: instruction text, assignee, optional platforms.
- Status lifecycle: `queued -> running -> awaiting_approval -> approved/rejected -> completed | failed`.
- Detail page: instruction, status timeline, tool-call trace, resulting drafts (links to `/approvals/{draftId}`), errors.
- Create returns `202 {task_id}`; the UI polls `GET /tasks/{id}` with TanStack Query `refetchInterval` **only while status is queued/running** (stop polling otherwise).

### 9.3 Backend work
- Tables: `swarms`, `swarm_members`, `tasks`, `task_events`.
- Background execution of the existing workflow runner (start with FastAPI `BackgroundTasks` or a simple worker loop; keep the interface so it can move to a queue later).
- Tasks store `run_id`, provider used, fallback flag (from the runner result).

**Acceptance:** creating a task runs the real workflow, status advances, drafts are linked, failures show a readable error.

---

## 10. Phase 6: Approvals, Activity Monitor, History

### 10.1 Approvals (`/approvals`, `/approvals/[draftId]`)
This implements the human-in-the-loop rules from `AGENT_HIERARCHY_V2_SPEC.md` section 5.
- List: pending drafts (platform, campaign, created, QA warnings count). Sidebar badge shows pending count.
- Detail: draft text per platform (editable `Textarea`), character count, visual idea, QA issues (`Alert`), version history.
- Actions (admin only): **Edit** (creates a new version, voids approval), **Request changes** (comment, optional agent revision), **Approve** (sends `{version, content_hash}`), **Reject** (reason).
- After approval: show state `approved`. If the platform connector is not connected or publishing is not built yet, show "Approved, waiting for connector". **No publish button until the publisher exists (V2 spec phase 4).**
- Approval is always for the **exact version shown**; if the version changed meanwhile the API returns `409` and the UI reloads the draft.

### 10.2 Activity Monitor (`/activity`)
Live view: employees' current status, running tasks, latest execution logs and errors. Start with polling every 5 seconds on this page only (pause when the tab is hidden). SSE can replace it later.

### 10.3 History (`/history`)
Table of past executions: task, result (completed/failed/rejected), employee, provider, duration, finished at. Filters (status, date range), cursor pagination, row opens task detail with the full trace.

### 10.4 Backend work
- Approval endpoints per V2 spec 5.3 (`approve`, `reject`, `request-changes`, `PATCH /drafts/{id}`), audit events for each action.
- `GET /activity` (live snapshot), `GET /history` (paginated, filterable).
- Role enforcement tests: members get 403 on approve/reject.

**Acceptance:** edit then approve flow works; stale approve returns 409 and the UI recovers; audit log records every action; history filters work.

---

## 11. Phase 7: Analytics, Settings, Billing (later)

- **Analytics:** usage per employee, tasks per status, provider/fallback counts, token/cost estimates if available. Simple tables first; charts later.
- **Settings:** workspace profile edit (reuse Phase 1 form), members and roles via Clerk `<OrganizationProfile />`, connector defaults.
- **Billing:** placeholder page only; Clerk Billing may require claiming the app. Do not build until the owner decides the pricing model.

---

## 12. Efficiency and quality rules (apply in every phase)

**Performance**
- Server Components by default; client components only for forms, polling and interaction.
- No request waterfalls: aggregate endpoints for dashboards; parallel fetches in Server Components.
- TanStack Query: set sensible `staleTime`; poll only when needed and stop when the state is final.
- Lists are paginated (cursor); never load unbounded tables.
- Use `loading.tsx` with shadcn `Skeleton`, and `error.tsx` per route group.
- `next/font`, `next/image`, dynamic import for heavy components (editors, large dialogs).
- Do not add GSAP, chart libraries or other heavy deps until their phase.

**Security**
- JWT verified on every backend request; org id always from the verified token, never from the client body.
- Admin-only actions enforced on the **backend**, not just hidden in the UI.
- OAuth `state` signed, single-use, short-lived. No tokens in logs, URLs or responses.
- CORS restricted to the frontend origin.

**Code quality**
- TypeScript strict; no `any` without a comment.
- Generated API types are the only source of request/response types.
- Each page: loading, empty and error states exist (plain shadcn components).
- Backend: pytest for auth, tenant isolation, role checks, OAuth state, approvals. Frontend: at least smoke tests for sign-in redirect and the connectors grid (Playwright or Vitest, owner's choice).

**Definition of done for every phase**
1. `lint`, `typecheck`, `build` pass; backend tests pass.
2. Acceptance list for the phase verified manually and listed in the report.
3. README updated with any new env var **names** and run steps.
4. Short report: what was built, what was skipped, open questions.

---

## 13. Explicitly NOT now
Custom design system, animations (GSAP), landing page, dark-mode polish, real publishing to social networks, auto-approval, billing, webhooks, SSE/WebSockets, mobile app. These come after the functional flow works end to end.

---

## 14. Decisions needed from the owner

1. Package manager (default npm).
2. Use an existing Clerk application or create a new claimable one? (Social login settings may need the app claimed.)
3. CORS direct, or Next.js rewrite proxy to the backend?
4. Which connector is `live` after LinkedIn (Facebook, Instagram, Gmail, Slack)?
5. Local DB for now: SQLite, or Postgres from the start?
6. Who can approve: only `org:admin`, or custom roles later?
7. Provide the Clerk issuer / Frontend API URL (non-sensitive) for backend JWT verification.

