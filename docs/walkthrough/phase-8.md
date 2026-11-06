# Phase 8 — Evaluation Harness

Built a deterministic eval harness in `backend/eval/run_eval.py` so the owner can measure retrieval without API keys.
The question set in `backend/eval/questions.json` covers factual, multi-chunk, unanswerable, access-control and injection cases.
The default eval indexes `sample-data/docs` in memory with the production chunker and `FakeEmbedder`, then compares chunk size and hybrid search settings.
The harness writes `backend/eval/report.md` and `docs/eval.md` with measured numbers only; live LLM judging is left opt-in behind `--llm real`.
Current fake run showed hybrid search improving 300/60 retrieval from 95.0% to 100.0% hit-rate@5, with no canary or injection leaks.

**Left unfinished (needs real keys):** live OpenRouter answer-quality judging, model cost/latency comparison, and LLM-as-judge scoring.
