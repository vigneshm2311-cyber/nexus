"""
Side-by-side comparison of llama3.2, mistral, and gemma4:e4b on three
real prompts that caused failures in NEXUS today:

1. Gap Detector — JSON array output (truncated mid-array with llama3.2)
2. Ranker — scoring prompt (llama3.2 misspelled "Novelty" as "Novety")
3. Critic relevance scorer — JSON array of paper relevance scores

Run from the nexus/ project root:
    python3 model_comparison.py
"""
import sys
import time
import json
import re

sys.path.insert(0, '.')
from nexus.config import ResearchConfig
from nexus.llm import LLMClient

MODELS_TO_TEST = ["llama3.2", "mistral", "gemma4:e4b"]

# ─────────────────────────────────────────────────────────────────────────
# Test 1: Gap Detector JSON prompt
# ─────────────────────────────────────────────────────────────────────────
GAP_SYSTEM = "You are a scientific gap analyst. Be specific and actionable. Respond only with valid JSON — no preamble, no markdown fences, no explanation."

GAP_PROMPT = """You are analyzing a set of research hypotheses and their critiques
about the following goal: Bakuchiol for anti-ageing?

Ranked hypotheses with scores and critiques:
Hypothesis 1 (score=0.733, novelty=0.5, evidence=0.8, feasibility=0.9):
Bakuchiol modulates the activity of the Wnt/beta-catenin signaling pathway in human keratinocytes, thereby reducing the expression of pro-inflammatory cytokines TNF-alpha and IL-1beta, which are associated with skin ageing and inflammation.
Critique: The hypothesis is plausible based on the known roles of Bakuchiol and Wnt/beta-catenin signaling pathway in modulating inflammation and skin health.

Low-evidence hypotheses (evidence score < 0.4) -- these signal genuine gaps:
None identified.

Identify the 3 most important unanswered questions (research gaps) in this field.
For each gap:
- It must be a specific, answerable research question
- It must be directly relevant to the research goal
- It must NOT be answered by existing hypotheses above
- Keep each field to one short sentence -- be concise

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

# ─────────────────────────────────────────────────────────────────────────
# Test 2: Ranker scoring prompt
# ─────────────────────────────────────────────────────────────────────────
RANKER_SYSTEM = "You are a scientific hypothesis evaluator. Output only numbers, no explanation."

RANKER_PROMPT = """Score this hypothesis on three dimensions. Reply with exactly three lines:
Novelty: <0.0-1.0>
Evidence: <0.0-1.0>
Feasibility: <0.0-1.0>

Hypothesis: Bakuchiol activates AMPK-mediated autophagy in keratinocytes, resulting in increased removal of damaged mitochondria and subsequent restoration of skin cell homeostasis and function.

Critique summary: The hypothesis is plausible given the role of autophagy and AMPK in cellular homeostasis and mitochondrial function. While the connection between bakuchiol and autophagy has been suggested before, the specific link to AMPK-mediated activation needs further investigation.

Papers found: 14

Scoring guide:
- Novelty: 1.0 = completely new idea, 0.0 = textbook knowledge
- Evidence: 1.0 = many strong papers support it, 0.0 = no literature
- Feasibility: 1.0 = testable with standard lab methods, 0.0 = untestable
"""

# ─────────────────────────────────────────────────────────────────────────
# Test 3: Critic relevance scorer prompt
# ─────────────────────────────────────────────────────────────────────────
RELEVANCE_SYSTEM = (
    "You are a scientific literature relevance assessor. Judge whether each "
    "paper's findings provide real evidence -- direct OR mechanistic -- for the "
    "hypothesis. A paper need not mention the specific compound by name to be "
    "relevant; a paper about the same biological mechanism in a different "
    "context can still count as supporting evidence. Output only what is asked."
)

RELEVANCE_PROMPT = """Hypothesis: Bakuchiol inhibits the activity of matrix metalloproteinases (MMPs) involved in dermal collagen degradation, thereby reducing wrinkles and skin elasticity.

For each paper below, rate how relevant its findings are as evidence for this
specific hypothesis, from 0.0 to 1.0:
- 1.0 = directly tests or supports this exact mechanism/claim
- 0.6-0.9 = relevant mechanism evidence, even if about a different compound, cell type, or context
- 0.2-0.5 = tangentially related (shares a general topic but not the specific mechanism)
- 0.0-0.1 = unrelated to this hypothesis

Papers:
0. Collagen Fragmentation Promotes Oxidative Stress and Elevates Matrix Metalloproteinase-1 in Fibroblasts in Aged Human Skin
   Shows MMP-1 elevation directly causes collagen fragmentation in aged skin fibroblasts.
