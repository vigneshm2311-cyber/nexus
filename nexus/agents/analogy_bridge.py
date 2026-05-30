import uuid
import time
import re
import requests
import xml.etree.ElementTree as ET
from nexus.agents.base import BaseAgent
from nexus.db import insert_paper

PUBMED_SEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
SEMANTIC_URL  = "https://api.semanticscholar.org/graph/v1/paper/search"

ADJACENT_FIELDS = [
    "materials science",
    "evolutionary biology",
    "neuroscience",
    "physics",
    "computer science",
    "immunology",
    "developmental biology",
]

SYSTEM = "You are a cross-disciplinary scientist who finds structural analogies between fields."

MECHANISM_PROMPT = """Read this hypothesis and extract the core biological mechanism in 1 sentence.
Focus on: what fails, what cascade it triggers, what outcome results.

Hypothesis: {hypothesis}

Output: one sentence describing the core mechanism only. No preamble.
"""

ANALOGY_PROMPT = """Core mechanism in {domain}: {mechanism}

Adjacent fields to draw from: {fields}

For each of 3 adjacent fields, find a structurally similar mechanism and explain
how it could inspire a new hypothesis about: {goal}

Output exactly 3 blocks in this format (no markdown bold, no --- separators):
Field: <field name>
Analogy: <mechanism in that field that mirrors the core mechanism>
New hypothesis: <one testable sentence applying this analogy to the research goal>

Field: <field name>
Analogy: <mechanism in that field>
New hypothesis: <one testable sentence>

Field: <field name>
Analogy: <mechanism in that field>
New hypothesis: <one testable sentence>
"""

SEARCH_PROMPT = """Given this research goal and adjacent field, write a 5-word PubMed search query
that bridges both fields. Output only the query, no explanation.

Research goal: {goal}
Adjacent field: {field}
Core mechanism: {mechanism}
"""

class AnalogyBridgeAgent(BaseAgent):
    name = "analogy_bridge"

    def execute(self, session_id: str, round_num: int, context: dict) -> dict:
        ranked = context["ranked"]
        goal   = context["goal"]
        domain = context["domain"]

        if not ranked:
            return {"analogies": [], "_summary": "No hypotheses to bridge"}

        top       = ranked[0]
        mechanism = self._extract_mechanism(top["hypothesis_text"])
        print(f"        Core mechanism: {mechanism[:80]}")

        raw = self.llm.complete(
            ANALOGY_PROMPT.format(
                domain=domain,
                mechanism=mechanism,
                fields=", ".join(ADJACENT_FIELDS[:5]),
                goal=goal,
            ),
            system=SYSTEM
        )

        analogies = _parse_analogies(raw)
        print(f"        Parsed {len(analogies)} analogies")
        papers = []

        for ana in analogies:
            field = ana.get("field", "")
            query = self.llm.complete(
                SEARCH_PROMPT.format(
                    goal=goal, field=field, mechanism=mechanism
                ),
                system="Output only the search query, nothing else."
            ).strip()
            print(f"        Analogy search [{field}]: {query}")

            fetched = _fetch_pubmed(query, n=2)
            if not fetched:
                fetched = _fetch_semantic_safe(query, n=2)

            for p in fetched:
                p_id       = str(uuid.uuid4())
                dummy_h_id = str(uuid.uuid4())
                insert_paper(
                    self.conn, p_id, dummy_h_id, session_id,
                    p["pmid"], p["title"], p["abstract"],
                    f"analogy:{field}", 0.4
                )
                papers.append({**p, "field": field})

            ana["papers"] = [p["title"] for p in fetched]

        return {
            "mechanism" : mechanism,
            "analogies" : analogies,
            "analogy_papers": papers,
            "_summary"  : f"Found {len(analogies)} analogies across adjacent fields"
        }

    def _extract_mechanism(self, hypothesis_text: str) -> str:
        raw = self.llm.complete(
            MECHANISM_PROMPT.format(hypothesis=hypothesis_text),
            system=SYSTEM
        )
        return raw.strip()

def _clean_label(text: str) -> str:
    return re.sub(r"[*_`#]", "", text).strip()

def _parse_analogies(raw: str) -> list:
    analogies  = []
    current    = {}
    key_map    = {
        "field"         : "field",
        "analogy"       : "analogy",
        "new hypothesis": "new_hypothesis",
    }

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            if len(current) == 3:
                analogies.append(current)
                current = {}
            continue

        cleaned = _clean_label(line)
        matched = False
        for prefix, key in key_map.items():
            pattern = re.compile(rf"^{prefix}\s*:", re.IGNORECASE)
            if pattern.match(cleaned):
                value = pattern.sub("", cleaned).strip()
                current[key] = value
                matched = True
                break

        if not matched and current:
            last_key = list(current.keys())[-1]
            current[last_key] += " " + cleaned

    if len(current) == 3:
        analogies.append(current)

    return analogies

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
        print(f"        [pubmed error] {e}")
        return []

def _fetch_semantic_safe(query: str, n: int, retries: int = 3) -> list:
    for attempt in range(retries):
        try:
            resp = requests.get(SEMANTIC_URL, params={
                "query": query, "limit": n,
                "fields": "title,abstract,externalIds"
            }, timeout=10)
            if resp.status_code == 429:
                wait = 2 ** attempt
                print(f"        [semantic 429] retrying in {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            papers = []
            for item in resp.json().get("data", []):
                pmid     = item.get("externalIds", {}).get("PubMed", f"ss_{item.get('paperId','')}")
                title    = item.get("title", "")
                abstract = item.get("abstract", "") or ""
                if title:
                    papers.append({
                        "pmid": str(pmid), "title": title,
                        "abstract": abstract, "source": "semantic_scholar"
                    })
            return papers
        except Exception as e:
            print(f"        [semantic error] {e}")
            return []
    return []

def _parse_pubmed_xml(xml_text: str) -> list:
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
                    "abstract": abstract or "", "source": "pubmed"
                })
    except ET.ParseError:
        pass
    return papers
