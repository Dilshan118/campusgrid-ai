# CampusGrid AI: Production Backend Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy build files and requirements
COPY pyproject.toml requirements.txt* ./
RUN pip install --no-cache-dir -U pip setuptools wheel
RUN pip install --no-cache-dir fastapi uvicorn pydantic pydantic-settings sqlmodel pulp numpy pandas litellm

# Copy application code
COPY src/ ./src/
COPY backend/ ./backend/
COPY README.md .env.example ./

# Install local package in editable mode
RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
