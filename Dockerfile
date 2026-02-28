FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CLONE_DIR=/tmp/vibecheck-repos

WORKDIR /app/vibecheck

# git is required for lightweight scans that clone GitHub repositories.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p "${CLONE_DIR}"

COPY vibecheck/pyproject.toml ./pyproject.toml
COPY vibecheck/api ./api
COPY frontend /app/frontend

RUN python -m pip install --upgrade pip \
    && python -m pip install .

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
