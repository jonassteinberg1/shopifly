FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml pytest.ini ./
COPY config/ config/
COPY scrapers/ scrapers/
COPY analysis/ analysis/
COPY storage/ storage/
COPY main.py .

# Create data directory for SQLite storage
RUN mkdir -p data

# Install Python dependencies (including dev dependencies for tests)
RUN pip install --no-cache-dir -e ".[dev]"

# Copy tests
COPY tests/ tests/

# Copy env example for reference
COPY .env.example .env.example

# Default command
ENTRYPOINT ["python", "main.py"]
CMD ["--help"]
