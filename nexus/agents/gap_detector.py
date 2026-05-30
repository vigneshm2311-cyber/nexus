from nexus.agents.base import BaseAgent

SYSTEM = "You are a scientific gap analyst. Be specific and actionable."

GAP_PROMPT = """You are analyzing a set of research hypotheses and their critiques
about the following goal: {goal}

Ranked hypotheses with scores and critiques:
{hypothesis_block}

Low-evidence hypotheses (evidence score < 0.4) — these signal genuine gaps:
{low_evidence_block}

Identify the 5 most important unanswered questions (research gaps) in this field.
For each gap:
- It must be a specific, answerable research question
- It must be directly relevant to the research goal
- It must NOT be answered by existing hypotheses above

Output format — exactly 5 blocks:
Gap: <specific research question>
Why it matters: <one sentence on scientific importance>
Suggested approach: <one sentence on how to investigate it>
Priority: <high / medium / low>

---
Gap: <specific research question>
Why it matters: <one sentence>
Suggested approach: <one sentence>
Priority: <high / medium / low>

(repeat for all 5 gaps)
"""

class GapDetectorAgent(BaseAgent):
    name = "gap_detector"

    def execute(self, session_id: str, round_num: int, context: dict) -> dict:
        ranked = context["ranked"]
        goal   = context["goal"]

        if not ranked:
            return {"gaps": [], "_summary": "No hypotheses to analyse"}

        hypothesis_block = "\n\n".join(
            f"Hypothesis {i+1} (score={h['score']}, "
            f"novelty={h['novelty']}, evidence={h['evidence']}, "
            f"feasibility={h['feasibility']}):\n"
            f"{h['hypothesis_text']}\n"
            f"Critique: {h['critique'][:300]}"
            for i, h in enumerate(ranked)
        )

        low_evidence = [h for h in ranked if h.get("evidence", 1.0) < 0.4]
        if low_evidence:
            low_evidence_block = "\n".join(
                f"- {h['hypothesis_text'][:100]} (evidence={h['evidence']})"
                for h in low_evidence
            )
        else:
            low_evidence_block = "None identified."

        prompt = GAP_PROMPT.format(
            goal=goal,
            hypothesis_block=hypothesis_block,
            low_evidence_block=low_evidence_block,
        )

        raw = self.llm.complete(prompt, system=SYSTEM)
        gaps = _parse_gaps(raw)

        gaps = _score_gaps(gaps, low_evidence)

        return {
            "gaps": gaps,
            "_summary": f"Identified {len(gaps)} research gaps"
        }

def _parse_gaps(raw: str) -> list:
    gaps = []
    blocks = raw.strip().split("---")
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines = block.splitlines()
        entry = {}
        for line in lines:
            line = line.strip()
            if line.lower().startswith("gap:"):
                entry["gap"] = line.split(":", 1)[1].strip()
            elif line.lower().startswith("why it matters:"):
                entry["why"] = line.split(":", 1)[1].strip()
            elif line.lower().startswith("suggested approach:"):
                entry["approach"] = line.split(":", 1)[1].strip()
            elif line.lower().startswith("priority:"):
                entry["priority"] = line.split(":", 1)[1].strip().lower()
        if entry.get("gap"):
            gaps.append(entry)
    return gaps

def _score_gaps(gaps: list, low_evidence: list) -> list:
    priority_map = {"high": 3, "medium": 2, "low": 1}
    for gap in gaps:
        base = priority_map.get(gap.get("priority", "medium"), 2)
        gap["priority_score"] = base + (1 if low_evidence else 0)
    gaps.sort(key=lambda x: x["priority_score"], reverse=True)
    return gaps
