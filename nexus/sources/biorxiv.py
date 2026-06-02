from datetime import datetime, timedelta
from nexus.sources._query_utils import clean_query

BIORXIV_URL = "https://api.biorxiv.org/details/biorxiv/{start}/{end}/0/json"
MEDRXIV_URL = "https://api.biorxiv.org/details/medrxiv/{start}/{end}/0/json"

def _keyword_match(text: str, keywords: list) -> bool:
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)

async def fetch(client, query: str, n: int) -> list:
    q        = clean_query(query)
    keywords = q.split()
    end      = datetime.now().strftime("%Y-%m-%d")
    start    = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")

    papers = []
    for url_template in [MEDRXIV_URL, BIORXIV_URL]:
        if len(papers) >= n:
            break
        try:
            url  = url_template.format(start=start, end=end)
            resp = await client.get(url, timeout=15)
            resp.raise_for_status()
            for item in resp.json().get("collection", []):
                title    = item.get("title", "")
                abstract = item.get("abstract", "") or ""
                if _keyword_match(title + " " + abstract, keywords):
                    server = item.get("server", "biorxiv")
                    papers.append({
                        "pmid"    : f"{server}_{item.get('doi','').replace('/','_')}",
                        "title"   : title,
                        "abstract": abstract,
                        "source"  : server,
                        "relevance": 0.55
                    })
                if len(papers) >= n:
                    break
        except Exception as e:
            print(f"        [biorxiv error] {e}")

    return papers[:n]
