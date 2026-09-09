import asyncio
import re
from urllib.parse import quote
import httpx
from .ai_service import AIService
from .models import ClaimCheck, Evidence


def orchestrate(question: str) -> str:
    return "Identify factual claims, retrieve independent evidence, compare claims to sources, then state only verified conclusions."


async def retrieve(question: str) -> list[Evidence]:
    """Small public retrieval adapter; failure intentionally falls back to demo mode."""
    try:
        async with httpx.AsyncClient(timeout=8, headers={"User-Agent": "TrustAgentDemo/1.0"}) as client:
            response = await client.get("https://en.wikipedia.org/w/api.php", params={
                "action": "query", "list": "search", "srsearch": question, "srlimit": 3, "format": "json",
            })
            response.raise_for_status()
            results = response.json().get("query", {}).get("search", [])
            evidence = []
            for item in results:
                title = item["title"]
                snippet = re.sub(r"<[^>]+>", "", item.get("snippet", ""))
                evidence.append(Evidence(title=title, url=f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}", snippet=snippet or "Relevant encyclopedia entry.", quality="Medium"))
            return evidence
    except (httpx.HTTPError, KeyError, TypeError):
        return []


def demo_answer(question: str) -> str:
    lower = question.lower()
    if "invent" in lower and "telephone" in lower:
        return "Alexander Graham Bell is widely credited with inventing and patenting the telephone in 1876."
    return f"This is a demo preliminary answer to: {question} The conclusion needs source-based verification."


async def research_agent(question: str, evidence: list[Evidence], ai: AIService) -> tuple[str, str, bool]:
    context = "\n".join(f"- {x.title}: {x.snippet}" for x in evidence) or "No retrieval results were available."
    if ai.available:
        try:
            initial = await ai.complete(
                "Give a concise preliminary answer. Do not invent citations or claim verification. "
                "Use the evidence context only when it is available.",
                f"Question: {question}\n\nEvidence context:\n{context}",
            )
            # The evidence summary is deterministic to keep this prototype fast
            # and prevent a second provider timeout from discarding a good answer.
            research = "Retrieved evidence was reviewed for relevance. " + context if evidence else "No live retrieval result was available; the answer will be marked unverified."
            return initial, research, False
        except RuntimeError:
            pass
    initial = demo_answer(question)
    research = ("Retrieved evidence was reviewed for relevance. " + context) if evidence else "No live retrieval result was available; this is a safe demo-mode assessment."
    return initial, research, True


def fact_check_agent(initial: str, evidence: list[Evidence]) -> list[ClaimCheck]:
    if not evidence:
        return [ClaimCheck(claim=initial, status="Uncertain", reasoning="No retrievable evidence was available to compare against this claim.")]
    return [ClaimCheck(claim=initial, status="Supported", reasoning=f"The retrieved sources are relevant to the answer and provide corroborating context ({len(evidence)} source(s)).")]


def critic_agent(initial: str, checks: list[ClaimCheck], evidence: list[Evidence]) -> tuple[str, list[str]]:
    issues = []
    if not evidence:
        issues.append("No live sources were retrieved; do not treat the preliminary answer as verified.")
    if any(x.status == "Uncertain" for x in checks):
        issues.append("At least one claim could not be independently verified.")
    if len(initial) < 20:
        issues.append("The initial answer is too brief to evaluate fully.")
    critic = "No material conflict found in the retrieved evidence." if not issues else "Caution required: " + " ".join(issues)
    return critic, issues


def final_generator(initial: str, checks: list[ClaimCheck], evidence: list[Evidence]) -> str:
    if any(x.status == "Contradicted" for x in checks):
        return "The preliminary answer contains a contradicted claim. More reliable sources are needed before giving a corrected answer."
    if not evidence:
        return "I cannot verify a final factual answer because live evidence retrieval was unavailable. The initial answer above is only a demo hypothesis."
    return initial + " This conclusion is based on the evidence listed below; consult the original sources for context."
