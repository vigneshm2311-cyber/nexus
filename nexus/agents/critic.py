from nexus.agents.base import BaseAgent
from nexus.db import get_papers_for_hypothesis

SYSTEM = "You are a rigorous scientific peer reviewer. Be concise and specific."

PROMPT = """Hypothesis: {hypothesis}

Supporting literature ({n_papers} papers found):
{paper_list}

Critically evaluate this hypothesis. Address:
1. Scientific plausibility
2. Novelty (is this already well established?)
3. Testability (can it be experimentally validated?)
4. Weaknesses or confounders

Respond in exactly 4 lines, one per point above. Be blunt.
"""

class CriticAgent(BaseAgent):
    name = "critic"

    def execute(self, session_id: str, round_num: int, context: dict) -> dict:
        hypotheses = context["hypotheses"]
        critiques = []

        for h in hypotheses:
            papers = get_papers_for_hypothesis(self.conn, h["id"])
            paper_list = "\n".join(
                f"- {p['title']}" for p in papers[:5]
            ) or "No papers found."

            prompt = PROMPT.format(
                hypothesis=h["text"],
                n_papers=len(papers),
                paper_list=paper_list,
            )

            critique = self.llm.complete(prompt, system=SYSTEM)
            critiques.append({
                "hypothesis_id": h["id"],
                "hypothesis_text": h["text"],
                "critique": critique.strip(),
                "n_papers": len(papers),
            })

        return {
            "critiques": critiques,
            "_summary": f"Critiqued {len(critiques)} hypotheses"
        }
