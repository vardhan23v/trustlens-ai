# Contributing to TrustLens AI

Thank you for your interest in contributing to TrustLens AI! This document outlines guidelines for submitting bug reports, feature requests, and code contributions.

---

## Development Workflow

### 1. Prerequisites
- **Python**: 3.10+
- **Node.js**: 18+
- **pnpm / npm**
- **FFmpeg**: (required for local media container inspection)

### 2. Backend Setup
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Run tests to verify setup:
```bash
pytest
```

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run build
npm test # or npm run lint
```

---

## Git Commit Guidelines
We follow conventional commit standards:
- `feat:` New features or analysis capabilities
- `fix:` Bug fixes or correction in logic
- `docs:` Documentation updates or API specifications
- `test:` Unit, integration, or evaluation tests
- `refactor:` Code improvements without behavioral changes
- `chore:` Tooling, dependency, or configuration tweaks

---

## Code Quality Standards
- **Python**: PEP 8 compliance, clear type annotations, and unit tests for new services.
- **Frontend**: Strict TypeScript types, accessible DOM structure (`aria-` attributes), responsive Tailwind styling.
- **Security**: Prevent SSRF on external endpoints; never log private API keys or unredacted user payloads.
