# CampusGrid AI: Backend Container
FROM python:3.11-slim

WORKDIR /app

# Build toolchain needed by psycopg2-binary / scientific wheels on slim images
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the single source of dependency truth first so this layer caches.
COPY pyproject.toml README.md ./

# Application code
COPY src/ ./src/
COPY backend/ ./backend/
COPY .env.example ./

# Install from pyproject rather than a hardcoded package list, so the image
# can never drift from the manifest. Swap the extras to suit the deployment:
#   ".[postgres]"            - API against Neon, mock embeddings
#   ".[postgres,rag]"        - adds real sentence-transformers embeddings (large)
#   ".[all]"                 - everything, including ML and dev tooling
RUN pip install --no-cache-dir -U pip setuptools wheel \
    && pip install --no-cache-dir -e ".[postgres]"

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
