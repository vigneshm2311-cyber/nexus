import uuid
from nexus.agents.base import BaseAgent
from nexus.db import insert_hypothesis

SYSTEM = "You are a rigorous scientific hypothesis generator. Output only what is asked, no preamble."

PROMPT = """Research goal: {goal}
Domain: {domain}
Keywords: {keywords}
Round: {round_num}
{seed_context}

Generate exactly {n} distinct, testable scientific hypotheses relevant to this goal.
Each hypothesis must:
- Be a single sentence
- Be falsifiable
- Be specific (name mechanisms, molecules, or populations where possible)

Output format — one hypothesis per line, numbered:
1. <hypothesis>
2. <hypothesis>
...
"""

class GenesisAgent(BaseAgent):
    name = "genesis"

    def execute(self, session_id: str, round_num: int, context: dict) -> dict:
        seed_context = ""
        if context.get("seeds"):
            seed_list = "\n".join(f"- {s}" for s in context["seeds"])
            seed_context = f"Evolve or build upon these prior hypotheses:\n{seed_list}"

        prompt = PROMPT.format(
            goal=context["goal"],
            domain=context["domain"],
            keywords=", ".join(context["keywords"]),
            round_num=round_num,
            n=self.config.hypotheses_per_round,
            seed_context=seed_context,
        )

        raw = self.llm.complete(prompt, system=SYSTEM, temperature=0.9)
        hypotheses = _parse_hypotheses(raw)

        ids = []
        for text in hypotheses:
            h_id = str(uuid.uuid4())
            insert_hypothesis(
                self.conn, h_id, session_id, text, round_num,
                parent_id=context.get("parent_id")
            )
            ids.append({"id": h_id, "text": text})

        return {
            "hypotheses": ids,
            "_summary": f"Generated {len(ids)} hypotheses"
        }

def _parse_hypotheses(raw: str) -> list:
    lines = raw.strip().splitlines()
    results = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        import re
        cleaned = re.sub(r"^\d+[\.\)]\s*", "", line).strip()
        if len(cleaned) > 20:
            results.append(cleaned)
    return results
