from abc import ABC, abstractmethod
from nexus.config import ResearchConfig
from nexus.llm import LLMClient
from nexus.db import log_agent
import sqlite3

class BaseAgent(ABC):
    name: str = "base"

    def __init__(self, config: ResearchConfig, llm: LLMClient, conn: sqlite3.Connection):
        self.config = config
        self.llm = llm
        self.conn = conn

    def run(self, session_id: str, round_num: int, context: dict) -> dict:
        result = self.execute(session_id, round_num, context)
        log_agent(
            self.conn,
            session_id,
            round_num,
            self.name,
            input_summary=str(context.get("_summary", ""))[:300],
            output_summary=str(result.get("_summary", ""))[:300],
        )
        return result

    @abstractmethod
    def execute(self, session_id: str, round_num: int, context: dict) -> dict:
        pass
