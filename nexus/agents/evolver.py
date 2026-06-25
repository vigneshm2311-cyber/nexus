import uuid
from nexus.agents.base import BaseAgent
from nexus.db import insert_hypothesis

SYSTEM = "You are a scientific hypothesis evolver. Output only what is asked, no preamble."

PROMPT = """You are given the top-scoring hypotheses from the previous research round.
Your job is to produce stronger, more specific hypotheses by:
- Combining insights from multiple hypotheses
- Addressing weaknesses noted in the critiques
- Increasing specificity (name exact mechanisms, biomarkers, or populations)
- Closing one or more of the open research gaps listed below, where relevant
- Drawing on the cross-domain analogies listed below for fresh angles, where relevant
- Introducing a novel angle not yet explored

Top hypotheses this round:
{top_hypotheses}

Their critiques:
{critiques}
{gap_context}{analogy_context}
Generate exactly {n} evolved hypotheses that are strictly better than the inputs.
Output format — one hypothesis per line, numbered:
1. <hypothesis>
2. <hypothesis>
...
"""

# Keep these caps generous but bounded — full critique text matters (the
# "weaknesses" line was previously cut off at 120 chars), but we still
# don't want to feed the model unbounded text that risks the same kind
# of truncation issues fixed elsewhere in the pipeline.
CRITIQUE_CHAR_CAP = 500
MAX_GAPS_USED      = 3
MAX_ANALOGIES_USED = 2

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
            f"- {h['hypothesis_text'][:60]}... → {h['critique'][:CRITIQUE_CHAR_CAP]}"
            for h in top
        )

        gap_context     = _format_gap_context(context.get("gaps"))
        analogy_context = _format_analogy_context(context.get("analogies"))

        prompt = PROMPT.format(
            top_hypotheses=top_hypotheses,
            critiques=critiques,
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


def _format_gap_context(gaps) -> str:
    """gaps is expected to be the dict returned by GapDetectorAgent.execute(),
    i.e. {"gaps": [...], "_summary": ...}. Tolerant of None or missing keys
    so Evolver never breaks if gaps weren't computed this round."""
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
    """analogies is expected to be the dict returned by
    AnalogyBridgeAgent.execute(), i.e. {"analogies": [...], "mechanism": ...,
    ...}. Tolerant of None or missing keys."""
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