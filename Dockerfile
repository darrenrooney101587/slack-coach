FROM python:3.11-slim

# Install build dependencies for poetry and cron
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    cron \
    && rm -rf /var/lib/apt/lists/*

ENV POETRY_VERSION=1.8.0
RUN curl -sSL https://install.python-poetry.org | python - --version $POETRY_VERSION
ENV PATH="/root/.local/bin:$PATH"
RUN useradd -m -u 1000 -s /bin/bash appuser
WORKDIR /app
COPY pyproject.toml poetry.lock* /app/
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main
COPY app/ ./app/
RUN chmod +x /app/app/entrypoint.sh
RUN chmod +x /app/app/entrypoint.sh /app/app/cron-runner.sh
# Create a top-level /state directory that we will mount from the host. Keep state
# outside of /app for clarity and to match the .env you mentioned (STATE_DIR=/state).
RUN mkdir -p /state && chown -R appuser:appuser /state
RUN chown -R appuser:appuser /app
USER appuser

ENV PYTHONPATH=/app
ENV STATE_DIR=/state
ENV RUN_MODE=job
EXPOSE 8080

# Default command
ENTRYPOINT ["/app/app/entrypoint.sh"]
