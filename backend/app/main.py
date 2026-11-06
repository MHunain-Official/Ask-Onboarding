"""FastAPI application entrypoint: wires routers and middleware only.

No business logic lives here. Each router owns one resource; see
`app/routers/`.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.logging_setup import RequestIdMiddleware, configure_logging
from app.routers import admin, auth, chat, documents, health, retrieve, tickets

configure_logging()
settings = get_settings()

app = FastAPI(
    title="Ask Onboarding",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url=None,
)

app.add_middleware(RequestIdMiddleware)

# The browser only ever talks to our backend; this is for local dev where
# the Next.js dev server runs on a different port than uvicorn.
if settings.app_env != "production":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(retrieve.router)
app.include_router(chat.router)
app.include_router(tickets.router)
app.include_router(admin.router)
