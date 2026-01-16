FROM python:3.12-slim

RUN apt-get update && apt-get -y upgrade && \
    apt-get -y install bsdmainutils mandoc && \
    rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy manj-db source so path in pyproject.toml is valid
COPY manj-db /manj-db

# Copy the application
COPY manj-mcp /app
WORKDIR /app

# Install the pre-built manj-ast-py wheel
ARG TARGETARCH
RUN case "$TARGETARCH" in \
    amd64) WHEEL_ARCH=x86_64 ;; \
    arm64) WHEEL_ARCH=aarch64 ;; \
    *) echo "Unsupported architecture: $TARGETARCH" && exit 1 ;; \
    esac && \
    uv pip install --system wheels/*${WHEEL_ARCH}.whl

# Install application dependencies (including manj-db in editable mode)
RUN uv sync --frozen --no-cache

# Run the application
CMD ["uv", "run", "server"]