1. LASER and Radiofrequency for Treatment of Vaginal Vulvar Atrophy in Women Treated for Breast Cancer
   A clinical trial on laser/RF treatment for vaginal atrophy post breast cancer treatment.
2. Vitamin A Antagonizes Decreased Cell Growth and Elevated Collagen-Degrading Matrix Metalloproteinases in Aged Human Skin
   Vitamin A reduces MMP activity and restores collagen accumulation in aged skin.
3. A natural and cultural history of femicide
   A sociological and historical analysis of femicide patterns across cultures.

Respond with ONLY a JSON array of 4 objects, in this exact order matching the
papers above, in this exact shape:
[
  {{"index": 0, "relevance": 0.8}},
  {{"index": 1, "relevance": 0.2}}
]

Do not include any text before or after the JSON array.
"""


def try_parse_json_array(raw: str):
    """Loose check: did the model produce a valid, parseable JSON array?"""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        return isinstance(data, list), data
    except Exception:
        return False, None


def check_novelty_spelling(raw: str) -> str:
    if re.search(r"\bnovelty\b", raw, re.IGNORECASE):
        return "correct ('Novelty')"
    elif re.search(r"\bnov\w*\b", raw, re.IGNORECASE):
        misspelling = re.search(r"\bnov\w*\b", raw, re.IGNORECASE).group(0)
        return f"MISSPELLED ('{misspelling}')"
    else:
        return "MISSING entirely"


def run_test(llm, label, system, prompt, check_fn):
    start = time.time()
    try:
        raw = llm.complete(prompt, system=system, temperature=0.1)
    except Exception as e:
        elapsed = time.time() - start
        print(f"  [{label}] ERROR: {e}  ({elapsed:.1f}s)")
        return
    elapsed = time.time() - start
    result = check_fn(raw)
    print(f"  [{label}] {result}  ({elapsed:.1f}s)")
    print(f"      raw (first 300 chars): {raw[:300]!r}")


def main():
    base_config = ResearchConfig()
    base_config.validate()

    for model_name in MODELS_TO_TEST:
        print(f"\n{'='*70}")
        print(f"MODEL: {model_name}")
        print(f"{'='*70}")

        config = ResearchConfig()
        config.llm_backend  = "ollama"
        config.ollama_model = model_name
        llm = LLMClient(config)

        print("\n--- Test 1: Gap Detector JSON ---")
        def check_gaps(raw):
            ok, data = try_parse_json_array(raw)
            if not ok:
                return "FAILED to parse as JSON array"
            if len(data) != 3:
                return f"parsed OK but got {len(data)} items (expected 3)"
            has_keys = all(
                isinstance(d, dict) and "gap" in d and "priority" in d
                for d in data
            )
            return "VALID JSON, correct shape" if has_keys else "parsed but missing expected keys"
        run_test(llm, "gap_detector", GAP_SYSTEM, GAP_PROMPT, check_gaps)

        print("\n--- Test 2: Ranker scoring (Novelty spelling) ---")
        run_test(llm, "ranker", RANKER_SYSTEM, RANKER_PROMPT, check_novelty_spelling)

        print("\n--- Test 3: Critic relevance scorer JSON ---")
        def check_relevance(raw):
            ok, data = try_parse_json_array(raw)
            if not ok:
                return "FAILED to parse as JSON array"
            if len(data) != 4:
                return f"parsed OK but got {len(data)} items (expected 4)"
            try:
                scores = {d["index"]: d["relevance"] for d in data}
                # Sanity: paper 0 and 2 (real MMP/collagen papers) should
                # score higher than paper 1 (vaginal atrophy) and paper 3
                # (femicide) which are unrelated.
                relevant_avg   = (scores.get(0, 0) + scores.get(2, 0)) / 2
                irrelevant_avg = (scores.get(1, 0) + scores.get(3, 0)) / 2
                sane = relevant_avg > irrelevant_avg
                return (f"VALID JSON, relevant_avg={relevant_avg:.2f} "
                        f"irrelevant_avg={irrelevant_avg:.2f} "
                        f"({'SANE' if sane else 'NOT SANE — irrelevant scored higher!'})")
            except Exception as e:
                return f"parsed but couldn't extract scores: {e}"
        run_test(llm, "critic_relevance", RELEVANCE_SYSTEM, RELEVANCE_PROMPT, check_relevance)

    print(f"\n{'='*70}")
    print("DONE")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
