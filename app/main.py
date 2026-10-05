"""Users + auth + todos API.

Run:  uvicorn app.main:app --reload   (needs Postgres: docker compose up -d)
Docs: http://127.0.0.1:8000/docs  (Swagger UI, auto-generated)
Demo: http://127.0.0.1:8000/app   (plain HTML/JS frontend)
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import assistant, auth, todos, users
from app.core.config import settings
from app.db.session import Base, engine, ensure_columns
from app.models import todo as _todo_model, user as _user_model  # noqa: F401  (registers tables on Base)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

# Strict CSP for the frontend: only our own files, no inline scripts, can't be framed.
FRONTEND_CSP = "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once at startup. Creates missing tables; for schema changes use Alembic migrations.
    Base.metadata.create_all(engine)
    ensure_columns()
    yield


app = FastAPI(title="Todo API", description="FastAPI basics demo", version="0.3.0", lifespan=lifespan)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.path.startswith("/app"):
        response.headers["Content-Security-Policy"] = FRONTEND_CSP  # /docs loads a CDN, so not applied there
    if request.url.path.startswith(("/auth", "/users", "/todos", "/assistant")):
        response.headers["Cache-Control"] = "no-store"  # tokens and personal data must not be cached
    return response


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(todos.router)
app.include_router(assistant.router)

if FRONTEND_DIR.is_dir():
    app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse("/app/")
