# TrustLens AI — API Reference

Comprehensive specification of the TrustLens AI REST API endpoints, request/response models, and error statuses.

---

## Base URL
- **Local Development**: `http://localhost:8000/api`
- **Production**: `https://<your-domain>/api`

---

## Authentication & Headers
All requests should include standard HTTP headers:
```http
Accept: application/json
X-Request-ID: <optional-uuid>
```

---

## Endpoints

### 1. Health & Status
#### `GET /api/health`
Returns the operational status of the service, Gemini API connectivity, and database availability.

**Response `200 OK`**:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "gemini_configured": true,
  "database_connected": true
}
```

---

### 2. Multi-Modal Analysis
#### `POST /api/analyze`
Submits media (image, video, audio) or claim text for AI verification and forensics analysis.

**Request (`multipart/form-data`)**:
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `mode` | `string` | **Yes** | Analysis mode: `"news_claim"` or `"ai_generated"` |
| `file` | `file` | Optional | Uploaded media file (`.jpg`, `.png`, `.mp4`, `.mp3`, `.wav`) |
| `text` | `string` | Optional | Raw claim text or article context |
| `source_url` | `string` | Optional | URL to fetch context from |

**Response `200 OK`**:
```json
{
  "request_id": "a93bf81d-e06b-4e1b-9f37-67de5ba49271",
  "mode": "news_claim",
  "timestamp": "2028-10-01T11:12:00Z",
  "overall_verdict": "MISLEADING",
  "trust_score": 38,
  "confidence": 0.89,
  "evidence": [
    {
      "claim": "Claim extracted from input context",
      "status": "DEBUNKED",
      "sources": [
        {
          "title": "Fact Check Verification",
          "url": "https://example.org/fact-check",
          "credibility_tier": "HIGH"
        }
      ]
    }
  ],
  "forensic_details": {
    "metadata_tampering": false,
    "ai_generated_indicators": []
  }
}
```

**Status Codes**:
- `200 OK`: Analysis successfully executed.
- `400 Bad Request`: Missing mandatory parameters or unsupported file format.
- `413 Payload Too Large`: Uploaded file exceeds file size threshold (100MB).
- `503 Service Unavailable`: Upstream Gemini model unreachable.

---

### 3. Preloaded Demos
#### `GET /api/demos`
Fetches a list of curated demo cases (deepfakes, manipulated articles, authentic news) for frontend previewing.

**Response `200 OK`**:
```json
{
  "demos": [
    {
      "id": "demo-deepfake-01",
      "title": "Synthesized Audio Voice Clone",
      "mode": "ai_generated",
      "media_type": "audio",
      "sample_url": "/static/samples/voice_clone.wav"
    }
  ]
}
```

---

### 4. PDF Trust Report Generation
#### `POST /api/report/pdf`
Generates an exportable PDF Trust Report summarizing evidence, timeline, and forensic findings.

**Request (`application/json`)**:
```json
{
  "analysis_id": "a93bf81d-e06b-4e1b-9f37-67de5ba49271",
  "include_forensic_timeline": true
}
```

**Response `200 OK`**:
- `Content-Type`: `application/pdf`
- `Content-Disposition`: `attachment; filename="TrustLens-Report-a93bf81d.pdf"`

---

## Error Handling
Standard error structure returned on `4xx` and `5xx` responses:
```json
{
  "error": {
    "code": "INVALID_INPUT",
    "message": "The provided media format is not supported.",
    "request_id": "a93bf81d-e06b-4e1b-9f37-67de5ba49271"
  }
}
```
