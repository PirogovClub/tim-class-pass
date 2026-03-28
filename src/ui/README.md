# Operator UI & Frontend Applications

The `ui/` directory houses two distinct web interfaces for the pipeline, each serving very different roles and relying on different technical stacks.

## 1. Operator UI (`ui/` root)

The **Operator UI** is the primary dashboard for executing and monitoring the data pipeline. Instead of running CLI commands manually, you can use this lightweight interface to create projects, launch pipeline steps, and watch execution logs in real-time.

### How to Run

From the repository root, start the Operator UI backend:

```powershell
uv run python -m ui
```

The app will typically start at `http://127.0.0.1:8000` (or whatever is configured in `ui/settings.py`).

### Features

- **Project Management:** Create new pipeline projects directly from local `.mp4` and `.vtt` files or a YouTube URL.
- **Run Controls:** Select specific pipeline stages (e.g., dense capture, AI vision, chunking) to execute.
- **Live Logs:** Stream pipeline execution logs directly to the browser.
- **Reconciliation:** Automatically poll and reconcile background batch jobs.

### Technical Stack (FastAPI + HTMX)

This UI is built as a server-rendered application. It does **not** use a complex Javascript framework like React. 
- **Backend:** FastAPI handles the orchestration, reads local pipeline states, and executes stages.
- **Templates:** Jinja2 builds the HTML pages.
- **Frontend Logic:** HTMX is used for partial page reloads (e.g., streaming logs and updating progress bars) without requiring a full page refresh.

---

## 2. Explorer & Adjudication UI (`ui/explorer/`)

The **Explorer UI** is the primary interface for human analysts to search the finalized knowledge graphs and adjudicate (review) the generated rule cards and extractions.

### How to Run

This relies on the `pipeline.rag.cli serve` backend. See [`ui/explorer/README.md`](explorer/README.md) for full setup instructions.

### Features

- **Semantic Search:** Browse and query generated educational concepts.
- **Adjudication:** A side-by-side review interface for discarding, merging, or accepting AI-generated outputs before they go live.

### Technical Stack (React + Vite)

Unlike the Operator UI, the Explorer is a heavy Single-Page Application (SPA):
- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS, TanStack Query.
- **Backend:** Communicates via REST JSON with the FastAPI instances mounted at `/browser/*` and `/adjudication/*`.

See [`ui/explorer/README.md`](explorer/README.md) for deep-dives into the frontend React structure and deployment.
