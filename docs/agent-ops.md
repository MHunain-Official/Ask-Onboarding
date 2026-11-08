# Agent / operator boundaries (Ask Onboarding)

How a human or Cursor agent may safely touch this stack. Goal: **user, node, and agent stay constrained** — least privilege, confirmation on critical steps, and actions that remain reviewable.

Companion Cursor rule: `.cursor/rules/agent-ops-security.mdc` (always on).

## Roles

| Actor | May do | Must not |
|---|---|---|
| **End user (browser)** | Login, chat, upload (if manager+), tickets, admin if role allows | See API keys; bypass ACL; write tickets via the LLM tool alone |
| **Agent (Cursor)** | Edit repo, run local checks, deploy **ask-onboarding** when asked, read-only prod diagnosis | Touch other VPS apps; dump secrets into chat; destroy data without confirmation |
| **Operator (you)** | Approve critical actions, hold `.env`, Vercel/GitHub access | Share production secrets in tickets/chat logs |

## Surfaces

```
Browser → Vercel (Next.js) → VPS API :18083 (FastAPI)
                              ├─ worker (ingestion)
                              └─ Postgres (pgvector) — not public
```

- **Vercel:** frontend only; `BACKEND_URL` points at the VPS API. No DB credentials in `NEXT_PUBLIC_*`.
- **VPS:** `/opt/ask-onboarding`, compose project `ask-onboarding`, file `docker-compose.vps.yml`. Isolated from `schoolos` / `wbs`.
- **DB:** only via app containers or `docker exec ask-onboarding-db …` for ops. Prefer `SELECT` for debugging.

## Confirmation required (critical)

Ask the owner before:

- `docker compose … down`, volume/image prune that might hit other apps  
- `DROP` / `TRUNCATE` / unbounded `DELETE`, restore over live data  
- Editing production secrets, UFW, SSH, reboot  
- Force-push / deleting cloud projects  
- Mass paid eval or full re-embed  

Explicit “deploy ask-onboarding” / “fix this bug on VPS” covers normal `up -d --build` of backend/worker.

## What “monitored” means here

There is no separate SIEM. Reviewability comes from:

- Docker / app structured logs (`request_id`)  
- `llm_calls` (full prompt/response/cost — admin only)  
- `audit_events` (login, upload, delete, rate limit, …)  
- Git history + Vercel deployment history  
- Agent should **summarize** VPS/DB actions in the chat reply (no secret values)

If a key appears in chat or logs: stop using it, rotate per [runbook](runbook.md), record in `SECURITY.md` if process changes.

## Server-side content rules (unchanged product security)

- ACL in SQL retrieval, not in the prompt  
- Uploaded text is untrusted; citations validated server-side  
- Ticket tool does not write; human + CSRF session does  
- See [SECURITY.md](../SECURITY.md) and [threat-model.md](threat-model.md)

## Quick safe deploy (agent checklist)

1. Confirm target is ask-onboarding only  
2. `git` update in `/opt/ask-onboarding`  
3. Rebuild **named** services only (`backend` / `worker` unless told otherwise)  
4. `curl` `/health` and `/ready`  
5. Confirm other compose projects still running  
6. Tell the owner commit SHA + what restarted  
