import asyncio
import logging
import os
from time import monotonic
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.gzip import GZipMiddleware
from .agents import orchestrate, retrieve, research_agent, fact_check_agent, critic_agent, final_generator
from .ai_service import AIService
from .models import AnalyzeRequest, AnalyzeResponse
from .trust_engine import calculate_trust

load_dotenv()
app = FastAPI(title="TrustAgent API", version="1.0.0")
logger = logging.getLogger(__name__)
started_at = monotonic()
in_flight_analyses: dict[str, asyncio.Task[AnalyzeResponse]] = {}


class CacheControlledStaticFiles(StaticFiles):
    """Cache Vite bundles, while serving the SPA shell for client-side routes."""

    async def get_response(self, path: str, scope: dict):
        # StaticFiles only resolves real files. Routes such as /evidence need to
        # return the React shell so the browser can render them client-side. Do
        # not turn missing API or asset URLs into a misleading HTML 200 response.
        is_client_route = (
            bool(path)
            and not path.startswith(("api/", "assets/"))
            and not Path(path).suffix
        )
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as error:
            if error.status_code != 404 or not is_client_route:
                raise
            response = await super().get_response("index.html", scope)
        if response.status_code == 200:
            if path.startswith("assets/"):
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            elif path in {"", "index.html"} or is_client_route:
                response.headers["Cache-Control"] = "no-cache"
        return response


app.add_middleware(GZipMiddleware, minimum_size=500)
# Permit both normal local Vite addresses. Production deployments should set
# CORS_ORIGINS explicitly to their public frontend URL(s).
default_origins = "http://localhost:5173,http://127.0.0.1:5173"
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("CORS_ORIGINS", default_origins).split(",") if origin.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def cache_static_response(request, call_next):
    """Keep cache policy intact when compression middleware wraps a file response."""
    response = await call_next(request)
    if request.url.path.startswith("/assets/") and response.status_code == 200:
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


FAVICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40">'
    '<defs>'
    '<linearGradient id="tg" x1="6" y1="4" x2="34" y2="36" gradientUnits="userSpaceOnUse">'
    '<stop stop-color="#7dd3fc"/>'
    '<stop offset="1" stop-color="#2563eb"/>'
    '</linearGradient>'
    '</defs>'
    '<path d="M20 3.5 34 9v9.2c0 8.7-5.5 15.5-14 18.3C11.5 33.7 6 26.9 6 18.2V9l14-5.5Z" fill="url(#tg)"/>'
    '<path d="m13.5 19.8 4.1 4.2 9-9.2" fill="none" stroke="white" stroke-linecap="round" stroke-linejoin="round" stroke-width="3.2"/>'
    '</svg>'
)


@app.get("/favicon.ico", include_in_schema=False)
@app.get("/favicon.svg", include_in_schema=False)
async def favicon():
    return Response(content=FAVICON_SVG, media_type="image/svg+xml")


@app.get("/api/health")
async def health():
    ai = AIService()
    return {
        "status": "ok",
        "api_status": "operational",
        "uptime_seconds": int(monotonic() - started_at),
        "frontend_available": frontend_dist.is_dir(),
        "database_configured": False,
        "llm_configured": ai.available,
        "provider": ai.provider,
        "mode": "llm" if ai.available else "demo",
    }


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question cannot be empty.")
    # A browser retry or two users submitting the same question simultaneously
    # should not trigger duplicate provider and retrieval requests. Results are
    # only shared while the work is in progress; no questions are persisted.
    cache_key = question.casefold()
    task = in_flight_analyses.get(cache_key)
    if task is None:
        task = asyncio.create_task(_analyze_question(question))
        in_flight_analyses[cache_key] = task
        task.add_done_callback(lambda _: in_flight_analyses.pop(cache_key, None))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        raise
    except Exception as error:
        logger.exception("Analysis failed")
        raise HTTPException(status_code=500, detail="Analysis could not be completed. Please try again.") from error


async def _analyze_question(question: str) -> AnalyzeResponse:
    ai = AIService()
    plan = orchestrate(question)
    service_warnings: list[str] = []

    # Gemini Search grounding returns an answer and its web sources in one
    # provider request. This is faster and more reliable than separately
    # querying Wikipedia and then asking an ungrounded model to answer.
    if ai.provider == "gemini" and ai.available:
        try:
            grounded = await ai.grounded_answer(question)
            initial, evidence, demo_mode = grounded.answer, grounded.evidence, False
            if evidence:
                research = f"Gemini Google Search grounding returned {len(evidence)} source(s) for review."
            else:
                # A model can elect not to search. It must not be labelled as
                # verified unless the fallback source can corroborate it.
                evidence = await retrieve(question)
                research = (
                    "Gemini responded without citations; fallback public retrieval returned "
                    f"{len(evidence)} source(s)."
                )
                if not evidence:
                    service_warnings.append(
                        "The LLM responded without verifiable web citations, so this result is unverified."
                    )
        except RuntimeError as error:
            service_warnings.append(str(error))
            evidence = await retrieve(question)
            # Do not repeat a failed provider call. The deterministic fallback
            # keeps the response useful and bounded in latency.
            initial, research, demo_mode = await research_agent(question, evidence, ai, use_ai=False)
    else:
        evidence = await retrieve(question)
        initial, research, demo_mode = await research_agent(question, evidence, ai)

    if not evidence and not any("unverified" in warning.lower() for warning in service_warnings):
        service_warnings.append("No verifiable web sources were available for this request.")
    checks = fact_check_agent(initial, evidence)
    critic, issues = critic_agent(initial, checks, evidence)
    score, level, status = calculate_trust(checks, evidence, issues)
    final = final_generator(initial, checks, evidence)
    return AnalyzeResponse(question=question, initial_answer=initial, research=research, fact_check=checks, critic=critic, confidence_score=score, trust_level=level, verification_status=status, detected_issues=issues, final_answer=final, evidence=evidence, agent_analysis={"orchestrator": plan, "research": research, "fact_checker": "Claims were compared against retrieved evidence.", "critic": critic, "trust_engine": f"Score {score}/100 from evidence availability, claim status, and critic flags.", "final_generator": "Final answer excludes claims that are contradicted or unsupported."}, demo_mode=demo_mode, service_warnings=service_warnings)


# Serve the compiled React app from this FastAPI process.  Keep this mount last
# so the API and Swagger routes above continue to take precedence.
frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", CacheControlledStaticFiles(directory=frontend_dist, html=True), name="frontend")
