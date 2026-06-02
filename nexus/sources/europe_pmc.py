from nexus.sources._query_utils import clean_query

URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

async def fetch(client, query: str, n: int) -> list:
    q = clean_query(query)
    try:
        resp = await client.get(URL, params={
            "query"     : q,
            "format"    : "json",
            "pageSize"  : n,
            "resultType": "core"
        }, timeout=15)
        resp.raise_for_status()
        results = resp.json().get("resultList", {}).get("result", [])
        papers  = []
        for r in results:
            title    = r.get("title", "")
            abstract = r.get("abstractText", "") or ""
            pmid     = r.get("pmid", r.get("id", "epmc_unknown"))
            if title:
                papers.append({
                    "pmid"    : str(pmid),
                    "title"   : title,
                    "abstract": abstract,
                    "source"  : "europe_pmc",
                    "relevance": 0.65
                })
        return papers
    except Exception as e:
        print(f"        [europe_pmc error] {e}")
        return []
