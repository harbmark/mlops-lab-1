# Stage 1: builder — installs dependencies into a virtual environment.
# Kept separate from the runtime stage so build tooling (uv itself, any
# compilers pulled in transitively) never ships in the final image.
FROM python:3.10-slim AS builder

# Install uv by copying its published binary — avoids pulling pip/curl
# into this stage just to install the installer.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_HTTP_TIMEOUT=120

# Copy ONLY the dependency manifests first. Docker caches each layer by
# its inputs — as long as these files don't change, this layer (and
# the potentially slow `uv sync`) is reused on every rebuild, even if
# serve.py or train.py changes constantly. See Question 4.
# README.md is included here because pyproject.toml's `readme` field
# points to it — uv needs it present to build the local package, even
# though this stage never actually imports its contents.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ ./src/
RUN uv sync --frozen --no-dev

# Stage 2: runtime — slim image, no build tools, just the venv + source.
FROM python:3.10-slim AS runtime

WORKDIR /app

# Copy the already-built virtual environment from the builder stage.
COPY --from=builder /app/.venv /app/.venv

# Copy application source last — this is the layer that changes most
# often, so putting it last means only THIS layer gets rebuilt on a
# code change, not the dependency install above it.
COPY src/ ./src/

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "src.food11.serve:app", "--host", "0.0.0.0", "--port", "8000"]