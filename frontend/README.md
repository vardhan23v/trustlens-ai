# TrustLens AI — frontend

React 19 + Vite 8 + TypeScript + Tailwind CSS 4. Single page, no router.

```bash
npm install
npm run dev      # http://localhost:5173, proxies /api to http://localhost:8000
npm run build    # type-check and production build into dist/
npm run lint     # oxlint
```

`src/types/report.ts` mirrors the backend's `TrustReport` schema. See the repository [README](../README.md).
