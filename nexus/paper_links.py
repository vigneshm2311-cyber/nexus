"""
Builds a clickable URL for a paper based on its source and stored ID.

Each source stores IDs differently — some are direct, usable identifiers
(PubMed IDs, NCT trial IDs, OpenAlex IDs), others need unwrapping back into
a real link (UniProt's "uniprot_P12345" prefix, bioRxiv/medRxiv's mangled
"biorxiv_10.1101_..." DOI string). This is the single place that knows how
to turn any source's stored pmid value back into a real, clickable URL.
"""
import re


def build_paper_url(source: str, pmid: str) -> str:
    if not pmid:
        return ""

    pmid = str(pmid)

    if source == "pubmed":
        return f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

    if source == "europe_pmc":
        # Europe PMC IDs are usually PubMed-compatible numeric IDs; this
        # URL pattern works for the common MED (PubMed-sourced) case.
        return f"https://europepmc.org/article/MED/{pmid}"

    if source == "openalex":
        # openalex.py already strips the "https://openalex.org/" prefix
        # before storing, so pmid here is just the bare ID (e.g. "W123...").
        return f"https://openalex.org/{pmid}"

    if source == "clinical_trials":
        # clinical_trials.py stores the real NCT ID directly.
        return f"https://clinicaltrials.gov/study/{pmid}"

    if source == "uniprot":
        # uniprot.py stores "uniprot_{accession}" — strip the prefix.
        accession = pmid.replace("uniprot_", "", 1)
        return f"https://www.uniprot.org/uniprotkb/{accession}"

    if source in ("biorxiv", "medrxiv"):
        # biorxiv.py stores "{server}_{doi-with-slashes-replaced-by-underscores}"
        # e.g. "biorxiv_10.1101_2024.01.01.123456". Reconstruct the DOI by
        # stripping the server prefix and putting the first underscore back
        # as a slash (DOIs are "prefix/suffix", e.g. "10.1101/2024.01.01...").
        doi_mangled = re.sub(rf"^{source}_", "", pmid)
        # First underscore back to slash (10.1101_X -> 10.1101/X); any
        # further underscores in the suffix are usually literal in bioRxiv
        # DOIs, so only the first one needs restoring.
        doi = doi_mangled.replace("_", "/", 1)
        return f"https://doi.org/{doi}"

    # Unknown source — no safe URL format known, return nothing rather
    # than guessing and producing a broken link.
    return ""
