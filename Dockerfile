FROM python:3.11-slim

# Install build dependencies for poetry
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
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
    && poetry install --no-interaction --no-ansi --no-dev

# Copy application code
COPY app/ ./app/

# Set ownership to non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Set python path
ENV PYTHONPATH=/app

# Default command
ENTRYPOINT ["python", "-m", "app.main"]
