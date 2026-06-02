from nexus.sources._query_utils import short_query

URL = "https://clinicaltrials.gov/api/v2/studies"

async def fetch(client, query: str, n: int) -> list:
    q = short_query(query, n_words=5)
    try:
        resp = await client.get(URL, params={
            "query.term": q,
            "pageSize"  : n,
            "format"    : "json"
        }, timeout=15)
        resp.raise_for_status()
        studies = resp.json().get("studies", [])
        papers  = []
        for s in studies:
            proto    = s.get("protocolSection", {})
            id_mod   = proto.get("identificationModule", {})
            desc_mod = proto.get("descriptionModule", {})
            title    = id_mod.get("briefTitle", "")
            abstract = desc_mod.get("briefSummary", "") or ""
            nct_id   = id_mod.get("nctId", "ct_unknown")
            if title:
                papers.append({
                    "pmid"    : nct_id,
                    "title"   : title,
                    "abstract": abstract,
                    "source"  : "clinical_trials",
                    "relevance": 0.6
                })
        return papers
    except Exception as e:
        print(f"        [clinical_trials error] {e}")
        return []
