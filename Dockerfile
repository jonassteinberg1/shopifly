FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including Chrome for Selenium
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    wget \
    gnupg \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Google Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml pytest.ini ./
COPY config/ config/
COPY scrapers/ scrapers/
COPY analysis/ analysis/
COPY storage/ storage/
COPY research/ research/
COPY scripts/ scripts/
COPY main.py .

# Create data directory for SQLite storage
RUN mkdir -p data

# Install Python dependencies (including dev dependencies for tests)
RUN pip install --no-cache-dir -e ".[dev]"

# Install dashboard dependencies
RUN pip install --no-cache-dir streamlit plotly wordcloud

# Copy dashboard
COPY dashboard/ dashboard/

# Copy tests
COPY tests/ tests/

# Copy env example for reference
COPY .env.example .env.example

# Default command
ENTRYPOINT ["python", "main.py"]
CMD ["--help"]
