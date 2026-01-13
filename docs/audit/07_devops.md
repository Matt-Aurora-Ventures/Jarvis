# DevOps & Infrastructure Improvements (81-90)

## 81. Docker Optimization

```dockerfile
# Dockerfile.optimized
FROM python:3.11-slim as builder
WORKDIR /app
RUN pip install --no-cache-dir pip-tools
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels
COPY . .
RUN useradd -m jarvis && chown -R jarvis:jarvis /app
USER jarvis
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s CMD curl -f http://localhost:8000/api/health || exit 1
CMD ["uvicorn", "api.fastapi_app:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile.optimized
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
    restart: unless-stopped
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```

## 82. Kubernetes Manifests

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: jarvis-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: jarvis-api
  template:
    metadata:
      labels:
        app: jarvis-api
    spec:
      containers:
      - name: api
        image: jarvis-api:latest
        ports:
        - containerPort: 8000
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /api/health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /api/health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
        envFrom:
        - secretRef:
            name: jarvis-secrets
---
apiVersion: v1
kind: Service
metadata:
  name: jarvis-api
spec:
  selector:
    app: jarvis-api
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

## 83. CI/CD Pipeline

```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: pytest --cov=core

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v5
        with:
          push: true
          tags: ghcr.io/${{ github.repository }}:${{ github.sha }}

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v4
      - run: |
          kubectl set image deployment/jarvis-api api=ghcr.io/${{ github.repository }}:${{ github.sha }}
```

## 84. Secrets Management

```python
# core/secrets/manager.py
import os
from typing import Optional
import boto3
from functools import lru_cache

class SecretsManager:
    def __init__(self):
        self.provider = os.getenv("SECRETS_PROVIDER", "env")
        if self.provider == "aws":
            self.client = boto3.client('secretsmanager')
    
    @lru_cache(maxsize=100)
    def get_secret(self, name: str) -> Optional[str]:
        if self.provider == "env":
            return os.getenv(name)
        elif self.provider == "aws":
            try:
                response = self.client.get_secret_value(SecretId=name)
                return response['SecretString']
            except Exception:
                return None
        return None
    
    def rotate_secret(self, name: str, new_value: str):
        if self.provider == "aws":
            self.client.put_secret_value(SecretId=name, SecretString=new_value)
        self.get_secret.cache_clear()

secrets = SecretsManager()
```

## 85. Blue-Green Deployment

```yaml
# k8s/blue-green.yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: jarvis-api
spec:
  replicas: 3
  strategy:
    blueGreen:
      activeService: jarvis-api-active
      previewService: jarvis-api-preview
      autoPromotionEnabled: false
      scaleDownDelaySeconds: 30
  selector:
    matchLabels:
      app: jarvis-api
  template:
    metadata:
      labels:
        app: jarvis-api
    spec:
      containers:
      - name: api
        image: jarvis-api:latest
        ports:
        - containerPort: 8000
```

## 86. Auto-Scaling

```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: jarvis-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: jarvis-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Pods
        value: 2
        periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
```

## 87. Backup Automation

```python
# scripts/backup.py
import subprocess
from datetime import datetime
from pathlib import Path
import boto3
import os

class BackupManager:
    def __init__(self):
        self.backup_dir = Path("backups")
        self.backup_dir.mkdir(exist_ok=True)
        self.s3 = boto3.client('s3') if os.getenv("AWS_ACCESS_KEY_ID") else None
    
    def backup_database(self) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"db_backup_{timestamp}.sql"
        
        # SQLite backup
        subprocess.run([
            "sqlite3", "data/jarvis.db",
            f".backup '{backup_file}'"
        ], check=True)
        
        return backup_file
    
    def backup_configs(self) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"config_backup_{timestamp}.tar.gz"
        
        subprocess.run([
            "tar", "-czf", str(backup_file),
            "lifeos.config.json", "lifeos.config.local.json"
        ], check=True)
        
        return backup_file
    
    def upload_to_s3(self, file_path: Path, bucket: str):
        if self.s3:
            key = f"backups/{file_path.name}"
            self.s3.upload_file(str(file_path), bucket, key)
    
    def cleanup_old_backups(self, days: int = 30):
        import time
        cutoff = time.time() - (days * 86400)
        for f in self.backup_dir.glob("*"):
            if f.stat().st_mtime < cutoff:
                f.unlink()

if __name__ == "__main__":
    manager = BackupManager()
    db_backup = manager.backup_database()
    config_backup = manager.backup_configs()
    manager.upload_to_s3(db_backup, "jarvis-backups")
    manager.cleanup_old_backups()
```

## 88. Monitoring Dashboards

```yaml
# monitoring/grafana-dashboard.json
{
  "dashboard": {
    "title": "Jarvis Overview",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [{"expr": "rate(http_requests_total[5m])"}]
      },
      {
        "title": "Error Rate",
        "type": "graph",
        "targets": [{"expr": "rate(http_requests_total{status=~'5..'}[5m])"}]
      },
      {
        "title": "Response Time P95",
        "type": "graph",
        "targets": [{"expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))"}]
      },
      {
        "title": "Active WebSocket Connections",
        "type": "stat",
        "targets": [{"expr": "websocket_connections_active"}]
      }
    ]
  }
}
```

```yaml
# monitoring/prometheus-rules.yml
groups:
- name: jarvis-alerts
  rules:
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: High error rate detected
  - alert: HighLatency
    expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
    for: 5m
    labels:
      severity: warning
```

## 89. Log Rotation

```python
# core/logging/rotation.py
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path

def setup_log_rotation(log_dir: Path = Path("logs")):
    log_dir.mkdir(exist_ok=True)
    
    # Size-based rotation (10MB, keep 5 backups)
    size_handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5
    )
    
    # Time-based rotation (daily, keep 30 days)
    time_handler = TimedRotatingFileHandler(
        log_dir / "app-daily.log",
        when="midnight",
        interval=1,
        backupCount=30
    )
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    size_handler.setFormatter(formatter)
    time_handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.addHandler(size_handler)
    root_logger.addHandler(time_handler)
```

## 90. Disaster Recovery Plan

```python
# scripts/disaster_recovery.py
import subprocess
import os
from pathlib import Path
from datetime import datetime

class DisasterRecovery:
    def __init__(self):
        self.backup_bucket = os.getenv("BACKUP_BUCKET")
        self.recovery_dir = Path("recovery")
    
    def restore_from_backup(self, backup_date: str):
        self.recovery_dir.mkdir(exist_ok=True)
        
        # Download backup
        subprocess.run([
            "aws", "s3", "cp",
            f"s3://{self.backup_bucket}/backups/db_backup_{backup_date}.sql",
            str(self.recovery_dir / "db_backup.sql")
        ], check=True)
        
        # Stop services
        subprocess.run(["docker-compose", "stop", "api"], check=True)
        
        # Restore database
        subprocess.run([
            "sqlite3", "data/jarvis.db",
            f".restore '{self.recovery_dir / 'db_backup.sql'}'"
        ], check=True)
        
        # Restart services
        subprocess.run(["docker-compose", "up", "-d", "api"], check=True)
    
    def failover_to_secondary(self):
        # Update DNS to point to secondary region
        pass
    
    def health_check_all_services(self) -> dict:
        services = ["api", "redis", "nginx"]
        status = {}
        for service in services:
            result = subprocess.run(
                ["docker-compose", "ps", "-q", service],
                capture_output=True
            )
            status[service] = bool(result.stdout.strip())
        return status
```
