import os
import json
from datetime import datetime
from nexus.config import ResearchConfig
from nexus.db import get_conn, get_papers_for_hypothesis

def generate(result: dict, config: ResearchConfig):
    os.makedirs(config.output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = result["goal"][:40].lower().replace(" ", "_").replace("?", "")
    base = f"{config.output_dir}/{ts}_{slug}"

    md_path   = base + ".md"
    json_path = base + ".json"

    conn = get_conn(config)
    _write_markdown(result, config, conn, md_path)
    _write_json(result, json_path)

    print(f"[NEXUS] Report   → {md_path}")
    print(f"[NEXUS] JSON     → {json_path}")
    return md_path, json_path

def _write_markdown(result: dict, config: ResearchConfig, conn, path: str):
    ranked = result["ranked"]
    lines = []

    lines.append(f"# NEXUS Research Report\n")
    lines.append(f"**Goal:** {result['goal']}\n")
    lines.append(f"**Domain:** {result['domain']}")
    lines.append(f"**Keywords:** {', '.join(result['keywords'])}")
    lines.append(f"**Rounds completed:** {result['rounds_completed']}")
    lines.append(f"**Session:** `{result['session_id']}`")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append("---\n")

    lines.append("## Ranked Hypotheses\n")
    for i, h in enumerate(ranked, 1):
        lines.append(f"### {i}. {h['hypothesis_text']}\n")
        lines.append(f"| Metric | Score |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Overall | **{h['score']}** |")
        lines.append(f"| Novelty | {h['novelty']} |")
        lines.append(f"| Evidence | {h['evidence']} |")
        lines.append(f"| Feasibility | {h['feasibility']} |")
        lines.append("")

        lines.append(f"**Critique:**")
        lines.append(f"> {h['critique'].replace(chr(10), chr(10) + '> ')}\n")

        papers = get_papers_for_hypothesis(conn, h["hypothesis_id"])
        if papers:
            lines.append(f"**Supporting literature ({len(papers)} papers):**")
            for p in papers:
                lines.append(f"- {p['title']} *(source: {p['source']})*")
            lines.append("")

        lines.append("---\n")

    lines.append("## Agent Log Summary\n")
    lines.append(f"Pipeline: Genesis → Fetcher → Critic → Ranker → Evolver")
    lines.append(f"LLM backend: `{config.llm_backend}` / `{config.ollama_model}`\n")

    with open(path, "w") as f:
        f.write("\n".join(lines))

def _write_json(result: dict, path: str):
    payload = {
        "session_id": result["session_id"],
        "goal": result["goal"],
        "domain": result["domain"],
        "keywords": result["keywords"],
        "rounds_completed": result["rounds_completed"],
        "generated_at": datetime.now().isoformat(),
        "hypotheses": [
            {
                "rank": i + 1,
                "text": h["hypothesis_text"],
                "score": h["score"],
                "novelty": h["novelty"],
                "evidence": h["evidence"],
                "feasibility": h["feasibility"],
                "critique": h["critique"],
            }
            for i, h in enumerate(result["ranked"])
        ]
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
