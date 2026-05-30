import uuid
import asyncio
import httpx
import xml.etree.ElementTree as ET
from nexus.agents.base import BaseAgent
from nexus.db import insert_paper, get_papers_for_hypothesis

PUBMED_SEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
SEMANTIC_URL  = "https://api.semanticscholar.org/graph/v1/paper/search"

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
            return " ".join(terms[:6])
    except Exception:
        pass
    words = hypothesis_text.split()
    core  = [w.strip(".,;:()") for w in words if len(w) > 5][:6]
    return " ".join(core)

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

async def _fetch_pubmed(client: httpx.AsyncClient, query: str, n: int) -> list:
    try:
        search = await client.get(PUBMED_SEARCH, params={
            "db": "pubmed", "term": query,
            "retmax": n, "retmode": "json"
        }, timeout=15)
        search.raise_for_status()
        ids = search.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []
        fetch = await client.get(PUBMED_FETCH, params={
            "db": "pubmed", "id": ",".join(ids),
            "retmode": "xml", "rettype": "abstract"
        }, timeout=15)
        fetch.raise_for_status()
        return _parse_pubmed_xml(fetch.text)
    except Exception as e:
        print(f"        [pubmed error] {e}")
        return []

async def _fetch_semantic(
    client: httpx.AsyncClient,
    query: str,
    n: int,
    semaphore: asyncio.Semaphore
) -> list:
    async with semaphore:
        await asyncio.sleep(0.5)
        try:
            resp = await client.get(SEMANTIC_URL, params={
                "query": query, "limit": n,
                "fields": "title,abstract,externalIds"
            }, timeout=15)
            if resp.status_code == 429:
                print(f"        [semantic 429 — skipping]")
                return []
            resp.raise_for_status()
            papers = []
            for item in resp.json().get("data", []):
                pmid     = item.get("externalIds", {}).get(
                    "PubMed", f"ss_{item.get('paperId','')}"
                )
                title    = item.get("title", "")
                abstract = item.get("abstract", "") or ""
                if title:
                    papers.append({
                        "pmid": str(pmid), "title": title,
                        "abstract": abstract,
                        "source": "semantic_scholar", "relevance": 0.5
                    })
            return papers
        except Exception as e:
            print(f"        [semantic error] {e}")
            return []

async def _fetch_hypothesis(
    client: httpx.AsyncClient,
    query: str,
    n: int,
    semaphore: asyncio.Semaphore
) -> list:
    papers = await _fetch_pubmed(client, query, n)
    if len(papers) < n:
        extra  = await _fetch_semantic(client, query, n - len(papers), semaphore)
        papers = _dedup(papers + extra)
    return papers

async def _fetch_all(queries: list, n: int) -> list:
    semaphore = asyncio.Semaphore(1)
    async with httpx.AsyncClient() as client:
        tasks   = [
            _fetch_hypothesis(client, q, n, semaphore)
            for q in queries
        ]
        results = await asyncio.gather(*tasks)
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
            loop    = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            fetched = loop.run_until_complete(_fetch_all(active, self.config.papers_per_hypothesis))
            loop.close()
            asyncio.set_event_loop(None)
        else:
            fetched = []

        fetched_iter = iter(fetched)
        all_papers   = []

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

        return {
            "papers"  : all_papers,
            "_summary": f"Fetched {len(all_papers)} papers for "
                        f"{len(hypotheses)} hypotheses (async)"
        }

def _parse_pubmed_xml(xml_text: str) -> list:
    papers = []
    try:
        root = ET.fromstring(xml_text)
        for article in root.findall(".//PubmedArticle"):
            pmid_el     = article.find(".//PMID")
            title_el    = article.find(".//ArticleTitle")
            abstract_el = article.find(".//AbstractText")
            pmid     = pmid_el.text     if pmid_el     is not None else "unknown"
            title    = title_el.text    if title_el    is not None else ""
            abstract = abstract_el.text if abstract_el is not None else ""
            if title:
                papers.append({
                    "pmid": pmid, "title": title,
                    "abstract": abstract or "",
                    "source": "pubmed", "relevance": 0.6
                })
    except ET.ParseError as e:
        print(f"        [xml error] {e}")
    return papers
