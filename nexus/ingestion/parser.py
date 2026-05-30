import re

DOMAIN_KEYWORDS = {
    "oncology": ["cancer", "tumor", "oncology", "carcinoma", "metastasis"],
    "cardiology": ["heart", "cardiac", "cardiovascular", "myocardial", "arrhythmia"],
    "neurology": ["brain", "neural", "neuron", "cognitive", "alzheimer", "parkinson"],
    "immunology": ["immune", "immunology", "antibody", "cytokine", "inflammation"],
    "microbiology": ["bacteria", "virus", "pathogen", "infection", "antimicrobial"],
    "genomics": ["gene", "genome", "dna", "rna", "mutation", "snp", "sequencing"],
    "pharmacology": ["drug", "therapy", "treatment", "pharmacology", "clinical trial"],
}

def parse_goal(goal: str) -> dict:
    goal_lower = goal.lower()
    words = re.findall(r'\b\w+\b', goal_lower)

    domain = _detect_domain(goal_lower)
    depth = _detect_depth(goal_lower)
    keywords = _extract_keywords(words)

    return {
        "goal": goal.strip(),
        "domain": domain,
        "depth": depth,
        "keywords": keywords,
    }

def _detect_domain(text: str) -> str:
    scores = {}
    for domain, terms in DOMAIN_KEYWORDS.items():
        scores[domain] = sum(1 for t in terms if t in text)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"

def _detect_depth(text: str) -> str:
    if any(w in text for w in ["mechanism", "pathway", "molecular", "underlying"]):
        return "deep"
    if any(w in text for w in ["overview", "review", "survey", "introduction"]):
        return "broad"
    return "standard"

def _extract_keywords(words: list) -> list:
    stopwords = {
        "the", "a", "an", "and", "or", "of", "in", "on", "at", "to",
        "for", "with", "is", "are", "was", "were", "be", "been", "what",
        "how", "why", "does", "do", "can", "role", "effect", "impact"
    }
    seen = set()
    keywords = []
    for w in words:
        if w not in stopwords and len(w) > 3 and w not in seen:
            seen.add(w)
            keywords.append(w)
    return keywords[:10]
