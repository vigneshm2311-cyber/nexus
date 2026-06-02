from nexus.sources._query_utils import clean_query

URL = "https://rest.uniprot.org/uniprotkb/search"

async def fetch(client, query: str, n: int) -> list:
    q = clean_query(query)
    try:
        resp = await client.get(URL, params={
            "query" : q,
            "format": "json",
            "size"  : n
        }, timeout=15)
        resp.raise_for_status()
        papers = []
        for item in resp.json().get("results", []):
            protein_desc = item.get("proteinDescription", {})
            rec_name     = protein_desc.get("recommendedName", {})
            full_name    = rec_name.get("fullName", {}).get("value", "")
            uniprot_id   = item.get("primaryAccession", "up_unknown")
            comments     = item.get("comments", [])
            abstract     = " ".join(
                c.get("texts", [{}])[0].get("value", "")
                for c in comments
                if c.get("commentType") == "FUNCTION"
            )
            if full_name:
                papers.append({
                    "pmid"    : f"uniprot_{uniprot_id}",
                    "title"   : full_name,
                    "abstract": abstract or "",
                    "source"  : "uniprot",
                    "relevance": 0.55
                })
        return papers
    except Exception as e:
        print(f"        [uniprot error] {e}")
        return []
