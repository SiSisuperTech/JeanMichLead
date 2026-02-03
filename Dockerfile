FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI (for compatibility)
# RUN curl -fsSL https://claude.ai/install.sh | sh

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY lead_qualifier_full.py .

# Expose port
EXPOSE 5678

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5678/health || exit 1

# Run the app
CMD ["gunicorn", "lead_qualifier_full:app", "--bind", "0.0.0.0:$PORT", "--workers", "1", "--timeout", "120"]
