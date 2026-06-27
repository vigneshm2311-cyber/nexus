import uuid
import asyncio
import re
import httpx
from nexus.agents.base import BaseAgent
from nexus.db import insert_paper, get_papers_for_hypothesis
from nexus.sources import pubmed, europe_pmc
from nexus.sources import clinical_trials, biorxiv, openalex, uniprot
from nexus.sources._query_utils import clean_query

ENTITY_SYSTEM = "You are a biomedical search query builder. Output only what is asked."

# Rewritten to explicitly cap term count and prioritize the core subject
# first. Root cause this fixes: longer queries (6+ terms) were being
# treated as implicit-AND by PubMed/OpenAlex/Europe PMC, requiring near-
# total term overlap in a single paper — measured empirically to return
# ZERO results at 7-8 terms, vs 4-5 results at 3-4 terms, for the same
# underlying hypothesis. Fewer, better-prioritized terms fixes this at
# the source, rather than trying to rank/filter a result set that was
# never populated in the first place.
ENTITY_PROMPT = """Extract the 3-4 best searchable terms from this hypothesis, in
priority order — most essential term first.

Term 1 MUST be the core compound, drug, gene, or subject name the hypothesis is
actually about (e.g. "Bakuchiol", "BRCA1").

Terms 2-4 should be the most specific mechanism, pathway, protein, or process
terms — pick the ones most likely to appear in a real paper's title or
abstract together with term 1. Prefer fewer, more specific terms over many
broad ones; a search engine treats multiple words as requiring ALL of them
to match, so extra terms make the search stricter, not better.

Exclude: verbs, adjectives, connective words, and any term that's just a
restatement of another term already chosen.

Hypothesis: {hypothesis}

Output: a single line of 3-4 comma-separated terms only, most essential first.
No explanation.
Example output: BRCA1, homologous recombination, breast cancer
"""

MIN_RELEVANCE = 0.15

# Hard ceiling on terms actually used to build the search string, even if
# the LLM ignores the "3-4 terms" instruction and returns more. Measured
# empirically: 4 terms reliably returns 4-5 results per source; 6+ terms
# reliably returns 0.
MAX_QUERY_TERMS = 4


def _cap_to_word_count(query: str, max_words: int) -> str:
    """Caps a query string to at most max_words actual words — not
    comma-separated phrase groups. This matters because the LLM may
    return something like 'Bakuchiol, ERbeta activation, collagen
    expression' — 3 comma groups, but 5 actual words once joined. Search
    APIs treat unstructured terms as implicit AND over every word, so
    word count (not phrase count) is what determines result count."""
    words = query.split()
    return " ".join(words[:max_words])


def _build_query(hypothesis_text: str, llm) -> str:
    try:
        prompt = ENTITY_PROMPT.format(hypothesis=hypothesis_text)
        raw    = llm.complete(prompt, system=ENTITY_SYSTEM, temperature=0.1)
        terms  = [t.strip() for t in raw.split(",") if len(t.strip()) > 2]
        if terms:
            # Join all extracted phrase-groups first, THEN cap by actual
            # word count — a 2-word phrase like "ERbeta activation"
            # counts as 2 words against the cap, not 1.
            query = " ".join(terms)
            query = clean_query(query)
            return _cap_to_word_count(query, MAX_QUERY_TERMS)
    except Exception:
        pass
    # Fallback: same as before, but also capped at MAX_QUERY_TERMS instead
    # of the old hardcoded 6 — keeps the fallback consistent with the same
    # fix even if the LLM call fails entirely.
    words = hypothesis_text.split()
    core  = [w.strip(".,;:()") for w in words if len(w) > 5][:MAX_QUERY_TERMS]
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


def _query_terms(query: str) -> list:
    return [t.lower() for t in re.split(r"\s+", query.strip()) if len(t) > 2]


def _score_relevance(query: str, title: str, abstract: str) -> float:
    terms = _query_terms(query)
    if not terms:
        return MIN_RELEVANCE

    title_lower    = (title or "").lower()
    abstract_lower = (abstract or "").lower()

    matched_weight = 0.0
    for term in terms:
        in_title    = term in title_lower
        in_abstract = term in abstract_lower
        if in_title:
            matched_weight += 1.0
        elif in_abstract:
            matched_weight += 0.5

    max_weight = len(terms) * 1.0
    raw_score  = matched_weight / max_weight if max_weight else 0.0

    return round(max(MIN_RELEVANCE, min(1.0, raw_score)), 4)


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

    for p in papers:
        p["relevance"] = _score_relevance(query, p.get("title", ""), p.get("abstract", ""))

    return _dedup(papers)


async def _fetch_for_query_with_widening(client: httpx.AsyncClient, query: str, n: int) -> list:
    """If the (already-shortened) query still returns nothing from every
    source, retries once with just the first 2 terms — the core subject
    plus its single most important mechanism term. This is a safety net
    for hypotheses with unusually rare/specific terminology, on top of
    the main fix (shorter queries from the start)."""
    papers = await _fetch_for_query(client, query, n)
    if papers:
        return papers

    terms = _query_terms(query)
    if len(terms) <= 2:
        return papers  # already as narrow as we go; nothing more to try

    widened_query = " ".join(terms[:2])
    print(f"        [fetcher] 0 results for full query, retrying narrower: {widened_query}")
    return await _fetch_for_query(client, widened_query, n)


async def _fetch_all_hypotheses(queries: list, n: int) -> list:
    async with httpx.AsyncClient() as client:
        results = []
        for q in queries:
            result = await _fetch_for_query_with_widening(client, q, n)
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
                    p["source"], p.get("relevance", MIN_RELEVANCE)
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
