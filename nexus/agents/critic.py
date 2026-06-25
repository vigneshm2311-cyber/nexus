from nexus.agents.base import BaseAgent
from nexus.db import get_papers_for_hypothesis

SYSTEM = "You are a rigorous scientific peer reviewer. Be concise and specific."

PROMPT = """Hypothesis: {hypothesis}

Supporting literature ({n_papers} papers found):
{paper_list}

Critically evaluate this hypothesis based on what these papers actually report. Address:
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
            paper_list = _format_papers(papers[:5])

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


def _row_get(row, key, default=""):
    """Safe field access that works for both sqlite3.Row and plain dicts."""
    try:
        value = row[key]
        return value if value is not None else default
    except (IndexError, KeyError):
        return default


def _format_papers(papers: list) -> str:
    if not papers:
        return "No papers found."

    blocks = []
    for p in papers:
        title    = str(_row_get(p, "title", "")).strip()
        abstract = str(_row_get(p, "abstract", "")).strip()
        if abstract:
            blocks.append(f"- {title}\n  Abstract: {abstract}")
        else:
            blocks.append(f"- {title}\n  (no abstract available)")
    return "\n\n".join(blocks)