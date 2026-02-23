FROM python:3.11-slim

WORKDIR /app

# Copy requirements
COPY requirements/ requirements/

# Install trading web dependencies
RUN pip install --no-cache-dir flask flask-cors && \
    pip install --no-cache-dir -r requirements/base.txt 2>/dev/null || \
    pip install --no-cache-dir flask flask-cors requests

# Copy project
COPY . .

# Create logs dir
RUN mkdir -p /app/logs

EXPOSE 5001

ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production

CMD ["python", "web/trading_web.py"]
