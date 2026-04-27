FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    # Prevent pip from complaining about running as root during build
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

# Create non-root user for running the app
RUN addgroup --system app && adduser --system --ingroup app app

COPY pyproject.toml ./
COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY app/ ./app/

RUN pip install --upgrade pip && pip install .

# Switch to non-root user
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live')" || exit 1

CMD ["sh", "-c", "python -m alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-server-header"]
