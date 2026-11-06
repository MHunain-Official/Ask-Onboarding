# Phase 3 — Retrieval

**What I built:** ACL-filtered vector search (`vector_search.py`, cosine
similarity via pgvector's `<=>` distance operator, converted with
`similarity = 1 - distance`); ACL-filtered full-text search
(`keyword_search.py`, `websearch_to_tsquery` + `ts_rank_cd` against the
generated `tsv` column); a pure, dependency-free Reciprocal Rank Fusion
function (`rrf.py`, `score = Σ 1/(60+rank)`) that `hybrid.py` uses to
combine the two rankings (or passes vector ranking through unchanged when
`HYBRID_ENABLED=false`); the deterministic no-answer gate
(`gate.py::passes_similarity_gate`); and `POST /api/retrieve`, wired into
`main.py`, which any authenticated user may call (documented as an
admin/eval endpoint) with the ACL always taken from their own session.

**Why this shape:** the ACL filter (`allowed_access_levels(user)` from
`security.py`) is passed straight into the `WHERE access_level IN (...)`
clause of *both* search queries — never applied by filtering a Python list
afterward — so a chunk a user may not read never leaves the database, let
alone the response. RRF lives in its own tiny pure function specifically
so it can be unit-tested with plain UUIDs and no database, independent of
how the chunks were ranked.

**Proving hybrid actually helps (not just plausible):** `FakeEmbedder`'s
cosine similarity is a plain, unweighted bag-of-words score — it treats
stopwords exactly like meaningful words. I built a deliberate test case
around that: a distractor chunk packed with repeated stopwords
("What is our vacation policy? What is our travel policy?...") beats the
real answer ("Escalation policy: when to page the on-call engineer.") on
vector similarity alone (0.86 vs 0.30), because `websearch_to_tsquery`
drops stopwords and requires every remaining term to match, the keyword
search only returns the real answer at all. Fusing the two rankings pulls
the real answer back to #1. This is asserted directly in
`test_hybrid_promotes_exact_keyword_match_over_vector_only_ranking` —
both the "vector alone gets it wrong" and "hybrid fixes it" assertions
are in the same test, against a real Postgres.

**A small refactor along the way:** `build_embedder()` (real vs.
`FakeEmbedder` based on whether `EMBEDDING_API_KEY` is set) lived only in
`ingestion/worker.py`. The retrieval router needed the same choice, so it
moved to `app/embeddings/factory.py` and the worker now imports it —
one decision point instead of two copies that could drift.

**What I verified for real:** ran the full suite (61 tests: 36 unit, 25
integration) against the live `pgvector/pgvector:pg16` container at
`localhost:55432` — RRF ordering on hand-computed cases (including ties,
single-list pass-through, and ids missing from one list), vector search
returning the right chunk for a known question, `top_k` truncation, the
canary-leakage case (employee never sees a manager-only chunk, through
both the inner `retrieve()` call and the real `POST /api/retrieve` HTTP
route; a manager does), and the stopword-vs-exact-keyword hybrid case
above. `ruff`, `ruff format --check`, and `mypy --strict` are clean;
overall coverage is 87%, with every new `retrieval/` module and
`routers/retrieve.py` at 100%.

**Left unfinished (expected — later phases):** the answer/chat pipeline
(SSE streaming, prompt building, grounding checks, the answer cache) does
not exist yet — `retrieve()` is only reachable today through the debug
`/api/retrieve` endpoint, not from any chat flow. The semantic query-cache
and single-flight de-duplication from §5.10 are also not built; this
phase only covers raw retrieval.
