import uuid
from nexus.agents.base import BaseAgent
from nexus.db import insert_hypothesis

SYSTEM = "You are a scientific hypothesis evolver. Output only what is asked, no preamble."

PROMPT = """You are given the top-scoring hypotheses from the previous research round.
Your job is to produce stronger, more specific hypotheses by:
- Combining insights from multiple hypotheses
- Addressing weaknesses noted in the critiques
- Increasing specificity (name exact mechanisms, biomarkers, or populations)
- Introducing a novel angle not yet explored

Top hypotheses this round:
{top_hypotheses}

Their critiques:
{critiques}

Generate exactly {n} evolved hypotheses that are strictly better than the inputs.
Output format — one hypothesis per line, numbered:
1. <hypothesis>
2. <hypothesis>
...
"""

class EvolverAgent(BaseAgent):
    name = "evolver"

    def execute(self, session_id: str, round_num: int, context: dict) -> dict:
        ranked = context["ranked"]
        top_k = self.config.top_k_evolve
        top = ranked[:top_k]

        top_hypotheses = "\n".join(
            f"{i+1}. {h['hypothesis_text']} (score={h['score']})"
            for i, h in enumerate(top)
        )
        critiques = "\n".join(
            f"- {h['hypothesis_text'][:60]}... → {h['critique'][:120]}"
            for h in top
        )

        prompt = PROMPT.format(
            top_hypotheses=top_hypotheses,
            critiques=critiques,
            n=self.config.hypotheses_per_round,
        )

        raw = self.llm.complete(prompt, system=SYSTEM)
        evolved = _parse_hypotheses(raw)

        seeds = []
        for text in evolved:
            h_id = str(uuid.uuid4())
            parent_id = top[0]["hypothesis_id"] if top else None
            insert_hypothesis(
                self.conn, h_id, session_id, text,
                round_num, parent_id=parent_id
            )
            seeds.append({"id": h_id, "text": text})

        return {
            "seeds": seeds,
            "seed_texts": [s["text"] for s in seeds],
            "_summary": f"Evolved {len(seeds)} hypotheses from top-{top_k}"
        }

def _parse_hypotheses(raw: str) -> list:
    import re
    lines = raw.strip().splitlines()
    results = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        cleaned = re.sub(r"^\d+[\.\)]\s*", "", line).strip()
        if len(cleaned) > 20:
            results.append(cleaned)
    return results
