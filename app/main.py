from __future__ import annotations

import os
import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .models import DecomposeRequest, DecomposeResponse, Workflow
from .decompose import fallback_decomposition, try_llm_decomposition
from .utils import topo_sort, validate_workflow
from .mermaid import to_mermaid


# Basic logging config if not set by runner (e.g., uvicorn)
root_logger = logging.getLogger()
if not root_logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

logger = logging.getLogger("workflow")

# Log OpenAI SDK version if available
try:
    import openai as _openai_mod  # type: ignore
    ver = getattr(_openai_mod, "__version__", "unknown")
    logger.info("OpenAI SDK detected (version=%s)", ver)
except Exception:
    logger.info("OpenAI SDK not installed or not importable")

app = FastAPI(title="Workflow Decomposer", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/decompose", response_model=DecomposeResponse)
async def decompose(req: DecomposeRequest):
    logger.info("/decompose called (granularity=%s)", req.granularity)
    llm_wf, engine_mode, debug = try_llm_decomposition(req)
    wf = llm_wf or fallback_decomposition(req)
    topo, issues = topo_sort(wf.tasks)
    issues += validate_workflow(wf)
    mermaid = to_mermaid(wf)
    engine = engine_mode or "heuristic"
    llm_error = (debug or {}).get("llm_error") if debug else None
    llm_raw = (debug or {}).get("llm_raw") if debug else None
    logger.info("/decompose returning tasks=%d, issues=%d, engine=%s", len(wf.tasks), len(issues), engine)
    return DecomposeResponse(workflow=wf, mermaid=mermaid, topo_order=topo, issues=issues, engine=engine, llm_error=llm_error, llm_raw=llm_raw)


@app.get("/health")
async def health():
    return {"ok": True}


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


@app.get("/", response_class=HTMLResponse)
async def index(_: Request):
    with open(STATIC_DIR / "index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
