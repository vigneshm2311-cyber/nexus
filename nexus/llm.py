import time
import requests
from nexus.config import ResearchConfig

MAX_RETRIES   = 3
RETRY_BACKOFF = 2

class LLMClient:
    def __init__(self, config: ResearchConfig):
        self.config = config

    def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        fallback: str = ""
    ) -> str:
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                if self.config.llm_backend == "ollama":
                    result = self._ollama(prompt, system, temperature)
                elif self.config.llm_backend == "grok":
                    result = self._grok(prompt, system, temperature)
                else:
                    raise ValueError(f"Unknown backend: {self.config.llm_backend}")

                if self._valid(result):
                    return result

                raise ValueError(f"Empty or invalid response: {repr(result)}")

            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_BACKOFF ** attempt
                    print(f"        [llm retry {attempt+1}/{MAX_RETRIES}] {e} — retrying in {wait}s")
                    time.sleep(wait)

        print(f"        [llm failed after {MAX_RETRIES} attempts] {last_error}")
        return fallback

    def _valid(self, response: str) -> bool:
        return bool(response and len(response.strip()) > 10)

    def _ollama(self, prompt: str, system: str, temperature: float) -> str:
        payload = {
            "model"  : self.config.ollama_model,
            "prompt" : prompt,
            "stream" : False,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system

        resp = requests.post(
            f"{self.config.ollama_base_url}/api/generate",
            json=payload,
            timeout=120
        )
        resp.raise_for_status()
        result = resp.json().get("response", "").strip()
        return result

    def _grok(self, prompt: str, system: str, temperature: float) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.config.grok_api_key}",
                "Content-Type" : "application/json"
            },
            json={
                "model"      : self.config.grok_model,
                "messages"   : messages,
                "temperature": temperature,
            },
            timeout=60
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
