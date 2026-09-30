# Stage 1: Build dependencies and virtual environment
FROM python:3.13-slim-bookworm AS builder

# Copy the lightning-fast uv binary from Astral's official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /code

# Install OS-level build tools required for 'cryptography' and PostgreSQL wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Enable bytecode compilation and optimize uv linking
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Copy dependency specifications first to maximize Docker caching
COPY pyproject.toml uv.lock ./

# Install dependencies using uv into a virtual environment (.venv)
RUN uv sync --frozen --no-install-project --no-dev


# Stage 2: Final lightweight runtime
FROM python:3.13-slim-bookworm AS runner

WORKDIR /code

# Copy the isolated virtual environment from the builder stage
COPY --from=builder /code/.venv /code/.venv

# Install ONLY runtime Postgres dependencies (much smaller than dev dependencies)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy application source code (relies on your .dockerignore)
COPY . .

# Place the virtual environment's python/bin in the PATH
ENV PATH="/code/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# Execute directly using the venv's fastapi binary (skips uv overhead at runtime)
CMD ["fastapi", "dev", "main.py", "--host", "0.0.0.0", "--port", "8000"]














































# FROM python:3.13-slim   

# WORKDIR /code

# # Install uv
# COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# # Install system dependencies
# RUN apt-get update && apt-get install -y \
#     build-essential \
#     libpq-dev \
#     && rm -rf /var/lib/apt/lists/*

# # Copy dependency files
# COPY pyproject.toml uv.lock ./

# # Install dependencies into the default location
# RUN uv sync --frozen --no-install-project --no-dev

# # Copy the rest of the code (The .dockerignore will skip your local .venv)
# COPY . .

# # Match your intended port
# EXPOSE 8000

# # Use uv run to execute the app
# CMD ["uv", "run", "fastapi", "dev", "main.py", "--host", "0.0.0.0", "--port", "8000"]