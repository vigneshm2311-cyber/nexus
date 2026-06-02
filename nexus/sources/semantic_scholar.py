import asyncio

URL = "https://api.semanticscholar.org/graph/v1/paper/search"

async def fetch(client, query: str, n: int, semaphore: asyncio.Semaphore) -> list:
    async with semaphore:
        await asyncio.sleep(2.0)
        try:
            resp = await client.get(URL, params={
                "query": query, "limit": n,
                "fields": "title,abstract,externalIds"
            }, timeout=15)
            if resp.status_code == 429:
                print(f"        [semantic scholar 429 — skipping]")
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
                        "pmid"    : str(pmid),
                        "title"   : title,
                        "abstract": abstract,
                        "source"  : "semantic_scholar",
                        "relevance": 0.6
                    })
            return papers
        except Exception as e:
            print(f"        [semantic scholar error] {e}")
            return []
