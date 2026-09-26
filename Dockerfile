# Backend image: the API (default command), the worker (`python -m app.worker`)
# and migrations (`alembic upgrade head`) all run from it - see
# docker-compose.yml's "app" profile.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# The CPU-only PyTorch index keeps sentence-transformers (the local embedding
# fallback) from pulling multi-GB CUDA wheels.
COPY requirements.txt .
RUN pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts

RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/uploads \
    && chown appuser /app/uploads
USER appuser

EXPOSE 8000
# --proxy-headers: behind the web container's nginx, the client IP (used for
# rate limiting) comes from X-Forwarded-For. Only safe because the API port
# is not published - nginx is the only thing that can reach it.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
