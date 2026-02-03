FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5678

CMD ["gunicorn", "-b", "0.0.0.0:5678", "lead_qualifier_full:app"]
