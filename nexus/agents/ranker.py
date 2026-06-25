import re
import statistics
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

SCORE_RUNS = 3

# Matched by leading characters rather than the full word, so common LLM
# typos (e.g. "Novety" instead of "Novelty") don't cause a silent miss.
# Order matters: longer/more-specific prefixes first to avoid "Nov" ever
# accidentally matching something unintended.
DIMENSION_PREFIXES = {
    "novelty"    : r"nov\w*",
    "evidence"   : r"evid\w*",
    "feasibility": r"feas\w*",
}

class RankerAgent(BaseAgent):
    name = "ranker"

    def execute(self, session_id: str, round_num: int, context: dict) -> dict:
        critiques = context["critiques"]
        ranked    = []

        for c in critiques:
            prompt = PROMPT.format(
                hypothesis=c["hypothesis_text"],
                critique=c["critique"][:400],
                n_papers=c["n_papers"],
            )

            all_novelty     = []
            all_evidence    = []
            all_feasibility = []
            missing_counts  = {"novelty": 0, "evidence": 0, "feasibility": 0}

            for _ in range(SCORE_RUNS):
                raw = self.llm.complete(
                    prompt, system=SYSTEM, temperature=0.1
                )
                n, e, f = _parse_scores(raw)

                if n is None:
                    missing_counts["novelty"] += 1
                else:
                    all_novelty.append(n)

                if e is None:
                    missing_counts["evidence"] += 1
                else:
                    all_evidence.append(e)

                if f is None:
                    missing_counts["feasibility"] += 1
                else:
                    all_feasibility.append(f)

            # A dimension is "unreliable" if a majority of runs failed to
            # produce a real value for it (2 of 3, or worse).
            unreliable_dims = [
                dim for dim, missed in missing_counts.items()
                if missed >= (SCORE_RUNS / 2)
            ]

            novelty     = round(statistics.mean(all_novelty),     4) if all_novelty     else 0.5
            evidence    = round(statistics.mean(all_evidence),    4) if all_evidence    else 0.5
            feasibility = round(statistics.mean(all_feasibility), 4) if all_feasibility else 0.5
            score       = round((novelty + evidence + feasibility) / 3, 4)

            nov_std  = round(statistics.stdev(all_novelty)     if len(all_novelty)     > 1 else 0.0, 4)
            evi_std  = round(statistics.stdev(all_evidence)    if len(all_evidence)    > 1 else 0.0, 4)
            fea_std  = round(statistics.stdev(all_feasibility) if len(all_feasibility) > 1 else 0.0, 4)
            avg_std  = round((nov_std + evi_std + fea_std) / 3, 4)

            if unreliable_dims:
                confidence = "unreliable"
            elif avg_std < 0.1:
                confidence = "high"
            elif avg_std < 0.2:
                confidence = "medium"
            else:
                confidence = "low"

            if unreliable_dims:
                dims_str = ", ".join(unreliable_dims)
                print(f"        [ranker warning] '{c['hypothesis_text'][:50]}...' "
                      f"— unreliable score: {dims_str} could not be parsed in "
                      f"{SCORE_RUNS}/2+ runs")

            update_hypothesis_score(
                self.conn,
                c["hypothesis_id"],
                score, novelty, evidence, feasibility
            )

            ranked.append({
                "hypothesis_id"  : c["hypothesis_id"],
                "hypothesis_text": c["hypothesis_text"],
                "score"          : score,
                "novelty"        : novelty,
                "evidence"       : evidence,
                "feasibility"    : feasibility,
                "std_novelty"    : nov_std,
                "std_evidence"   : evi_std,
                "std_feasibility": fea_std,
                "confidence"     : confidence,
                "unreliable_dims": unreliable_dims,
                "critique"       : c["critique"],
            })

        ranked.sort(key=lambda x: x["score"], reverse=True)

        return {
            "ranked"  : ranked,
            "_summary": (
                f"Ranked {len(ranked)} hypotheses — "
                f"top score: {ranked[0]['score']} "
                f"({ranked[0]['confidence']} confidence)"
                if ranked else "No hypotheses ranked"
            )
        }


def _parse_scores(raw: str) -> tuple:
    return (
        _extract("novelty",     raw),
        _extract("evidence",    raw),
        _extract("feasibility", raw),
    )


def _extract(label: str, text: str):
    """Returns a float in [0,1] if a value was found for this dimension,
    or None if it genuinely could not be located — callers must handle
    None explicitly rather than treating it as a real score."""
    prefix_pattern = DIMENSION_PREFIXES.get(label, label)
    match = re.search(
        rf"{prefix_pattern}\w*[:\s]+([0-9]*\.?[0-9]+)",
        text, re.IGNORECASE
    )
    if match:
        return max(0.0, min(1.0, float(match.group(1))))
    return None