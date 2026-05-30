import uuid
import requests
import xml.etree.ElementTree as ET
from nexus.agents.base import BaseAgent
from nexus.db import insert_paper, get_papers_for_hypothesis

PUBMED_SEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
SEMANTIC_URL  = "https://api.semanticscholar.org/graph/v1/paper/search"

def _make_query(hypothesis_text: str, keywords: list) -> str:
    words = hypothesis_text.split()
    core = [w.strip(".,;:()") for w in words if len(w) > 5][:6]
    query = " ".join(core) if core else " ".join(keywords[:5])
    return query

class FetcherAgent(BaseAgent):
    name = "fetcher"

    def execute(self, session_id: str, round_num: int, context: dict) -> dict:
        hypotheses = context["hypotheses"]
        keywords = context.get("keywords", [])
        all_papers = []

        for h in hypotheses:
            existing = get_papers_for_hypothesis(self.conn, h["id"])
            if existing:
                all_papers.extend([dict(p) for p in existing])
                continue

            query = _make_query(h["text"], keywords)
            papers = []
            papers += _fetch_pubmed(query, self.config.papers_per_hypothesis)
            if len(papers) < self.config.papers_per_hypothesis:
                papers += _fetch_semantic(query, self.config.papers_per_hypothesis - len(papers))

            seen_pmids = set()
            for p in papers:
                if p["pmid"] in seen_pmids:
                    continue
                seen_pmids.add(p["pmid"])
                p_id = str(uuid.uuid4())
                insert_paper(
                    self.conn, p_id, h["id"], session_id,
                    p["pmid"], p["title"], p["abstract"],
                    p["source"], p.get("relevance", 0.5)
                )
                all_papers.append({**p, "hypothesis_id": h["id"]})

        return {
            "papers": all_papers,
            "_summary": f"Fetched {len(all_papers)} papers for {len(hypotheses)} hypotheses"
        }

def _fetch_pubmed(query: str, n: int) -> list:
    try:
        search = requests.get(PUBMED_SEARCH, params={
            "db": "pubmed", "term": query,
            "retmax": n, "retmode": "json"
        }, timeout=10)
        search.raise_for_status()
        ids = search.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []

        fetch = requests.get(PUBMED_FETCH, params={
            "db": "pubmed", "id": ",".join(ids),
            "retmode": "xml", "rettype": "abstract"
        }, timeout=10)
        fetch.raise_for_status()
        return _parse_pubmed_xml(fetch.text)
    except Exception as e:
        print(f"    [pubmed error] {e}")
        return []

def _parse_pubmed_xml(xml_text: str) -> list:
    papers = []
    try:
        root = ET.fromstring(xml_text)
        for article in root.findall(".//PubmedArticle"):
            pmid_el = article.find(".//PMID")
            title_el = article.find(".//ArticleTitle")
            abstract_el = article.find(".//AbstractText")
            pmid = pmid_el.text if pmid_el is not None else "unknown"
            title = title_el.text if title_el is not None else ""
            abstract = abstract_el.text if abstract_el is not None else ""
            if title:
                papers.append({
                    "pmid": pmid,
                    "title": title,
                    "abstract": abstract or "",
                    "source": "pubmed",
                    "relevance": 0.6
                })
    except ET.ParseError as e:
        print(f"    [xml parse error] {e}")
    return papers

def _fetch_semantic(query: str, n: int) -> list:
    try:
        resp = requests.get(SEMANTIC_URL, params={
            "query": query,
            "limit": n,
            "fields": "title,abstract,externalIds"
        }, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        papers = []
        for item in data:
            pmid = item.get("externalIds", {}).get("PubMed", f"ss_{item.get('paperId','')}")
            title = item.get("title", "")
            abstract = item.get("abstract", "") or ""
            if title:
                papers.append({
                    "pmid": str(pmid),
                    "title": title,
                    "abstract": abstract,
                    "source": "semantic_scholar",
                    "relevance": 0.5
                })
        return papers
    except Exception as e:
        print(f"    [semantic error] {e}")
        return []
