# ADR 003: Postgres-backed queue with a separate ingestion worker

**Status:** accepted

**Context.** Parsing, chunking and embedding a document takes seconds to minutes. Uploads must return immediately and survive restarts. We do not want to run Redis for this.

**Decision.** The `documents` table is the queue. `POST /api/documents` inserts a row with `status=queued`. A separate worker container (`app.ingestion.worker`) claims one row with `SELECT ... FOR UPDATE SKIP LOCKED`, sets `processing`, and runs `process_document`. On success it swaps chunks and sets `ready` in one transaction; on failure it sets `failed` with a message and leaves the previous version's chunks in place. At start the worker requeues rows stuck in `processing` for more than 30 minutes.

**Why.**
- No extra infrastructure; state is visible in the same table the UI lists.
- `SKIP LOCKED` lets several workers run without double-processing.
- `process_document` is a plain function, so tests call it directly.

**Consequences.**
- Polling (every 5 s), not push.
- Stuck-row reclaim happens only at worker start, not continuously.
- No per-document wall-clock timeout, no retry/backoff scheduling for failed documents, no dead-letter handling.
- At the playbook's 200k-document scale we would move to a real queue with rate-limited embedding workers (ARCHITECTURE.md §3).
