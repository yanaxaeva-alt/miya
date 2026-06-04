# ADR 0002: Vite editor skeleton before Tauri packaging

## Status

Accepted

## Context

The desktop editor goal remains a local app shell with Model Studio, Persona Studio, Graph Studio, Run Console, Trace Viewer, and Approval Queue. However, the current implementation slice needs to validate frontend/backend contracts without introducing native desktop packaging complexity too early.

Tauri is still the preferred packaging direction for a local Apple Silicon desktop app, but adding it before the React editor and FastAPI sidecar contracts stabilize would increase setup requirements and slow runtime iteration.

## Decision

Create a Vite + React + TypeScript frontend skeleton first.

The skeleton will:

- render the editor shell and core pages;
- call the local FastAPI backend for health, runtime profiles, and model list;
- keep desktop packaging out of the critical path for the runtime MVP.

Tauri integration will be added after the frontend can validate and run graphs through the backend API.

## Consequences

Positive:

- Fast frontend build checks.
- No Rust/Tauri toolchain requirement for the first UI slice.
- Backend contracts can be tested in the browser before native packaging.

Negative:

- This is not yet a packaged desktop application.
- First-run wizard and sidecar lifecycle management are deferred.

## Follow-up

Add a Tauri sidecar ADR and implementation once Graph Studio can run a mock graph and display WebSocket events.
