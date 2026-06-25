import json
import re

from nexus.agents.base import BaseAgent

SYSTEM = "You are a scientific gap analyst. Be specific and actionable. Respond only with valid JSON — no preamble, no markdown fences, no explanation."

GAP_PROMPT = """You are analyzing a set of research hypotheses and their critiques
about the following goal: {goal}

Ranked hypotheses with scores and critiques:
{hypothesis_block}

Low-evidence hypotheses (evidence score < 0.4) — these signal genuine gaps:
{low_evidence_block}

Identify the 3 most important unanswered questions (research gaps) in this field.
For each gap:
- It must be a specific, answerable research question
- It must be directly relevant to the research goal
- It must NOT be answered by existing hypotheses above
- Keep each field to one short sentence — be concise

Respond with ONLY a JSON array of exactly 3 objects, in this exact shape:
[
  {{
    "gap": "<specific research question>",
    "why": "<one short sentence on scientific importance>",
    "approach": "<one short sentence on how to investigate it>",
    "priority": "high"
  }}
]

priority must be exactly one of: "high", "medium", "low".
Do not include any text before or after the JSON array.
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


def _repair_json(raw: str) -> str:
    """Strip markdown fences, isolate the JSON array, and auto-close
    truncated arrays/objects when the model stops generating mid-output."""
    text = raw.strip()

    # Strip markdown code fences (```json ... ``` or ``` ... ```)
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    start = text.find("[")
    if start == -1:
        return text  # no array start at all — let json.loads fail naturally

    end = text.rfind("]")
    if end != -1 and end > start:
        # Array appears closed — just isolate it
        text = text[start:end + 1]
    else:
        # No closing bracket found — the model was cut off mid-array.
        # Truncate back to the last fully-closed object and close the array.
        body = text[start:]
        last_close = body.rfind("}")
        if last_close == -1:
            return text  # nothing usable, let json.loads fail naturally
        text = "[" + body[1:last_close + 1] + "]"

    # Remove trailing commas before ] or }
    text = re.sub(r",\s*([\]}])", r"\1", text)

    return text


def _parse_gaps(raw: str) -> list:
    """Primary parser: JSON (with truncation repair). Falls back to a
    tolerant line-based parser if the model didn't return valid JSON
    despite instructions."""
    cleaned = _repair_json(raw)

    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            gaps = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                gap_text = item.get("gap", "").strip()
                if not gap_text:
                    continue
                gaps.append({
                    "gap": gap_text,
                    "why": item.get("why", "").strip(),
                    "approach": item.get("approach", "").strip(),
                    "priority": str(item.get("priority", "medium")).strip().lower(),
                })
            if gaps:
                return gaps
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass

    return _parse_gaps_fallback(raw)


def _parse_gaps_fallback(raw: str) -> list:
    """Tolerant line-based parser. Handles both:
    - quoted JSON-style keys:  "gap": "...",
    - plain text keys:         Gap: ...
    Also tolerant of numbered/bulleted lines and markdown bold.
    """
    gaps = []
    entry = {}

    line_pattern = re.compile(
        r'^\s*(?:[-*\d.)]+\s*)?\*{0,2}"?(gap|why|why it matters|approach|suggested approach|priority)"?\*{0,2}\s*:\s*"?(.*?)"?,?\s*$',
        re.IGNORECASE,
    )

    key_map = {
        "gap": "gap",
        "why": "why",
        "why it matters": "why",
        "approach": "approach",
        "suggested approach": "approach",
        "priority": "priority",
    }

    for raw_line in raw.splitlines():
        match = line_pattern.match(raw_line.strip())
        if not match:
            continue
        raw_key, value = match.group(1).lower(), match.group(2).strip()
        key = key_map.get(raw_key)
        if not key:
            continue

        if key == "gap":
            if entry.get("gap"):
                gaps.append(entry)
            entry = {"gap": value}
        else:
            entry[key] = value.lower() if key == "priority" else value

    if entry.get("gap"):
        gaps.append(entry)

    for gap in gaps:
        gap.setdefault("why", "")
        gap.setdefault("approach", "")
        gap.setdefault("priority", "medium")

    return gaps


def _score_gaps(gaps: list, low_evidence: list) -> list:
    priority_map = {"high": 3, "medium": 2, "low": 1}
    for gap in gaps:
        base = priority_map.get(gap.get("priority", "medium"), 2)
        gap["priority_score"] = base + (1 if low_evidence else 0)
    gaps.sort(key=lambda x: x["priority_score"], reverse=True)
    return gaps