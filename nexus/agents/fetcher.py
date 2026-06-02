import uuid
import asyncio
import httpx
from nexus.agents.base import BaseAgent
from nexus.db import insert_paper, get_papers_for_hypothesis
from nexus.sources import pubmed, europe_pmc
from nexus.sources import clinical_trials, biorxiv, openalex, uniprot
from nexus.sources._query_utils import clean_query

ENTITY_SYSTEM = "You are a biomedical search query builder. Output only what is asked."
ENTITY_PROMPT = """Extract the 5-7 most important searchable biological terms from this hypothesis.
Include: gene names, protein names, biological processes, disease names, molecular pathways.
Exclude: verbs, adjectives, connective words.

Hypothesis: {hypothesis}

Output: a single line of comma-separated terms only. No explanation.
Example output: BRCA1, homologous recombination, breast cancer, metastasis, DNA repair
"""

def _build_query(hypothesis_text: str, llm) -> str:
    try:
        prompt = ENTITY_PROMPT.format(hypothesis=hypothesis_text)
        raw    = llm.complete(prompt, system=ENTITY_SYSTEM, temperature=0.1)
        terms  = [t.strip() for t in raw.split(",") if len(t.strip()) > 2]
        if terms:
            query = " ".join(terms[:6])
            return clean_query(query)
    except Exception:
        pass
    words = hypothesis_text.split()
    core  = [w.strip(".,;:()") for w in words if len(w) > 5][:6]
    return clean_query(" ".join(core))

def _title_similarity(t1: str, t2: str) -> float:
    w1 = set(t1.lower().split())
    w2 = set(t2.lower().split())
    if not w1 or not w2:
        return 0.0
    return len(w1 & w2) / len(w1 | w2)

def _dedup(papers: list, threshold: float = 0.6) -> list:
    deduped = []
    for p in papers:
        if not any(_title_similarity(p["title"], k["title"]) >= threshold
                   for k in deduped):
            deduped.append(p)
    return deduped

async def _safe_fetch(name: str, coro) -> list:
    try:
        result = await coro
        return result if isinstance(result, list) else []
    except Exception as e:
        print(f"        [{name} error] {e}")
        return []

async def _fetch_for_query(client: httpx.AsyncClient, query: str, n: int) -> list:
    batches = await asyncio.gather(
        _safe_fetch("pubmed",          pubmed.fetch(client, query, n)),
        _safe_fetch("europe_pmc",      europe_pmc.fetch(client, query, n)),
        _safe_fetch("openalex",        openalex.fetch(client, query, n)),
        _safe_fetch("clinical_trials", clinical_trials.fetch(client, query, n)),
        _safe_fetch("biorxiv",         biorxiv.fetch(client, query, n)),
        _safe_fetch("uniprot",         uniprot.fetch(client, query, n)),
    )
    papers = []
    for batch in batches:
        papers.extend(batch)
    return _dedup(papers)

async def _fetch_all_hypotheses(queries: list, n: int) -> list:
    async with httpx.AsyncClient() as client:
        results = []
        for q in queries:
            result = await _fetch_for_query(client, q, n)
            results.append(result)
    return results

class FetcherAgent(BaseAgent):
    name = "fetcher"

    def execute(self, session_id: str, round_num: int, context: dict) -> dict:
        hypotheses = context["hypotheses"]
        queries    = []
        cached     = {}

        for h in hypotheses:
            existing = get_papers_for_hypothesis(self.conn, h["id"])
            if existing:
                cached[h["id"]] = [dict(p) for p in existing]
                queries.append(None)
            else:
                q = _build_query(h["text"], self.llm)
                print(f"        Query [{h['id'][:8]}]: {q[:65]}")
                queries.append(q)

        active = [q for q in queries if q is not None]
        if active:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            fetched = loop.run_until_complete(
                _fetch_all_hypotheses(active, self.config.papers_per_hypothesis)
            )
            loop.close()
            asyncio.set_event_loop(None)
        else:
            fetched = []

        fetched_iter  = iter(fetched)
        all_papers    = []
        source_counts = {}

        for i, h in enumerate(hypotheses):
            if queries[i] is None:
                all_papers.extend(cached.get(h["id"], []))
                continue

            papers = next(fetched_iter, [])
            seen   = set()
            for p in papers:
                if p["pmid"] in seen:
                    continue
                seen.add(p["pmid"])
                p_id = str(uuid.uuid4())
                insert_paper(
                    self.conn, p_id, h["id"], session_id,
                    p["pmid"], p["title"], p["abstract"],
                    p["source"], p.get("relevance", 0.5)
                )
                all_papers.append({**p, "hypothesis_id": h["id"]})
                source_counts[p["source"]] = source_counts.get(p["source"], 0) + 1

        source_summary = " | ".join(
            f"{k}:{v}" for k, v in sorted(source_counts.items())
        )
        return {
            "papers"  : all_papers,
            "_summary": (
                f"Fetched {len(all_papers)} papers for "
                f"{len(hypotheses)} hypotheses — {source_summary}"
            )
        }
