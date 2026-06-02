import xml.etree.ElementTree as ET
from nexus.sources._query_utils import clean_query

SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
FETCH_URL  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

async def fetch(client, query: str, n: int) -> list:
    q = clean_query(query)
    try:
        search = await client.get(SEARCH_URL, params={
            "db": "pubmed", "term": q,
            "retmax": n, "retmode": "json"
        }, timeout=15)
        search.raise_for_status()
        ids = search.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []
        fetch = await client.get(FETCH_URL, params={
            "db": "pubmed", "id": ",".join(ids),
            "retmode": "xml", "rettype": "abstract"
        }, timeout=15)
        fetch.raise_for_status()
        return _parse(fetch.text)
    except Exception as e:
        print(f"        [pubmed error] {e}")
        return []

def _parse(xml_text: str) -> list:
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
                    "source": "pubmed", "relevance": 0.7
                })
    except ET.ParseError as e:
        print(f"        [pubmed xml error] {e}")
    return papers
