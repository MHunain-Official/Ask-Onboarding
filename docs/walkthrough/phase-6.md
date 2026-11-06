# Phase 6 — Frontend

**What I built:** a Next.js 15 (App Router) UI with shadcn/ui (base-nova style, slate + ink theme, Source Serif 4 headings, DM Sans body). Pages: `/login` (demo users with role badges), `/chat` (history sidebar, SSE streaming, citation chips, SourceDrawer, ticket offer), `/upload` (drag-drop, per-file progress, status table that polls every 2 s while queued/processing), `/tickets`, `/admin` (stat tiles, request table + detail drawer, audit tab).

**Why it is shaped this way:**
- `src/lib/api.ts` is the only place that calls the backend. It sends `credentials: include`, and adds the CSRF header (`X-Requested-With: ask-onboarding`) to every non-GET request. A 401 sends the user to `/login?next=…`; the chat draft lives in `sessionStorage` so it survives that.
- `src/lib/sse.ts` is a small, tested parser. We use `fetch` + `ReadableStream` (not `EventSource`) because chat is a POST. The event name comes from the SSE `event:` field.
- `src/hooks/useChatStream.ts` holds all chat state. A stream that ends without `done` is saved as `partial`; Stop aborts the request; Retry and Regenerate re-ask the previous question (Regenerate sends `bypass_cache`).
- Model output is rendered with `react-markdown` (no raw HTML). `[n]` becomes a chip only if the server sent that citation. Source text is shown as plain text with one `<mark>`; a 404 shows "source updated or removed".
- Route protection is client-side (`(app)/layout.tsx` calls `/api/auth/me`); the backend still enforces auth.

**Run it:** `cd frontend && npm install && npm run dev` (open http://localhost:3000; needs the backend at `BACKEND_URL`, default `http://localhost:8000`). Checks: `npx tsc --noEmit`, `npm run lint`, `npm run test:run`, `npm run build`.

**Not finished / assumptions:**
- Backend routes not yet in the repo (`/api/chat/stream`, `/api/conversations`, `/api/tickets`, `/api/admin/*`) are coded against the playbook contracts in `src/lib/types.ts`. Field names beyond the playbook (e.g. `llm-calls` list shape, `cache_hit`/`cached_at` on the `meta` event, `bypass_cache`) are my assumptions and may need aligning.
- The backend does not check the CSRF header yet; the client already sends it.
- Not run: Playwright smoke test, thumbs up/down, and a visual check in a real browser against a live backend. Contrast was chosen for WCAG AA but not measured with a tool.
- `shadcn init` generated `import { cn } from "cn"` (an unrelated npm package). I changed it to `@/lib/utils` and wrote `cn` with `clsx` + `tailwind-merge`.
