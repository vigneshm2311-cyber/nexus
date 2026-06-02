import re

# Greek letter map for biomedical terms
GREEK_MAP = {
    'α': 'alpha', 'β': 'beta',  'γ': 'gamma', 'δ': 'delta',
    'ε': 'epsilon','ζ': 'zeta', 'η': 'eta',   'θ': 'theta',
    'κ': 'kappa', 'λ': 'lambda','μ': 'mu',    'ν': 'nu',
    'π': 'pi',    'ρ': 'rho',   'σ': 'sigma', 'τ': 'tau',
    'φ': 'phi',   'χ': 'chi',   'ψ': 'psi',   'ω': 'omega',
    'Α': 'Alpha', 'Β': 'Beta',  'Γ': 'Gamma', 'Δ': 'Delta',
}

def clean_query(query: str) -> str:
    for greek, english in GREEK_MAP.items():
        query = query.replace(greek, english)
    query = re.sub(r'[^\x00-\x7F]+', ' ', query)
    query = re.sub(r'\s+', ' ', query).strip()
    return query

def short_query(query: str, n_words: int = 5) -> str:
    return " ".join(clean_query(query).split()[:n_words])
