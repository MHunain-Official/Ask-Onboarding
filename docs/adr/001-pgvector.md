# ADR 001: pgvector in PostgreSQL instead of a dedicated vector store

**Status:** accepted

**Context.** We need vector search, keyword search, access control, an answer cache, tickets and an audit log. Options: Qdrant/Pinecone/Weaviate next to a relational DB, or pgvector inside Postgres.

**Decision.** Use PostgreSQL 16 with pgvector (`pgvector/pgvector:pg16`): `vector(1536)` column, HNSW index with cosine ops, GIN index on a generated `tsvector` column.

**Why.**
- One database for everything: the chunk swap on re-upload, cache invalidation and ACL filtering are single transactions or single `WHERE` clauses. With two stores they would be two systems that can disagree.
- The access filter can sit in the same SQL as the similarity search.
- One thing to back up and run on a single VPS.

**Consequences.**
- Good to roughly low millions of chunks on one node; at ~2M chunks × 1536 dims the raw vectors are ~12 GB plus index. See ARCHITECTURE.md §3 for what we would do first (halfvec/quantisation, read replica) before leaving Postgres.
- The embedding dimension is baked into the column. Changing the embedding model means a migration and a full re-embed, and there is currently no startup check for a mismatch.
- Similarity is `1 - (embedding <=> query)`: `<=>` is a distance, a mistake the playbook warns about.
