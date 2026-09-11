"""A small, replaceable LLM client. Keys never leave the backend."""
from dataclasses import dataclass
import os

import httpx

from .models import Evidence


@dataclass
class GroundedAnswer:
    """A Gemini answer plus the web sources returned with it."""

    answer: str
    evidence: list[Evidence]


class AIService:
    def __init__(self) -> None:
        self.provider = os.getenv("LLM_PROVIDER", "openai").lower().strip()
        self.api_key = os.getenv("LLM_API_KEY", "")
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        if self.provider == "groq":
            # Groq implements OpenAI's chat-completions interface. Keeping this
            # configuration separate avoids overloading generic LLM variables
            # and ensures the browser never receives the provider credential.
            self.api_key = os.getenv("GROQ_API_KEY", "") or self.api_key
            self.base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
            self.model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b") or "openai/gpt-oss-120b"
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        self.timeout = _timeout_from_env("LLM_TIMEOUT_SECONDS", default=15.0)

    @property
    def available(self) -> bool:
        return bool(self.gemini_api_key) if self.provider == "gemini" else bool(self.api_key)

    async def complete(self, system: str, prompt: str) -> str:
        if self.provider == "gemini":
            return await self._complete_gemini(system, prompt)
        return await self._complete_openai_compatible(system, prompt)

    async def grounded_answer(self, question: str) -> GroundedAnswer:
        """Answer using Gemini Search grounding and return its cited web sources.

        This replaces the old Wikipedia-then-LLM sequence for Gemini requests.
        It is both faster (one provider request) and gives the fact checker the
        exact sources used to generate the answer.
        """
        if self.provider != "gemini":
            raise RuntimeError("Search grounding is currently available only for Gemini.")
        if not self.available:
            raise RuntimeError("GEMINI_API_KEY is not configured.")

        payload = {
            "contents": [{"parts": [{"text": (
                "Answer this factual question concisely. Use Google Search to ground "
                "the answer in reliable web sources. Do not make a claim that the "
                "grounded sources do not support.\n\n"
                f"Question: {question}"
            )}]}],
            "tools": [{"google_search": {}}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 360},
        }
        data = await self._gemini_request(payload)
        try:
            candidate = data["candidates"][0]
            parts = candidate["content"]["parts"]
            answer = "".join(part.get("text", "") for part in parts).strip()
        except (KeyError, IndexError, TypeError) as error:
            raise RuntimeError("Gemini returned an unexpected response.") from error
        if not answer:
            raise RuntimeError("Gemini returned an empty response.")

        metadata = candidate.get("groundingMetadata") or {}
        evidence = _grounding_evidence(metadata.get("groundingChunks") or [])
        return GroundedAnswer(answer=answer, evidence=evidence)

    async def _complete_openai_compatible(self, system: str, prompt: str) -> str:
        if not self.available:
            key_name = "GROQ_API_KEY" if self.provider == "groq" else "LLM_API_KEY"
            raise RuntimeError(f"{key_name} is not configured")
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 360,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
                if response.status_code == 404 and self.provider == "groq" and self.model != "openai/gpt-oss-120b":
                    payload["model"] = "openai/gpt-oss-120b"
                    response = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("The LLM returned an empty response")
                return content.strip()
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as error:
            raise RuntimeError(f"LLM request failed: {error}") from error

    async def _complete_gemini(self, system: str, prompt: str) -> str:
        if not self.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        payload = {
            "contents": [{"parts": [{"text": f"System instructions:\n{system}\n\nUser request:\n{prompt}"}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 360},
        }
        data = await self._gemini_request(payload)
        try:
            parts = data["candidates"][0]["content"]["parts"]
            content = "".join(part.get("text", "") for part in parts).strip()
        except (KeyError, IndexError, TypeError) as error:
            raise RuntimeError("Gemini returned an unexpected response.") from error
        if not content:
            raise RuntimeError("Gemini returned an empty response.")
        return content

    async def _gemini_request(self, payload: dict) -> dict:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers={"x-goog-api-key": self.gemini_api_key})
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as error:
            raise RuntimeError("Gemini request timed out. Try again or increase LLM_TIMEOUT_SECONDS.") from error
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 429:
                raise RuntimeError(
                    "Gemini is rate limited (HTTP 429). Wait for quota to reset or enable additional Gemini API capacity."
                ) from error
            raise RuntimeError(
                f"Gemini returned HTTP {error.response.status_code}. Check the model name and API-key permissions."
            ) from error
        except (httpx.HTTPError, ValueError) as error:
            raise RuntimeError("Gemini could not be reached. Check the network connection.") from error


def _timeout_from_env(name: str, default: float) -> float:
    try:
        return max(3.0, min(float(os.getenv(name, str(default))), 60.0))
    except ValueError:
        return default


def _grounding_evidence(chunks: list[dict]) -> list[Evidence]:
    """Normalize documented Gemini grounding chunks into the app's source model."""
    evidence: list[Evidence] = []
    seen_urls: set[str] = set()
    for chunk in chunks:
        web = chunk.get("web") if isinstance(chunk, dict) else None
        if not isinstance(web, dict):
            continue
        url = web.get("uri")
        if not isinstance(url, str) or not url.startswith(("https://", "http://")) or url in seen_urls:
            continue
        seen_urls.add(url)
        title = web.get("title")
        evidence.append(Evidence(
            title=title.strip() if isinstance(title, str) and title.strip() else "Grounded web source",
            url=url,
            snippet="Source returned by Gemini Google Search grounding.",
            quality="Medium",
        ))
    return evidence
