# Todo API + frontend + chat assistant, in one image.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /code

# Dependencies first: this layer is cached until requirements.txt changes
COPY requirements.txt .
RUN pip install -r requirements.txt

# Only what the app needs at runtime (no tests, no .env: secrets are injected at run time, never baked in)
COPY app ./app
COPY frontend ./frontend
COPY mcp_server ./mcp_server

# Don't run as root
RUN useradd --system --uid 10001 --no-create-home appuser
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/app/', timeout=3)" || exit 1

# One worker on purpose: the login throttle and assistant limiter live in memory (see README)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
