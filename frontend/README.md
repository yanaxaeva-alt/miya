# MiaOS Builder frontend

Vite + React + TypeScript editor skeleton for the local MiaOS Builder backend.

## Run

```bash
npm install
npm run dev
```

The frontend expects the FastAPI backend at `http://127.0.0.1:8765` by default.
Override with:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8765 npm run dev
```

## Pages

- Model Studio
- Persona Studio
- Graph Studio
- Run Console
- Trace Viewer
- Approval Queue

## Checks

```bash
npm run build
```
