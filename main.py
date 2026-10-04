import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from agent import DISCLAIMER, generate_financing_explanation, render_explanation
from ai_agent import process_agent_request
from models import FinancingRequest
from orchestrator import process_financing_request

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
app = FastAPI(title="Financing-AI-Agent", description=DISCLAIMER)
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=FileResponse, include_in_schema=False)
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health():
    return {"message": "Financing AI Agent is running", "disclaimer": DISCLAIMER}


@app.post("/evaluate")
def evaluate_financing(request: FinancingRequest):
    result = process_financing_request(request)
    fallback = False
    if result["requires_human_review"]:
        explanation = render_explanation(result)
        mode = "review_without_llm"
    else:
        explanation, fallback = generate_financing_explanation(request, result)
        mode = "deterministic_fallback" if fallback else "gemini_explanation"
    return {
        "company": request.company_name, **result,
        "ai_explanation": explanation, "workflow": "deterministic",
        "execution_mode": mode, "llm_fallback": fallback, "tool_calls": [],
    }


@app.post("/agent-evaluate")
def agent_evaluate(request: FinancingRequest):
    return process_agent_request(request)
