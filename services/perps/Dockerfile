FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY services/perps/requirements.txt /tmp/requirements-perps.txt
RUN pip install --no-cache-dir -r /tmp/requirements-perps.txt

COPY web /app/web
COPY core /app/core

# Cloud Run provides PORT at runtime.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 8 \"web.run_perps_api:create_app()\""]
