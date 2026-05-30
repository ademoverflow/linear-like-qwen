ARG PLATFORM=linux/amd64
ARG PYTHON_VERSION=3.13
ARG FULL_TAG=${PYTHON_VERSION}-slim

FROM --platform=${PLATFORM} python:${FULL_TAG} AS base

# Build arguments for user configuration
ARG USER_ID
ARG USER_GID

# Set working directory
WORKDIR /app

# Install system dependencies (curl for healthchecks, needed for Coolify)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user with configurable USER_ID/USER_GID
# Handle case where GID already exists (e.g., GID 20 is 'dialout' in Debian)
RUN groupadd -g ${USER_GID} worker 2>/dev/null || true && \
    useradd -u ${USER_ID} -g ${USER_GID} -m worker

# Install uv package manager (system-wide for non-root user access)
RUN curl -LsSf https://astral.sh/uv/0.9.22/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh

# Python environment variables
ENV PYTHONUNBUFFERED=true

# Copy workspace dependency files (for layer caching)
COPY pyproject.toml uv.lock README.md /app/

# We copy the full packages here but they will be overridden by volume mounts
COPY core /app/core

FROM base AS dev

# Install dependencies INCLUDING dev dependencies for development tools (from root)
RUN uv sync --frozen --group dev --package core --package ademoverflow-template

# Add virtual environment to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Change ownership and switch to non-root user
RUN chown -R ${USER_ID}:${USER_GID} /app
USER ${USER_ID}

# Run the application
CMD ["uv", "run", "--package", "core", "python", "-m", "core"]

# =============================================================================
# Production Stage - Minimal, self-contained image
# =============================================================================
FROM base AS prod

# Install ONLY production dependencies
RUN uv sync --frozen --no-dev --package core

# Add virtual environment to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Change ownership and switch to non-root user
RUN chown -R ${USER_ID}:${USER_GID} /app
USER ${USER_ID}

# Run the application
CMD ["uv", "run", "--package", "core", "python", "-m", "core"]
