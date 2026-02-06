FROM python:3.11-slim

# Install build dependencies for poetry and cron
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
ENV POETRY_VERSION=1.8.0
RUN curl -sSL https://install.python-poetry.org | python - --version $POETRY_VERSION
ENV PATH="/root/.local/bin:$PATH"

# Create a non-root user
RUN useradd -m -r -s /bin/bash appuser

WORKDIR /app

# Copy poetry files and install
COPY pyproject.toml poetry.lock* /app/
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main

# Copy application code
COPY app/ ./app/

# Make entrypoint executable
RUN chmod +x /app/app/entrypoint.sh

# Create state dir inside app and give ownership
RUN mkdir -p /app/state && chown -R appuser:appuser /app/state

# Set ownership to non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Set python path
ENV PYTHONPATH=/app
# Default state dir inside container
ENV STATE_DIR=/app/state
# Default run mode: job (use "server" to run the Flask receiver)
ENV RUN_MODE=job
# Expose port for server mode
EXPOSE 8080

# Default command
ENTRYPOINT ["/app/app/entrypoint.sh"]
