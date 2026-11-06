# ADR 004: Hybrid search (vector + full-text) fused with Reciprocal Rank Fusion

**Status:** accepted

**Context.** Pure vector search is weak on exact terms (commands, port numbers, product names); pure keyword search is weak on paraphrases.

**Decision.** Run vector search (top 20) and full-text search (`websearch_to_tsquery` + `ts_rank_cd`, top 20), both with the same access filter, then fuse the ranks with RRF: `score = Σ 1 / (60 + rank)`. Toggle with `HYBRID_ENABLED` (default `true`). The no-answer gate still uses the best **vector** similarity.

**Evidence.** From `docs/eval.md` (20 questions, **FakeEmbedder**, so indicative only):

| Chunk/overlap | Hybrid | Hit-rate@5 | MRR |
|---|---|---:|---:|
| 300/60 | off | 95.0% | 0.742 |
| 300/60 | on | 100.0% | 0.892 |
| 500/80 | off | 100.0% | 0.760 |
| 500/80 | on | 100.0% | 0.892 |

Hybrid raised MRR by 0.132 at 500/80. A Phase 3 test also shows the mechanism: a stopword-stuffed distractor outranks the real answer on vectors alone, and keyword search plus RRF restores it.

**Consequences.**
- English-only stemming (`to_tsvector('english', ...)`).
- RRF has no tunable weights; simple and explainable, but not optimal.
- The gain should be re-measured with real OpenAI embeddings, which handle stopwords better than the fake embedder; the gap may be smaller.
