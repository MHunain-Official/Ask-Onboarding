# ADR 007: OpenRouter for answers, OpenAI directly for embeddings

**Status:** accepted

**Context.** We want to compare and swap answer models and survive a provider outage, but embeddings must stay stable: changing the embedding model invalidates every stored vector.

**Decision.**
- **Answers:** OpenRouter (OpenAI-compatible) through the `openai` SDK, behind an `LlmClient` interface. `LLM_MODEL` is the primary and `LLM_FALLBACK_MODEL` the fallback, both from env. On timeout, 5xx or 429 after bounded retries the fallback is tried once; content refusals never trigger a silent fallback. A circuit breaker fails fast after repeated failures.
- **Embeddings:** OpenAI `text-embedding-3-small` (1536 dims) called directly, behind an `Embedder` interface, with its own base URL, key and model in env. Never routed through a gateway.
- Tests use `FakeLlm` and `FakeEmbedder`; no API keys needed.

**Consequences.**
- **Data leaves the network** to OpenRouter (and its upstream providers) and OpenAI. See SECURITY.md for the retention note.
- Two keys, two bills.
- Models must support streaming and tool calling; this is **not verified** for any specific model here. The defaults in `.env.example` (`openai/gpt-4o-mini` for both) are placeholders, not a result of comparison.
- If either key is empty the app silently uses fake clients (a local-dev convenience that is a risk in production).
- Prices come from env (`LLM_PRICE_*`) for cost estimates; if usage is missing the code estimates tokens and flags `usage_estimated`.
