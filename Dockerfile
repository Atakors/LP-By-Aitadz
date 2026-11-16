FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=3000

WORKDIR /app

# Create non-root runtime user
RUN addgroup --system aitadz && adduser --system --ingroup aitadz aitadz

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py bot.py database.py didactic_rules.py docx_builder.py mcp_client.py ./

RUN chown -R aitadz:aitadz /app
USER aitadz

EXPOSE 3000

CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT:-3000} --workers 1 --threads 4 --timeout 120 --preload"]
