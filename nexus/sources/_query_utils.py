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
    # Substitute each Greek letter with a SPACED English word, not a
    # fused concatenation. Root cause this fixes: "ERβ" was becoming
    # "ERbeta" (one fused word) — a literal string that essentially
    # never appears in real paper titles/abstracts, since researchers
    # write "ERβ", "ER-β", or "estrogen receptor beta" with the Greek
    # letter or spelled-out word kept separate from the preceding
    # abbreviation. Measured empirically: a query containing "ERbeta"
    # returned 0 results from PubMed/Europe PMC/OpenAlex; replacing it
    # with the same concept spaced out recovered 5 results from each.
    # Example: "NF-κB" -> "NF- kappa B" -> (after whitespace cleanup)
    # "NF- kappa B", "ERβ" -> "ER beta".
    for greek, english in GREEK_MAP.items():
        query = query.replace(greek, f' {english} ')

    query = re.sub(r'[^\x00-\x7F]+', ' ', query)
    query = re.sub(r'\s+', ' ', query).strip()
    return query


def short_query(query: str, n_words: int = 5) -> str:
    return " ".join(clean_query(query).split()[:n_words])
