from nexus.sources._query_utils import clean_query

URL = "https://api.openalex.org/works"

async def fetch(client, query: str, n: int) -> list:
    q = clean_query(query)
    try:
        resp = await client.get(URL, params={
            "search"  : q,
            "per-page": n,
            "mailto"  : "nexus@amura.ai"
        }, timeout=15)
        resp.raise_for_status()
        papers = []
        for item in resp.json().get("results", []):
            title    = item.get("title", "") or ""
            abstract = _reconstruct_abstract(
                item.get("abstract_inverted_index", {})
            )
            oa_id = item.get("id", "oa_unknown").replace(
                "https://openalex.org/", ""
            )
            if title:
                papers.append({
                    "pmid"    : oa_id,
                    "title"   : title,
                    "abstract": abstract,
                    "source"  : "openalex",
                    "relevance": 0.6
                })
        return papers
    except Exception as e:
        print(f"        [openalex error] {e}")
        return []

def _reconstruct_abstract(inverted_index: dict) -> str:
    if not inverted_index:
        return ""
    try:
        words = {}
        for word, positions in inverted_index.items():
            for pos in positions:
                words[pos] = word
        return " ".join(words[i] for i in sorted(words.keys()))
    except Exception:
        return ""
