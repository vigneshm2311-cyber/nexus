# ⬡ NEXUS — Multi-Agent Research Intelligence Platform

A local, privacy-first research intelligence platform that generates, evolves, and ranks scientific hypotheses using a pipeline of specialised AI agents — powered entirely by Ollama (no cloud APIs required).

---

## What It Does

You give NEXUS a research question. It spins up a coordinated pipeline of agents that:

1. Generate novel hypotheses from the question
2. Fetch supporting evidence from 6 scientific literature sources
3. Critique each hypothesis against the evidence
4. Rank hypotheses by novelty, evidence strength, and feasibility
5. Find analogies from adjacent scientific fields
6. Detect gaps in the current literature
7. Evolve the top-ranked hypotheses into refined next-generation ideas

Repeat for N rounds. Output a ranked, critiqued, evidence-backed research report.

---

## Architecture

```
nexus/
├── app.py                        # Flask web server + SSE streaming
├── run.py                        # CLI entry point
├── templates/
│   ├── index.html                # Research goal input form
│   ├── progress.html             # Live agent log (Server-Sent Events)
│   └── results.html              # Ranked hypothesis cards + downloads
├── static/
│   └── style.css                 # Dark theme UI
├── nexus/
│   ├── config.py                 # ResearchConfig dataclass
│   ├── conductor.py              # Orchestrates the full pipeline
│   ├── llm_client.py             # LLM wrapper (Ollama / Grok)
│   ├── database.py               # SQLite session + hypothesis storage
│   ├── output.py                 # Markdown + JSON report generation
│   ├── agents/
│   │   ├── base.py               # BaseAgent with retry logic
│   │   ├── genesis.py            # Hypothesis generation
│   │   ├── fetcher.py            # Async literature fetcher
│   │   ├── critic.py             # Evidence-based critique
│   │   ├── ranker.py             # Multi-dimensional scoring
│   │   ├── evolver.py            # Hypothesis evolution
│   │   ├── analogy_bridge.py     # Cross-domain analogy search
│   │   └── gap_detector.py       # Literature gap detection
│   └── sources/
│       ├── pubmed.py             # PubMed (NCBI Entrez)
│       ├── europe_pmc.py         # Europe PMC
│       ├── openalex.py           # OpenAlex
│       ├── biorxiv.py            # bioRxiv + medRxiv preprints
│       ├── clinical_trials.py    # ClinicalTrials.gov
│       ├── uniprot.py            # UniProt protein database
│       └── _query_utils.py       # Shared query normalisation
└── outputs/                      # Generated reports (markdown + JSON)
```

---

## Agent Pipeline

| # | Agent | Role |
|---|-------|------|
| 1 | **Genesis** | Generates N hypotheses from the research goal using LLM |
| 2 | **Fetcher** | Fetches papers from 6 sources concurrently per hypothesis |
| 3 | **Critic** | Critiques each hypothesis against retrieved evidence |
| 4 | **Ranker** | Scores hypotheses on novelty, evidence, and feasibility |
| 5 | **Analogy Bridge** | Finds cross-domain analogies from adjacent fields |
| 6 | **Gap Detector** | Identifies unexplored areas in the literature |
| 7 | **Evolver** | Evolves top-K hypotheses into refined next-generation ideas |

---

## Literature Sources

| Source | Type | Notes |
|--------|------|-------|
| PubMed | Peer-reviewed journals | NCBI Entrez API |
| Europe PMC | Peer-reviewed + preprints | EBI REST API |
| OpenAlex | Open scholarly graph | Covers 250M+ works |
| bioRxiv / medRxiv | Preprints | Biology + medicine |
| ClinicalTrials.gov | Clinical studies | Trial registry |
| UniProt | Protein/gene data | Biological entity queries |

> Semantic Scholar and ChEMBL were removed due to persistent reliability issues.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM backend | [Ollama](https://ollama.com) (local) — `llama3.2` default |
| Web framework | Flask + Server-Sent Events (SSE) |
| Async fetching | `httpx` + `asyncio` |
| Storage | SQLite |
| Runtime | Python 3.11 |
| UI | Vanilla HTML/CSS (dark theme, no JS framework) |

---

## Versions

### V1 — MVP
- Core 5-agent pipeline (Genesis → Fetcher → Critic → Ranker → Evolver)
- SQLite session management
- LLMClient wrapping Ollama
- Domain detection
- Markdown + JSON output

### V2
- Added AnalogyBridgeAgent and GapDetectorAgent
- Smarter biological entity query building
- Jaccard-similarity deduplication across fetched papers

### V3
- LLM retry logic with exponential backoff
- Async PubMed fetching (httpx + asyncio)
- 3-run confidence intervals with standard deviation
- Confidence badges: high / medium / low
- Flask web UI with live SSE progress log
- Ranked hypothesis cards with metric bars and critique panels
- Markdown + JSON report download from browser

---

## Installation

### Prerequisites
- Python 3.11+
- [Ollama](https://ollama.com) installed and running
- `llama3.2` model pulled

```bash
ollama pull llama3.2
```

### Setup

```bash
git clone https://github.com/vigneshm2311-cyber/nexus.git
cd nexus
pip install -r requirements.txt
```

Create a `.env` file:

```env
LLM_BACKEND=ollama
OLLAMA_MODEL=llama3.2
OLLAMA_BASE_URL=http://localhost:11434
DB_PATH=nexus.db
```

---

## Usage

### Web UI (recommended)

```bash
python3 app.py
```

Open `http://127.0.0.1:8080` in your browser.

- Enter a research goal
- Set rounds, hypotheses per round, papers per hypothesis
- Watch agents run live
- View ranked hypotheses with scores, critiques, and metric bars
- Download the full report as Markdown or JSON

### CLI

```bash
python run.py "Bakuchiol for anti-ageing?" --rounds 3 --hypotheses 5 --papers 5
```

---

## Output

Each run produces two files in `outputs/`:

- `YYYYMMDD_HHMMSS_<slug>.md` — Human-readable ranked report
- `YYYYMMDD_HHMMSS_<slug>.json` — Full structured data for downstream use

---

## Configuration

All settings live in `nexus/config.py` as a `ResearchConfig` dataclass:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `llm_backend` | `ollama` | `ollama` or `grok` |
| `ollama_model` | `llama3.2` | Any model available in Ollama |
| `ollama_base_url` | `http://localhost:11434` | Ollama API endpoint |
| `rounds` | `2` | Number of research rounds |
| `hypotheses_per_round` | `5` | Hypotheses generated per round |
| `papers_per_hypothesis` | `5` | Papers fetched per hypothesis |
| `top_k_evolve` | `2` | Top-K hypotheses evolved each round |
| `preprint_max_days` | `180` | Max age of preprints to include |

---

## Key Design Decisions

- **Local-first**: All LLM inference runs via Ollama — no data leaves your machine
- **Source reliability over breadth**: Flaky sources removed rather than worked around
- **Sequential hypotheses, concurrent sources**: Hypotheses fetched one at a time to avoid API interference; sources within a hypothesis run concurrently
- **Query normalisation at source**: Greek letter substitution (β→beta) and ASCII cleaning at query-build time
- **Asyncio loop scoping**: Semaphore/Lock objects created inside the event loop to avoid cross-round failures

---

## Roadmap

- [ ] arXiv source integration
- [ ] Patent search (USPTO / EPO)
- [ ] FDA regulatory filings
- [ ] Entity extraction + knowledge graph
- [ ] RSS monitoring for real-time literature alerts
- [ ] Healthcare intelligence dashboard

---

## License

MIT
