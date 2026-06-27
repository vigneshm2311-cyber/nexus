import json
import re

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

RELEVANCE_SYSTEM = (
    "You are a scientific literature relevance assessor. Judge whether each "
    "paper's findings provide real evidence — direct OR mechanistic — for the "
    "hypothesis. A paper need not mention the specific compound by name to be "
    "relevant; a paper about the same biological mechanism in a different "
    "context can still count as supporting evidence. Output only what is asked."
)

RELEVANCE_PROMPT = """Hypothesis: {hypothesis}

For each paper below, rate how relevant its findings are as evidence for this
specific hypothesis, from 0.0 to 1.0:
- 1.0 = directly tests or supports this exact mechanism/claim
- 0.6-0.9 = relevant mechanism evidence, even if about a different compound,
  cell type, or context (e.g. a paper about the same pathway or gene)
- 0.2-0.5 = tangentially related (shares a general topic like "skin aging"
  or "inflammation" but not the specific mechanism)
- 0.0-0.1 = unrelated to this hypothesis

Papers:
{paper_block}

Respond with ONLY a single JSON array of {n_papers} objects, in this exact
order matching the papers above, in this exact shape:
[
  {{"index": 0, "relevance": 0.8}},
  {{"index": 1, "relevance": 0.2}}
]

Return exactly ONE JSON array containing all {n_papers} objects — do not
split the response into multiple separate arrays.
Do not include any text before or after the JSON array.
"""

MAX_PAPERS_TO_SCORE = 18
ABSTRACT_SCORING_CHAR_CAP = 250
TOP_N_FOR_CRITIQUE = 8


class CriticAgent(BaseAgent):
    name = "critic"

    def execute(self, session_id: str, round_num: int, context: dict) -> dict:
        hypotheses = context["hypotheses"]
        critiques = []

        for h in hypotheses:
            papers = get_papers_for_hypothesis(self.conn, h["id"])
            top_papers = self._select_top_papers(h["text"], papers)
            paper_list = _format_papers(top_papers)

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

    def _select_top_papers(self, hypothesis_text: str, papers: list) -> list:
        if not papers:
            return []

        candidates = list(papers)[:MAX_PAPERS_TO_SCORE]

        try:
            scores = self._score_relevance_llm(hypothesis_text, candidates)
        except Exception as e:
            print(f"        [critic relevance error] {e}")
            scores = None

        if not scores:
            return candidates[:TOP_N_FOR_CRITIQUE]

        scored = list(zip(candidates, scores))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return [p for p, _ in scored[:TOP_N_FOR_CRITIQUE]]

    def _score_relevance_llm(self, hypothesis_text: str, papers: list):
        paper_block = "\n".join(
            f"{i}. {_row_get(p, 'title', '')}\n"
            f"   {(_row_get(p, 'abstract', '') or 'No abstract available.')[:ABSTRACT_SCORING_CHAR_CAP]}"
            for i, p in enumerate(papers)
        )

        prompt = RELEVANCE_PROMPT.format(
            hypothesis=hypothesis_text,
            paper_block=paper_block,
            n_papers=len(papers),
        )

        raw = self.llm.complete(prompt, system=RELEVANCE_SYSTEM, temperature=0.1)
        parsed = _parse_relevance_scores(raw, len(papers))
        return parsed


def _row_get(row, key, default=""):
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


def _extract_all_json_arrays(text: str) -> list:
    """Finds every top-level [...] array in the text, even if the model
    returned multiple separate arrays back to back (observed with mistral
    on the relevance-scoring prompt: it split a 4-item array into two
    separate 2-item arrays). Returns a list of raw array substrings."""
    arrays = []
    depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == "[":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0 and start is not None:
                arrays.append(text[start:i + 1])
                start = None
    return arrays


def _repair_json(raw: str) -> str:
    """Strip markdown fences, isolate the JSON array, and auto-close
    truncated arrays/objects when the model stops generating mid-output."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    start = text.find("[")
    if start == -1:
        return text

    end = text.rfind("]")
    if end != -1 and end > start:
        text = text[start:end + 1]
    else:
        body = text[start:]
        last_close = body.rfind("}")
        if last_close == -1:
            return text
        text = "[" + body[1:last_close + 1] + "]"

    text = re.sub(r",\s*([\]}])", r"\1", text)
    return text


def _parse_relevance_scores(raw: str, n_papers: int):
    """Returns a list of floats aligned by index to the original papers
    list, or None if parsing genuinely failed. Handles three cases:
    1. A single well-formed JSON array (the common case)
    2. A single array with truncation/trailing-comma issues (repaired)
    3. Multiple separate JSON arrays concatenated (seen with mistral) —
       merges all objects found across every array into one result set
    """
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    all_items = []

    # Try the multi-array extraction first, since it's a strict superset:
    # a single well-formed array is just "one array found" under this
    # same logic, so we don't need a separate code path for the common
    # case.
    raw_arrays = _extract_all_json_arrays(cleaned)

    if raw_arrays:
        for arr_text in raw_arrays:
            try:
                data = json.loads(arr_text)
                if isinstance(data, list):
                    all_items.extend(data)
            except json.JSONDecodeError:
                # This particular array segment is malformed (e.g.
                # truncated) — try the single-array repair path on just
                # this segment before giving up on it.
                repaired = _repair_json(arr_text)
                try:
                    data = json.loads(repaired)
                    if isinstance(data, list):
                        all_items.extend(data)
                except (json.JSONDecodeError, TypeError):
                    continue
    else:
        # No bracket-matched array found at all — fall back to the
        # original truncation-repair path on the whole text.
        repaired = _repair_json(cleaned)
        try:
            data = json.loads(repaired)
            if isinstance(data, list):
                all_items = data
        except (json.JSONDecodeError, TypeError):
            return None

    if not all_items:
        return None

    by_index = {}
    for item in all_items:
        if not isinstance(item, dict):
            continue
        idx = item.get("index")
        rel = item.get("relevance")
        if idx is None or rel is None:
            continue
        try:
            idx = int(idx)
            rel = max(0.0, min(1.0, float(rel)))
            by_index[idx] = rel
        except (ValueError, TypeError):
            continue

    if not by_index:
        return None

    return [by_index.get(i, 0.3) for i in range(n_papers)]
