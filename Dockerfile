FROM python:3.12-slim

RUN apt-get update && \
    rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy manj-db and manj-collector source so path in pyproject.toml is valid
COPY manj-db /manj-db

# Copy the application
COPY manj-mcp /app
WORKDIR /app

# Install application dependencies (including manj-db in editable mode)
RUN uv sync --frozen --no-cache

# Run the application
CMD ["uv", "run", "server"]
