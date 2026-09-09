# TrustAgent

**A Trust-Aware Multi-Agent Framework for Reliable and Verifiable Generative AI** — a small, working research/demo prototype for showing how a factual answer can be inspected before it is presented as trustworthy.

## Problem and objective

Single LLM answers can sound certain even when they are incomplete or hallucinated. TrustAgent separates generation from verification: it retrieves lightweight public evidence, checks the preliminary answer, identifies caveats, calculates a transparent trust score, and returns a corrected/safe final response.

## Architecture

```
Question → Orchestrator → Research → Fact checker → Critic → Trust engine → Final generator
                                                              ↓
                                     Answer + evidence + confidence + detected issues
```

**Baseline:** Single LLM → Answer
**Proposed:** Multi-agent → Research → Fact check → Critic → Trust score → Verified answer

## Agents

- **Orchestrator:** defines the verification plan.
- **Research agent:** obtains public retrieval results and makes an initial answer.
- **Fact-check agent:** labels the main claim Supported, Contradicted, or Uncertain.
- **Critic:** identifies missing evidence and reliability risks.
- **Trust engine:** scores evidence availability/quality, claim result, and critic flags on a simple 0–100 heuristic.
- **Final generator:** only returns an affirmative conclusion when evidence is available; otherwise it explicitly says it cannot verify it.

## Stack

- React + Vite and plain CSS
- Python FastAPI
- Optional OpenAI-compatible chat-completions API through one replaceable `AIService`
- Lightweight Wikipedia search retrieval; no database or user-data storage

## Installation and run

Requirements: Python 3.10+ and Node.js 18+.

```powershell
# from the project root
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
cd frontend
npm install
npm run build
cd ..
uvicorn backend.main:app --reload --port 8000
```

Open `http://localhost:8000`. FastAPI serves both the React interface and the `/api` endpoints from the same address. During UI-only development, `cd frontend; npm run dev` still starts Vite separately on port 5173; set `VITE_API_URL=http://localhost:8000` for that workflow.

## Environment variables

Copy `.env.example` to `.env`. API keys are optional and remain on the backend. For Gemini, set `LLM_PROVIDER=gemini`, add `GEMINI_API_KEY`, and optionally choose `GEMINI_MODEL`. For an OpenAI-compatible provider, set `LLM_PROVIDER=openai` with `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL`. Without a key, TrustAgent runs deterministic safe demo mode. Never add `.env` to version control or expose its key in the frontend.

## API

`GET /api/health` returns service state and whether an LLM is configured.

`POST /api/analyze`

```json
{ "question": "Who invented the telephone?" }
```

The response includes `initial_answer`, `research`, `fact_check`, `critic`, `confidence_score`, `trust_level`, `verification_status`, `detected_issues`, `final_answer`, and `evidence`. Interactive OpenAPI docs are available at `http://localhost:8000/docs`.

## Example and evaluation

Ask **“Who invented the telephone?”** to see an initial answer separated from the evidence-backed final answer, fact-check status, and confidence score.

For research evaluation, compare a baseline single-answer workflow with TrustAgent using answer accuracy, fact-check accuracy, hallucination detection rate, correction success rate, citation/evidence accuracy, confidence calibration, and response time.

## Research novelty and next steps

The project exposes intermediate agent decisions and uses confidence as an interpretable combination of evidence, agreement, and critique rather than hiding verification behind a single answer. Future work can add multiple source providers, claim-level entailment models, benchmark datasets, source credibility weighting, calibration experiments, and audit logging with consent.

## Error handling

Input validation, LLM timeouts/failures, invalid LLM responses, and retrieval failures are handled without crashing the API. If retrieval fails, the UI displays a clearly unverified demo result rather than fabricating evidence.
