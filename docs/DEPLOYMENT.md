# TrustLens AI — Production Deployment Guide

This guide details the procedures for deploying TrustLens AI in containerized and cloud environments (Docker, Railway, Kubernetes).

---

## 1. Environment Configuration

Ensure the following environment variables are provisioned in your hosting environment:

| Variable | Description | Required | Default |
| :--- | :--- | :--- | :--- |
| `GEMINI_API_KEY` | Google Gemini API key for multimodal reasoning | **Yes** | — |
| `PORT` | Listening HTTP port for FastAPI server | No | `8000` |
| `DEBUG` | Enable verbose debugging logs | No | `false` |
| `RAILWAY_PUBLIC_DOMAIN` | Domain URL for Railway CORS whitelisting | No | — |
| `DATABASE_URL` | Optional PostgreSQL connection string for report persistence | No | — |
| `OPENROUTER_API_KEY` | Optional OpenRouter API key for secondary wording layer | No | — |

---

## 2. Docker Deployment

### Building the Image
```bash
docker build -t trustlens-ai:latest -f Dockerfile .
```

### Running the Container
```bash
docker run -d \
  --name trustlens-ai \
  -p 8000:8000 \
  -e GEMINI_API_KEY="your_api_key_here" \
  trustlens-ai:latest
```

---

## 3. Railway One-Click Deployment

TrustLens AI includes a preconfigured `railway.json` blueprint.
1. Connect your GitHub repository to Railway.
2. Under **Variables**, add `GEMINI_API_KEY`.
3. Railway automatically detects the multi-stage build, builds the frontend static assets, mounts them inside FastAPI, and deploys.

---

## 4. Kubernetes Manifest Example

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: trustlens-backend
  labels:
    app: trustlens
spec:
  replicas: 2
  selector:
    matchLabels:
      app: trustlens
  template:
    metadata:
      labels:
        app: trustlens
    spec:
      containers:
      - name: trustlens
        image: trustlens-ai:latest
        ports:
        - containerPort: 8000
        env:
        - name: GEMINI_API_KEY
          valueFrom:
            secretKeyRef:
              name: trustlens-secrets
              key: gemini-api-key
        resources:
          limits:
            cpu: "2"
            memory: "2Gi"
          requests:
            cpu: "500m"
            memory: "512Mi"
        livenessProbe:
          httpGet:
            path: /api/health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 15
        readinessProbe:
          httpGet:
            path: /api/health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
```

---

## 5. Health Monitoring & Verification
Verify deployment readiness via the health check endpoint:
```bash
curl -f https://<your-service-url>/api/health
```
A return payload containing `{"status": "ok"}` confirms that all routes and Gemini bindings are active.
