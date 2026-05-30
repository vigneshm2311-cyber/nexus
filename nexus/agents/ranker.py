import re
from nexus.agents.base import BaseAgent
from nexus.db import update_hypothesis_score

SYSTEM = "You are a scientific hypothesis evaluator. Output only numbers, no explanation."

PROMPT = """Score this hypothesis on three dimensions. Reply with exactly three lines:
Novelty: <0.0-1.0>
Evidence: <0.0-1.0>
Feasibility: <0.0-1.0>

Hypothesis: {hypothesis}

Critique summary: {critique}

Papers found: {n_papers}

Scoring guide:
- Novelty: 1.0 = completely new idea, 0.0 = textbook knowledge
- Evidence: 1.0 = many strong papers support it, 0.0 = no literature
- Feasibility: 1.0 = testable with standard lab methods, 0.0 = untestable
"""

class RankerAgent(BaseAgent):
    name = "ranker"

    def execute(self, session_id: str, round_num: int, context: dict) -> dict:
        critiques = context["critiques"]
        ranked = []

        for c in critiques:
            prompt = PROMPT.format(
                hypothesis=c["hypothesis_text"],
                critique=c["critique"][:400],
                n_papers=c["n_papers"],
            )

            raw = self.llm.complete(prompt, system=SYSTEM)
            novelty, evidence, feasibility = _parse_scores(raw)
            score = round((novelty + evidence + feasibility) / 3, 4)

            update_hypothesis_score(
                self.conn,
                c["hypothesis_id"],
                score, novelty, evidence, feasibility
            )

            ranked.append({
                "hypothesis_id": c["hypothesis_id"],
                "hypothesis_text": c["hypothesis_text"],
                "score": score,
                "novelty": novelty,
                "evidence": evidence,
                "feasibility": feasibility,
                "critique": c["critique"],
            })

        ranked.sort(key=lambda x: x["score"], reverse=True)

        return {
            "ranked": ranked,
            "_summary": f"Ranked {len(ranked)} hypotheses, top score: {ranked[0]['score'] if ranked else 0}"
        }

def _parse_scores(raw: str) -> tuple:
    defaults = (0.5, 0.5, 0.5)
    try:
        novelty = _extract("novelty", raw)
        evidence = _extract("evidence", raw)
        feasibility = _extract("feasibility", raw)
        return novelty, evidence, feasibility
    except Exception:
        return defaults

def _extract(label: str, text: str) -> float:
    pattern = rf"{label}[:\s]+([0-9]*\.?[0-9]+)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        val = float(match.group(1))
        return max(0.0, min(1.0, val))
    return 0.5
