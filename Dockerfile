# Use an official Python slim image
FROM python:3.13-slim

# Copy the uv binary from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy the dependencies and definitions
COPY pyproject.toml uv.lock ./

# Install dependencies before full copy to leverage Docker caching
RUN uv sync --frozen --no-install-project --no-dev

# Copy the application source code
COPY . .

# Final sync to install the project
RUN uv sync --frozen --no-dev

# Put the virtual environment in PATH
ENV PATH="/app/.venv/bin:$PATH"

# Expose the default OAuth callback port
EXPOSE 9999

# By default, data should persist to bot_data.json in the working directory
# Consider overriding or mapping this as a bind mount during execution:
# e.g., -v ./bot_data.json:/app/bot_data.json 

# Run the websockets bot
CMD ["python", "bot_ws.py"]
