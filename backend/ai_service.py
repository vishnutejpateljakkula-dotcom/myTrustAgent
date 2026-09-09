"""A small, replaceable LLM client. Keys never leave the backend."""
import os
import httpx


class AIService:
    def __init__(self) -> None:
        self.provider = os.getenv("LLM_PROVIDER", "openai").lower().strip()
        self.api_key = os.getenv("LLM_API_KEY", "")
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

    @property
    def available(self) -> bool:
        return bool(self.gemini_api_key) if self.provider == "gemini" else bool(self.api_key)

    async def complete(self, system: str, prompt: str) -> str:
        if self.provider == "gemini":
            return await self._complete_gemini(system, prompt)
        return await self._complete_openai_compatible(system, prompt)

    async def _complete_openai_compatible(self, system: str, prompt: str) -> str:
        if not self.available:
            raise RuntimeError("LLM_API_KEY is not configured")
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 700,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            async with httpx.AsyncClient(timeout=25) as client:
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
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 700},
        }
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent"
        try:
            async with httpx.AsyncClient(timeout=25) as client:
                response = await client.post(url, json=payload, headers={"x-goog-api-key": self.gemini_api_key})
                response.raise_for_status()
                parts = response.json()["candidates"][0]["content"]["parts"]
                content = "".join(part.get("text", "") for part in parts).strip()
                if not content:
                    raise ValueError("The Gemini API returned an empty response")
                return content
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
            raise RuntimeError(f"Gemini request failed: {error}") from error
