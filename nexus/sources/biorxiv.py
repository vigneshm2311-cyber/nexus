import asyncio
from datetime import datetime, timedelta
from nexus.sources._query_utils import clean_query

BIORXIV_URL = "https://api.biorxiv.org/details/biorxiv/{start}/{end}/0/json"
MEDRXIV_URL = "https://api.biorxiv.org/details/medrxiv/{start}/{end}/0/json"

MAX_RETRIES = 3
RETRY_BASE_DELAY = 1  # seconds; doubles each retry (1s, 2s, 4s)


def _keyword_match(text: str, keywords: list) -> bool:
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


async def _get_with_retry(client, url: str, timeout: int = 15):
    """GET with exponential backoff on 503 (Service Unavailable), which is
    common for this API under load. Other errors are not retried — they're
    raised immediately and handled by the caller's try/except."""
    last_exc = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = await client.get(url, timeout=timeout)
            if resp.status_code == 503:
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_BASE_DELAY * (2 ** attempt)
                    print(f"        [biorxiv 503] retrying in {wait}s...")
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()  # final attempt: let it raise
            resp.raise_for_status()
            return resp
        except Exception as e:
            last_exc = e
            # Only retry loop continues for 503s (handled above); any other
            # exception type falls through and is raised immediately.
            if "503" not in str(e):
                raise
    if last_exc:
        raise last_exc


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
            resp = await _get_with_retry(client, url, timeout=15)
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