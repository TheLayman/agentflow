Workflow Decomposer (Python + FastAPI)

Goal: Turn a natural-language description of a business process into a set of granular tasks, a dependency DAG, and a rendered flowchart you can download as a JPG.

Features
- FastAPI backend with JSON schema for workflows
- Decomposition engine:
  - Optional: Uses OpenAI if `OPENAI_API_KEY` is set
  - Fallback: Simple heuristics that produce a linear DAG from sentences
- Mermaid flowchart generation and in-browser rendering
- Download the diagram as JPG (client-side SVG->canvas conversion)

Quickstart
1) Install deps
   - python -m venv .venv && source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
   - pip install -r requirements.txt

2) (Optional) Enable OpenAI (with reasoning)
   - Set env vars:
     - `OPENAI_API_KEY=...`
     - `OPENAI_MODEL=gpt-5` (default). Uses the Responses API via HTTPS directly; if unavailable, falls back to Chat Completions HTTPS.
     - `OPENAI_REASONING_EFFORT=low|medium|high` (default: `medium`) — used for reasoning-capable models via the Responses API.
     - Optional: `OPENAI_BASE_URL` for custom endpoints/Azure (default `https://api.openai.com/v1`).
     - Optional: `OPENAI_FALLBACK_MODEL=gpt-4o-mini` — used when falling back to Chat Completions.

Upgrade SDK (to enable responses.parse)
- Ensure you have a recent OpenAI Python SDK:
  - `pip install -U "openai>=1.51.0"`
  - Or reinstall dependencies: `pip install -U -r requirements.txt`
  - The app logs the detected OpenAI SDK version at startup.

3) Run the server
   - uvicorn app.main:app --reload --port 8000

4) Open the UI
   - Visit http://localhost:8000
   - Enter your process, choose granularity, click Decompose
   - Click "Download JPG" to save the diagram

API
- POST /decompose
  - Body: { text: string, title?: string, granularity?: "low"|"medium"|"high", constraints?: object }
  - Returns: { workflow, mermaid, topo_order, issues }

Notes
- Mermaid rendering and JPG export happen in the browser; no Graphviz install required.
- The fallback decomposition creates a simple linear chain for clarity; with `OPENAI_API_KEY` it produces richer, dependency-aware graphs. If `OPENAI_MODEL` is a reasoning-capable family (e.g., `gpt-5`, `o4`, `o3`), the backend uses the Responses API with a reasoning effort setting.
  - If the SDK/server does not support the Responses API, it automatically switches to Chat Completions and logs the switch.
- Robustness measures:
  - Responses API uses `response_format: json_schema` with a strict JSON Schema for the workflow.
  - Chat Completions path uses `response_format: json_object`, includes few-shot examples, and caps `max_tokens`.
  - Backend cleans and validates LLM output (dedup deps, remove self-deps, check duplicates/empties) and reports issues.
- This is an MVP; you can extend with editing, roles, tools, and smarter dependency inference.
Testing
- Programmatic tests (uses in-process FastAPI TestClient):
  - With your venv active, run: `python scripts/test_llm.py`
  - If `OPENAI_API_KEY` is set, tests will use the LLM (Responses or Completions). Otherwise they run in heuristic mode.
  - The script prints the engine used, number of tasks, issues, and a preview of tasks for each case.
