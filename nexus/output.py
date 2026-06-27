import os
import json
from datetime import datetime
from nexus.config import ResearchConfig
from nexus.db import get_conn, get_papers_for_hypothesis
from nexus.paper_links import build_paper_url


def generate(result: dict, config: ResearchConfig):
    os.makedirs(config.output_dir, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = result["goal"][:40].lower().replace(" ", "_").replace("?", "")
    base = f"{config.output_dir}/{ts}_{slug}"

    md_path   = base + ".md"
    json_path = base + ".json"

    conn = get_conn(config)
    _write_markdown(result, config, conn, md_path)
    _write_json(result, conn, json_path)

    print(f"[NEXUS v3] Report → {md_path}")
    print(f"[NEXUS v3] JSON   → {json_path}")
    return md_path, json_path


def _row_get(row, key, default=""):
    """Safe field access that works for both sqlite3.Row and plain dicts."""
    try:
        value = row[key]
        return value if value is not None else default
    except (IndexError, KeyError):
        return default


def _write_markdown(result: dict, config: ResearchConfig, conn, path: str):
    ranked    = result["ranked"]
    analogies = result.get("analogies", {})
    gaps      = result.get("gaps", {})
    lines     = []

    lines.append(f"# NEXUS v3 Research Report\n")
    lines.append(f"**Goal:** {result['goal']}\n")
    lines.append(f"**Domain:** {result['domain']}")
    lines.append(f"**Keywords:** {', '.join(result['keywords'])}")
    lines.append(f"**Rounds completed:** {result['rounds_completed']}")
    lines.append(f"**Session:** `{result['session_id']}`")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append("---\n")

    lines.append("## Ranked Hypotheses\n")
    for i, h in enumerate(ranked, 1):
        confidence = h.get("confidence", "n/a")
        conf_badge = {"high": "HIGH", "medium": "MEDIUM", "low": "LOW"}.get(confidence, confidence)
        lines.append(f"### {i}. {h['hypothesis_text']}\n")
        lines.append(f"| Metric | Score | Std Dev |")
        lines.append(f"|--------|-------|---------|")
        lines.append(f"| Overall | **{h['score']}** | — |")
        lines.append(f"| Novelty | {h['novelty']} | ±{h.get('std_novelty', 0)} |")
        lines.append(f"| Evidence | {h['evidence']} | ±{h.get('std_evidence', 0)} |")
        lines.append(f"| Feasibility | {h['feasibility']} | ±{h.get('std_feasibility', 0)} |")
        lines.append(f"| Confidence | `{conf_badge}` | — |")
        lines.append("")
        lines.append(f"**Critique:**")
        lines.append(f"> {h['critique'].replace(chr(10), chr(10) + '> ')}\n")

        papers = get_papers_for_hypothesis(conn, h["hypothesis_id"])
        if papers:
            lines.append(f"**Supporting literature ({len(papers)} papers):**")
            for p in papers:
                title  = _row_get(p, "title", "Untitled")
                source = _row_get(p, "source", "")
                pmid   = _row_get(p, "pmid", "")
                url    = build_paper_url(source, pmid)
                if url:
                    lines.append(f"- [{title}]({url}) *(source: {source})*")
                else:
                    lines.append(f"- {title} *(source: {source})*")
        lines.append("\n---\n")

    if analogies.get("analogies"):
        lines.append("## Analogies from Adjacent Fields\n")
        lines.append(f"**Core mechanism:** {analogies.get('mechanism', '')}\n")
        for ana in analogies["analogies"]:
            lines.append(f"### Field: {ana.get('field', '')}\n")
            lines.append(f"**Analogy:** {ana.get('analogy', '')}\n")
            lines.append(f"**Inspired hypothesis:** {ana.get('new_hypothesis', '')}\n")
            if ana.get("papers"):
                lines.append(f"**Related papers:**")
                for p in ana["papers"]:
                    lines.append(f"- {p}")
            lines.append("")
        lines.append("---\n")

    if gaps.get("gaps"):
        lines.append("## Research Gaps\n")
        lines.append("*Unanswered questions identified from hypothesis analysis*\n")
        for i, gap in enumerate(gaps["gaps"], 1):
            priority = gap.get("priority", "medium").upper()
            lines.append(f"### Gap {i} — `{priority}`\n")
            lines.append(f"**Question:** {gap.get('gap', '')}\n")
            lines.append(f"**Why it matters:** {gap.get('why', '')}\n")
            lines.append(f"**Suggested approach:** {gap.get('approach', '')}\n")
        lines.append("---\n")

    lines.append("## Pipeline Summary\n")
    lines.append(
        "Pipeline: Genesis → Fetcher (async) → Critic → "
        "Ranker (3× confidence) → Analogy Bridge → Gap Detector → Evolver"
    )
    lines.append(f"LLM backend: `{config.llm_backend}` / `{config.ollama_model}`\n")

    with open(path, "w") as f:
        f.write("\n".join(lines))


def _write_json(result: dict, conn, path: str):
    analogies = result.get("analogies", {})
    gaps      = result.get("gaps", {})
    ranked    = result["ranked"]

    hypotheses_payload = []
    for i, h in enumerate(ranked):
        papers = get_papers_for_hypothesis(conn, h["hypothesis_id"])
        papers_payload = []
        for p in papers:
            title  = _row_get(p, "title", "")
            source = _row_get(p, "source", "")
            pmid   = _row_get(p, "pmid", "")
            papers_payload.append({
                "title"    : title,
                "source"   : source,
                "pmid"     : pmid,
                "url"      : build_paper_url(source, pmid),
                "relevance": _row_get(p, "relevance", 0.0),
            })

        hypotheses_payload.append({
            "rank"           : i + 1,
            "text"           : h["hypothesis_text"],
            "score"          : h["score"],
            "novelty"        : h["novelty"],
            "evidence"       : h["evidence"],
            "feasibility"    : h["feasibility"],
            "std_novelty"    : h.get("std_novelty", 0),
            "std_evidence"   : h.get("std_evidence", 0),
            "std_feasibility": h.get("std_feasibility", 0),
            "confidence"     : h.get("confidence", "n/a"),
            "critique"       : h["critique"],
            "papers"         : papers_payload,
        })

    payload = {
        "session_id"      : result["session_id"],
        "goal"            : result["goal"],
        "domain"          : result["domain"],
        "keywords"        : result["keywords"],
        "rounds_completed": result["rounds_completed"],
        "generated_at"    : datetime.now().isoformat(),
        "hypotheses"      : hypotheses_payload,
        "analogies": {
            "mechanism": analogies.get("mechanism", ""),
            "items"    : analogies.get("analogies", []),
        },
        "gaps": gaps.get("gaps", []),
    }

    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
