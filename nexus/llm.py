import requests
import json
from nexus.config import ResearchConfig

class LLMClient:
    def __init__(self, config: ResearchConfig):
        self.config = config

    def complete(self, prompt: str, system: str = "") -> str:
        if self.config.llm_backend == "ollama":
            return self._ollama(prompt, system)
        elif self.config.llm_backend == "grok":
            return self._grok(prompt, system)
        else:
            raise ValueError(f"Unknown backend: {self.config.llm_backend}")

    def _ollama(self, prompt: str, system: str) -> str:
        payload = {
            "model": self.config.ollama_model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system

        try:
            resp = requests.post(
                f"{self.config.ollama_base_url}/api/generate",
                json=payload,
                timeout=120
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except requests.exceptions.ConnectionError:
            raise RuntimeError("Ollama not running. Start it with: ollama serve")
        except requests.exceptions.Timeout:
            raise RuntimeError("Ollama timed out. Try a smaller model.")

    def _grok(self, prompt: str, system: str) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            resp = requests.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.config.grok_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.config.grok_model,
                    "messages": messages,
                    "temperature": 0.7
                },
                timeout=60
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"Grok API error: {e.response.status_code} {e.response.text}")
