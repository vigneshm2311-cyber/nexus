import re
import uuid
from nexus.agents.base import BaseAgent
from nexus.db import insert_hypothesis, get_papers_for_hypothesis

SYSTEM = "You are a scientific hypothesis evolver. Output only what is asked, no preamble."

PROMPT = """You are given the top-scoring hypotheses from the previous research round,
along with their strongest supporting evidence and their single most important
stated weakness. Your job is to produce stronger, more specific hypotheses by:
- Combining insights from multiple hypotheses
- Specifically fixing the stated weakness for each hypothesis below — not
  general critique, the EXACT weakness listed
- Anchoring new hypotheses to details from the actual supporting papers
  where relevant (a specific cell type, pathway, dose, or population
  mentioned in the evidence) rather than restating the same generic claim
  more confidently
- Increasing specificity (name exact mechanisms, biomarkers, or populations)
- Closing one or more of the open research gaps listed below, where relevant
- Drawing on the cross-domain analogies listed below for fresh angles, where relevant
- Introducing a novel angle not yet explored

Top hypotheses this round:
{top_hypotheses}
{gap_context}{analogy_context}
Generate exactly {n} evolved hypotheses that are strictly better than the inputs.
Output format — one hypothesis per line, numbered:
1. <hypothesis>
2. <hypothesis>
...
"""

# How much evidence/critique detail to show Evolver per hypothesis. Kept
# deliberately smaller than Critic's own limits (Critic sees up to 8 full
# abstracts) — Evolver's prompt needs to stay short and focused, since it's
# combining info from TWO hypotheses at once, not critiquing one.
PAPERS_PER_HYPOTHESIS = 3
PAPER_SNIPPET_CHAR_CAP = 150
WEAKNESS_CHAR_CAP = 200

MAX_GAPS_USED      = 3
MAX_ANALOGIES_USED = 2


class EvolverAgent(BaseAgent):
    name = "evolver"

    def execute(self, session_id: str, round_num: int, context: dict) -> dict:
        ranked = context["ranked"]
        top_k = self.config.top_k_evolve
        top = ranked[:top_k]

        top_hypotheses = "\n\n".join(
            self._format_hypothesis_block(i, h) for i, h in enumerate(top)
        )

        gap_context     = _format_gap_context(context.get("gaps"))
        analogy_context = _format_analogy_context(context.get("analogies"))

        prompt = PROMPT.format(
            top_hypotheses=top_hypotheses,
            gap_context=gap_context,
            analogy_context=analogy_context,
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

    def _format_hypothesis_block(self, index: int, h: dict) -> str:
        """Builds one hypothesis's full context block: its text, score,
        top supporting papers, and its specific stated weakness — rather
        than a vague critique snippet."""
        papers = get_papers_for_hypothesis(self.conn, h["hypothesis_id"])
        paper_lines = _format_top_papers(papers[:PAPERS_PER_HYPOTHESIS])

        weakness = _extract_weakness(h.get("critique", ""))

        return (
            f"{index + 1}. {h['hypothesis_text']} (score={h['score']})\n"
            f"   Top supporting evidence:\n{paper_lines}\n"
            f"   Specific weakness to fix: {weakness}"
        )


def _row_get(row, key, default=""):
    """Safe field access that works for both sqlite3.Row and plain dicts."""
    try:
        value = row[key]
        return value if value is not None else default
    except (IndexError, KeyError):
        return default


def _format_top_papers(papers: list) -> str:
    if not papers:
        return "   (no supporting papers found)"

    lines = []
    for p in papers:
        title    = str(_row_get(p, "title", "")).strip()
        abstract = str(_row_get(p, "abstract", "")).strip()
        snippet  = abstract[:PAPER_SNIPPET_CHAR_CAP] if abstract else ""
        if snippet:
            lines.append(f"     - {title}: {snippet}...")
        else:
            lines.append(f"     - {title}")
    return "\n".join(lines)


def _extract_weakness(critique: str) -> str:
    """Pulls out specifically the 'Weaknesses or confounders' line from
    Critic's 4-line critique, rather than handing Evolver the whole
    critique blob. Falls back to a capped slice of the full critique if
    the expected line isn't found (e.g. different numbering/formatting
    from a different model) so this never breaks the pipeline — it's an
    enrichment, not a hard dependency."""
    if not critique:
        return "No critique available."

    match = re.search(
        r"(?:weaknesses?|confounders?)[^\n:]*:\s*(.+?)(?:\n\d|\Z)",
        critique, re.IGNORECASE | re.DOTALL
    )
    if match:
        weakness = match.group(1).strip()
        return weakness[:WEAKNESS_CHAR_CAP]

    # Fallback: no recognizable "weakness" line found — use the tail end
    # of the critique, which is where it usually lives even if the
    # numbering/wording differs.
    return critique.strip()[-WEAKNESS_CHAR_CAP:]


def _format_gap_context(gaps) -> str:
    if not gaps:
        return ""

    gap_list = gaps.get("gaps") if isinstance(gaps, dict) else gaps
    if not gap_list:
        return ""

    lines = "\n".join(
        f"- {g.get('gap', '').strip()}"
        for g in gap_list[:MAX_GAPS_USED]
        if g.get("gap")
    )
    if not lines:
        return ""

    return f"\nOpen research gaps to consider:\n{lines}\n"


def _format_analogy_context(analogies) -> str:
    if not analogies:
        return ""

    ana_list = analogies.get("analogies") if isinstance(analogies, dict) else analogies
    if not ana_list:
        return ""

    lines = "\n".join(
        f"- [{a.get('field', '').strip()}] {a.get('new_hypothesis', '').strip()}"
        for a in ana_list[:MAX_ANALOGIES_USED]
        if a.get("new_hypothesis")
    )
    if not lines:
        return ""

    return f"\nCross-domain analogies to consider:\n{lines}\n"


def _parse_hypotheses(raw: str) -> list:
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
