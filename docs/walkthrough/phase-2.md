# Phase 2 — Ingestion

**What I built:** parsers for md/txt (UTF-8 → latin-1 fallback) and PDF
(per-page text via `pypdf`, with a clear error for scanned/image-only
PDFs); a heading-aware token chunker (`tiktoken`) that splits markdown on
headings first, then paragraph → sentence → word, packs pieces to
`CHUNK_TARGET_TOKENS` with `CHUNK_OVERLAP_TOKENS` of trailing overlap, and
keeps `char_start`/`char_end` pointing at the original parsed text; an
`Embedder` interface with a real `OpenAiEmbedder` (batched ≤64, retried)
and a deterministic `FakeEmbedder` for tests; the ingestion pipeline
(parse → chunk → reuse-or-embed → atomic chunk swap) and the worker's real
`SELECT ... FOR UPDATE SKIP LOCKED` poll loop with stuck-row reclaim; and
the `/api/documents` + `/api/chunks` routes (upload with magic-byte and
size validation, re-upload identity rules, ACL-filtered listing, content
and chunk retrieval with 404-not-403 on forbidden chunks).

**Why this shape:** one pure function (`process_document`) that both the
worker and tests call directly, so re-upload/failure behaviour is testable
without running a worker process; offsets are computed from simple
character-span arithmetic (no token-to-character byte-boundary mapping)
so the `text[start:end] == chunk text` invariant is exact and easy to
reason about.

**A real bug this caught:** `DocumentChunk.tsv` was declared with
`insert_default=None`, which makes SQLAlchemy send an explicit `NULL` for
that column on every INSERT — but `tsv` is a Postgres `GENERATED ALWAYS`
column, which rejects *any* supplied value, even `NULL`. Every chunk
insert failed until the column was remapped with `Computed(...)`, which
tells the ORM to omit it from INSERT/UPDATE entirely and let Postgres
compute it. Caught immediately by `test_reupload.py` against a real
Postgres — exactly why that suite runs against real Postgres instead of
mocks.

**What I verified for real:** ran the full suite (49 tests: 29 unit, 20
integration) against a live `pgvector/pgvector:pg16` container — chunker
offset/overlap/heading invariants, parser encoding fallback and PDF page
numbers (built with hand-rolled minimal PDF bytes, no new dependency),
upload validation (wrong type, spoofed PDF magic bytes, oversize, empty,
path traversal), the full re-upload matrix (new/changed/failed/identical),
worker claim + stuck-row reclaim, and ACL-filtered listing/chunk 404s.
`ruff`, `ruff format`, and `mypy --strict` are clean; coverage is 85%
overall and 88–97% on the new `ingestion/`/`embeddings/` modules.

**Left unfinished (expected — later phases):** retrieval (vector/hybrid
search), the answer/chat pipeline, tickets, and the admin/audit pages are
not built yet; the worker does not yet expose Prometheus-style metrics,
only structured logs.
