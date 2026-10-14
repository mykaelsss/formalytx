# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.11.19-python3.14-trixie-slim

# Setup a non-root user
RUN groupadd --system --gid 999 nonroot \
 && useradd --system --gid 999 --uid 999 --create-home nonroot

# gosu lets the entrypoint drop from root to nonroot after fixing mount ownership
RUN apt-get update \
 && apt-get install -y --no-install-recommends gosu \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering.
ENV PYTHONUNBUFFERED=1

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Omit development dependencies
ENV UV_NO_DEV=1

# Ensure installed tools can be executed out of the box
ENV UV_TOOL_BIN_DIR=/usr/local/bin

# Install the project's dependencies using the lockfile and settings.
# Copying only the lockfile + manifest first keeps this layer cached unless
# they change. No uv cache mount: Railway ties a cache mount's id to a single
# service, and the API and the scheduled export build from this same file.
# --no-cache keeps uv's download cache out of the image.
COPY uv.lock pyproject.toml ./
RUN uv sync --locked --no-install-project --no-cache

# Then, add the rest of the project source code and install it
# Installing separately from its dependencies allows optimal layer caching
COPY . /app
RUN uv sync --locked --no-cache

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

RUN mkdir -p /home/nonroot/.fastf1 \
   && chown -R nonroot:nonroot /home/nonroot/.fastf1

# Entrypoint runs as root only long enough to chown the mounted cache disk,
# then execs the server as nonroot via gosu (see docker-entrypoint.sh).
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

CMD ["sh", "-c", "exec fastapi run --host 0.0.0.0 --port ${PORT:-8000} app/main.py"]
