import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .agents import orchestrate, retrieve, research_agent, fact_check_agent, critic_agent, final_generator
from .ai_service import AIService
from .models import AnalyzeRequest, AnalyzeResponse
from .trust_engine import calculate_trust

load_dotenv()
app = FastAPI(title="TrustAgent API", version="1.0.0")
# Permit both normal local Vite addresses. Production deployments should set
# CORS_ORIGINS explicitly to their public frontend URL(s).
default_origins = "http://localhost:5173,http://127.0.0.1:5173"
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("CORS_ORIGINS", default_origins).split(",") if origin.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    ai = AIService()
    return {"status": "ok", "llm_configured": ai.available, "provider": ai.provider, "mode": "llm" if ai.available else "demo"}


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question cannot be empty.")
    ai = AIService()
    plan = orchestrate(question)
    evidence = await retrieve(question)
    initial, research, demo_mode = await research_agent(question, evidence, ai)
    checks = fact_check_agent(initial, evidence)
    critic, issues = critic_agent(initial, checks, evidence)
    score, level, status = calculate_trust(checks, evidence, issues)
    final = final_generator(initial, checks, evidence)
    return AnalyzeResponse(question=question, initial_answer=initial, research=research, fact_check=checks, critic=critic, confidence_score=score, trust_level=level, verification_status=status, detected_issues=issues, final_answer=final, evidence=evidence, agent_analysis={"orchestrator": plan, "research": research, "fact_checker": "Claims were compared against retrieved evidence.", "critic": critic, "trust_engine": f"Score {score}/100 from evidence availability, claim status, and critic flags.", "final_generator": "Final answer excludes claims that are contradicted or unsupported."}, demo_mode=demo_mode)


# Serve the compiled React app from this FastAPI process.  Keep this mount last
# so the API and Swagger routes above continue to take precedence.
frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
