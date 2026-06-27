from dataclasses import dataclass, field
from dotenv import load_dotenv
import os

load_dotenv()

@dataclass
class ResearchConfig:
    # LLM
    llm_backend: str = field(default_factory=lambda: os.getenv("LLM_BACKEND", "ollama"))
    ollama_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3.1"))
    ollama_base_url: str = field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    grok_api_key: str = field(default_factory=lambda: os.getenv("GROK_API_KEY", ""))
    grok_model: str = field(default_factory=lambda: os.getenv("GROK_MODEL", "grok-beta"))

    # Research loop
    max_rounds: int = 3
    hypotheses_per_round: int = 5
    top_k_evolve: int = 3
    papers_per_hypothesis: int = 3

    # Storage
    db_path: str = "nexus.db"
    output_dir: str = "outputs"

    def validate(self):
        if self.llm_backend not in ("ollama", "grok"):
            raise ValueError(f"LLM_BACKEND must be 'ollama' or 'grok', got: {self.llm_backend}")
        if self.llm_backend == "grok" and not self.grok_api_key:
            raise ValueError("GROK_API_KEY is required when LLM_BACKEND=grok")
        return self
