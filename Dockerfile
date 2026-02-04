FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY lead_qualifier_full.py .

# Koyeb sets PORT env variable, default to 8000
ENV PORT=8000
EXPOSE 8000

# Run gunicorn with proper settings for Koyeb
CMD ["gunicorn", "-b", "0.0.0.0:8000", "--timeout", "120", "--workers", "2", "--threads", "2", "lead_qualifier_full:app"]
