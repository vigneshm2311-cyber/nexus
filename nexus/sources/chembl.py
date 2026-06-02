URL = "https://www.ebi.ac.uk/chembl/api/data/document/search"

def _shorten_query(query: str) -> str:
    terms = query.split()[:3]
    return " ".join(terms)

async def fetch(client, query: str, n: int) -> list:
    short_query = _shorten_query(query)
    try:
        resp = await client.get(URL, params={
            "q"     : short_query,
            "format": "json",
            "limit" : n
        }, timeout=15)
        if resp.status_code == 500:
            print(f"        [chembl 500 — query too complex, skipping]")
            return []
        resp.raise_for_status()
        raw  = resp.json()
        docs = raw.get("documents", [])
        if isinstance(docs, dict):
            docs = docs.get("documents", [])
        papers = []
        for item in docs:
            title    = item.get("title", "") or ""
            abstract = item.get("abstract", "") or ""
            doc_id   = item.get("doc_id", "chembl_unknown")
            if title:
                papers.append({
                    "pmid"    : f"chembl_{doc_id}",
                    "title"   : title,
                    "abstract": abstract,
                    "source"  : "chembl",
                    "relevance": 0.55
                })
        return papers
    except Exception as e:
        print(f"        [chembl error] {e}")
        return []
