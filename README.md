Workflow Decomposer + Agentic Planner (FastAPI)

Turn a natural-language process into a validated task graph and a clean flowchart, then group those tasks into reusable agents and human roles with crisp, machine‑readable assignments.

Features
- Decomposition: Converts prose into atomic tasks with dependencies and explicit inputs/outputs. Uses OpenAI when available; falls back to heuristics otherwise.
- Diagram: Mermaid graph rendered in-browser; export to JPG. No Graphviz required.
- Agentic Plan: Deduplicates similar steps into a single agent, reuses human roles for approvals, and returns strict JSON (agents, humans, assignments) for orchestration.
- Strict schemas: Pydantic models for all inputs/outputs; Responses Parse for structured LLM output with safe fallbacks.

Quickstart
1) Install
   - python -m venv .venv && . .venv/Scripts/activate  (Windows)
   - or: python -m venv .venv && source .venv/bin/activate  (macOS/Linux)
   - pip install -r requirements.txt

2) Optional: LLM support
   - Environment variables:
     - OPENAI_API_KEY=...
     - OPENAI_MODEL=gpt-5 (default)
     - OPENAI_REASONING_EFFORT=low|medium|high (default: medium)
     - OPENAI_BASE_URL=https://api.openai.com/v1 (override for Azure/proxy)
   - SDK: pip install -U "openai>=1.51.0"

3) Run
   - uvicorn app.main:app --reload --port 8000

4) Use the UI
   - Home: http://localhost:8000
     - Enter your process and optional title, then click Decompose.
     - Review the Mermaid diagram, issues, and LLM debug.
   - Agentic Workflow: http://localhost:8000/agentic
     - Reuses the last decomposed workflow (no re‑entry of the process).
     - Left pane: show the workflow diagram or all task details.
     - Right pane: generate and view Agents, Humans, and per‑task Assignments.

API
- POST /decompose
  - Body: { text: string, title?: string, granularity?: "low"|"medium"|"high" }
  - Returns: { workflow, mermaid, topo_order, issues, engine, llm_error?, llm_raw? }
  - Notes: The UI does not expose granularity; the server defaults to "medium" if omitted.

- POST /agentic_plan
  - Body: { workflow: Workflow }
  - Returns: { agents: AgentSpec[], humans: HumanSpec[], assignments: AssignedTask[], engine, llm_error?, llm_raw? }
  - Behavior: Uses structured LLM parsing when available; falls back to a heuristic grouping otherwise.

Models (high‑level)
- Task
  - id, title, actor (agent|human), depends_on[], inputs[], outputs[], tool?, parameters?, approval?, acceptance_criteria[], parallelizable
- Workflow
  - title, tasks[], edges?, assumptions[], version
- Agentic
  - AgentSpec (A#), HumanSpec (H#), AssignedTask (task_id → owner_id, instructions, inputs, outputs)

Troubleshooting
- Connection refused: ensure uvicorn is running on port 8000; check firewall/port conflicts; hard reload the browser.
- No agentic data: decompose a workflow first on the home page; the agentic page reads the latest result from local/session storage.
- OpenAI errors: set OPENAI_API_KEY; upgrade SDK to >=1.51.0; verify base URL/model; use the LLM Debug panel for details.
- Mermaid render issues: check the raw Mermaid in the UI; try https://mermaid.live for isolation.

Notes
- All rendering and export happens client‑side.
- Heuristic fallback produces a clear linear chain; LLM mode can infer richer dependencies.
