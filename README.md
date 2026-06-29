# ⬡ NEXUS — Multi-Agent Research Intelligence Platform

A local, privacy-first research intelligence platform that generates, critiques, ranks, and evolves scientific hypotheses using a pipeline of specialised AI agents — powered entirely by a local LLM through Ollama. No cloud APIs, no API keys, no subscription, no data leaving your machine.

This guide assumes **zero prior coding experience or installed tools**. Every step is spelled out, including for people who have never opened a terminal before.

---

## Table of Contents

1. [What You're Building](#1-what-youre-building)
2. [Part 1 — Installing the Tools You Need](#part-1--installing-the-tools-you-need)
3. [Part 2 — Getting the NEXUS Code](#part-2--getting-the-nexus-code)
4. [Part 3 — Setting Up the Local AI Model](#part-3--setting-up-the-local-ai-model)
5. [Part 4 — Installing NEXUS's Dependencies](#part-4--installing-nexuss-dependencies)
6. [Part 5 — Configuration](#part-5--configuration)
7. [Part 6 — Running NEXUS](#part-6--running-nexus)
8. [Troubleshooting](#troubleshooting)
9. [Architecture Reference](#architecture-reference)
10. [Configuration Reference](#configuration-reference)
11. [Known Limitations & Honest Caveats](#known-limitations--honest-caveats)

---

## 1. What You're Building

NEXUS takes a research question (e.g. *"Bakuchiol for anti-ageing?"*) and runs it through a pipeline of 7 AI agents:

1. **Genesis** — generates several candidate scientific hypotheses
2. **Fetcher** — searches 6 real scientific databases (PubMed, Europe PMC, OpenAlex, ClinicalTrials.gov, bioRxiv, medRxiv) for supporting papers
3. **Critic** — reads the papers' actual abstracts and critically evaluates each hypothesis, explicitly calling out when the evidence doesn't really support the claim
4. **Ranker** — scores hypotheses on novelty, evidence strength, and feasibility, with 3 independent scoring passes per hypothesis for a confidence estimate
5. **Analogy Bridge** — looks for similar mechanisms in unrelated scientific fields (materials science, neuroscience, evolutionary biology) for fresh angles
6. **Gap Detector** — identifies unanswered questions in the field
7. **Evolver** — combines the strongest hypotheses, anchors them to real supporting evidence, and specifically addresses their stated weaknesses to produce stronger versions for the next round

Everything runs **on your own computer**. The AI model runs locally via **Ollama** — nothing is sent to the cloud, and there's no per-use cost.

You can run NEXUS from the **command line** or from a **web browser interface** with a dark-themed UI, live progress streaming, clickable links to every supporting paper, a Fast/Quality speed toggle, and downloadable reports.

---

## Part 1 — Installing the Tools You Need

You need three things, in this order: **Python**, **Git**, and **Ollama**.

### Step 1.1 — Open a Terminal

- **Mac:** Press `Cmd + Space`, type `Terminal`, press Enter.
- **Windows:** Press the `Windows key`, type `PowerShell`, press Enter.
- **Linux:** Press `Ctrl + Alt + T`.

### Step 1.2 — Install Python

Check if it's already installed:

```bash
python3 --version
```

If you see `Python 3.10` or higher, skip to Step 1.3.

If not:
- **Mac:** Download from [python.org/downloads](https://www.python.org/downloads/), run the installer, keep default options.
- **Windows:** Download from [python.org/downloads](https://www.python.org/downloads/). **Important:** check **"Add Python to PATH"** on the first installer screen before clicking Install.
- **Linux:** `sudo apt update && sudo apt install python3 python3-pip`

NEXUS was built and tested on **Python 3.11.8**; any 3.10+ should work.

### Step 1.3 — Install Git

```bash
git --version
```

If you see a version number, skip ahead. Otherwise:
- **Mac:** Running `git --version` for the first time usually offers to install it automatically — click Install.
- **Windows/Linux:** Download from [git-scm.com/downloads](https://git-scm.com/downloads), or `sudo apt install git` on Linux.

### Step 1.4 — Mac only: Command Line Tools (no Xcode needed)

Some Python packages need a compiler to install correctly. On Mac, this comes from **Xcode Command Line Tools** — a small, separate download, **not the full Xcode app**. The full Xcode app from the App Store is several GB and is a complete iOS/Mac app development suite — you do **not** need it for NEXUS. Command Line Tools is a much smaller, standalone package that just provides the compiler and related tools.

**If you have a brand new Mac with nothing installed, follow this exactly:**

1. Open Terminal (Step 1.1 above).
2. Type this command and press Enter:
   ```bash
   xcode-select --install
   ```
3. A system popup window will appear, titled something like *"The xcode-select command requires the command line developer tools."* It will show two buttons: **"Get Xcode"** and **"Install."**
4. Click **"Install"** — NOT "Get Xcode." ("Get Xcode" sends you to the App Store for the full multi-GB app, which you don't want.)
5. Another popup will show a license agreement. Click **"Agree."**
6. It will now download and install in the background — this typically takes 5-15 minutes depending on your internet connection. You'll see a progress bar in a small window.
7. When it finishes, the window closes automatically (or shows "The software was installed"). You can close it.
8. Confirm it worked by running:
   ```bash
   xcode-select -p
   ```
   This should print a path like `/Library/Developer/CommandLineTools` — if you see a path (any path), it worked.

**If you already have it installed**, running `xcode-select --install` in step 2 will instead show an error like *"command line tools are already installed"* — that's fine, it means you can skip straight to Part 2.

You only ever need to do this **once per Mac**, not once per project — it's a system-level tool, not something tied to NEXUS specifically.

> **Windows users:** the equivalent (only needed if a future dependency requires compilation, which is unlikely for NEXUS's current dependencies) is [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) — in its installer, check "Desktop development with C++" and install. Most Windows users will never need this for NEXUS as it stands today.

> **Linux users:** if you ever see a compiler error, run `sudo apt install build-essential` (Ubuntu/Debian) — this is the equivalent toolset.

### Step 1.5 — Install Ollama (runs the AI model locally)

Download from [ollama.com/download](https://ollama.com/download), run the installer (default options are fine), then confirm:

```bash
ollama --version
```

---

## Part 2 — Getting the NEXUS Code

```bash
cd ~
git clone https://github.com/vigneshm2311-cyber/nexus.git
cd nexus
```

Every command for the rest of this guide runs from inside this `nexus` folder.

---

## Part 3 — Setting Up the Local AI Model

NEXUS uses **two models**, switchable per-run from the web UI:

- **`mistral`** (default, "Quality" mode) — slower, more reliable, used for real research
- **`llama3.2`** ("Fast" mode) — quicker, slightly less precise, useful for quick tests

### Download both

```bash
ollama pull mistral
ollama pull llama3.2
```

`mistral` is about 4.4 GB; `llama3.2` is about 2 GB. This may take several minutes depending on your internet speed.

### Confirm they're there

```bash
ollama list
```

You should see both `mistral` and `llama3.2` listed.

> **Hardware note:** `mistral` needs roughly 8 GB of free RAM to run comfortably. On 8 GB machines or less, lean on Fast mode (`llama3.2`) more often — it's noticeably lighter.

---

## Part 4 — Installing NEXUS's Dependencies

```bash
pip3 install -r requirements.txt
```

This installs: `flask` (web interface), `httpx` and `requests` (network requests to the literature databases), `python-dotenv` (configuration), `anyio` (async support). All are pure Python — no compiler needed for these specifically, but Step 1.4 above covers you if a future dependency ever needs one.

If `pip3` isn't recognized, try `pip install -r requirements.txt` or `python3 -m pip install -r requirements.txt`.

> **Permission errors:** add `--user` to the end of the command.

---

## Part 5 — Configuration

Create a `.env` file in the `nexus` folder — this isn't included in the downloaded code and you need to create it yourself.

**Mac/Linux:**
```bash
cat > .env << 'EOF'
LLM_BACKEND=ollama
OLLAMA_MODEL=mistral
OLLAMA_BASE_URL=http://localhost:11434
GROK_API_KEY=
GROK_MODEL=grok-beta
EOF
```

**Windows (PowerShell):**
```powershell
@"
LLM_BACKEND=ollama
OLLAMA_MODEL=mistral
OLLAMA_BASE_URL=http://localhost:11434
GROK_API_KEY=
GROK_MODEL=grok-beta
"@ | Out-File -Encoding utf8 .env
```

`OLLAMA_MODEL=mistral` here is just the *default* — the web UI's Speed toggle (see below) overrides it per-run, so you don't need to edit this file again just to switch models. The `GROK_*` lines are unused legacy fields; leave them blank.

---

## Part 6 — Running NEXUS

### Option A — Web Browser Interface (recommended)

```bash
python3 app.py
```

Open **`http://127.0.0.1:8080`** in your browser. You'll see:

- A research goal input field
- Sliders for rounds, hypotheses per round, and papers per hypothesis
- A **Speed toggle**: ⚡ Fast (`llama3.2`) or 🎯 Quality (`mistral`, default)
- A live progress log as each agent runs, showing which model is active
- On completion: ranked hypothesis cards with score bars, critiques, a collapsible **"Supporting literature"** list with clickable links to every real paper, a section of cross-domain analogies, a section of identified research gaps, and download buttons for the full Markdown/JSON report

To stop the server, press `Ctrl + C` in the terminal.

### Option B — Command Line

```bash
python3 run.py "Bakuchiol for anti-ageing?" --rounds 3 --hypotheses 5 --papers 5
```

- `--rounds` — how many generate→critique→evolve cycles to run
- `--hypotheses` — how many hypotheses per round
- `--papers` — how many papers to fetch per hypothesis

Reports save to `outputs/` as both `.md` (human-readable, with clickable paper links) and `.json` (structured data, includes full paper metadata).

---

## Troubleshooting

**"command not found: python3 / git / ollama"**
Close and reopen your terminal, then retry. If it persists, revisit Part 1.

**A pip install step fails mentioning a compiler, `gcc`, or `clang`**
Mac: run `xcode-select --install` (see Step 1.4). Windows: install the Visual C++ Build Tools linked above.

**"Connection refused" or errors mentioning `localhost:11434`**
Ollama isn't running. Run `ollama serve` in one terminal window, then run NEXUS commands in a second window.

**Port conflicts on Mac (AirPlay uses port 5000)**
NEXUS already uses port 8080 specifically to avoid this. If you still see a conflict, turn off AirPlay Receiver in System Settings → General → AirDrop & Handoff.

**Everything is running very slowly**
Expected with local models — `mistral` ("Quality" mode) is deliberately slower but more reliable; a full multi-round run can take 15-30+ minutes. Switch to "Fast" mode (`llama3.2`) for quicker iteration if you're just testing.

**A paper link 404s or looks broken**
Most sources (PubMed, OpenAlex, Europe PMC, ClinicalTrials.gov) produce reliable direct links. bioRxiv/medRxiv links are reconstructed from a stored DOI string and are less consistently tested — if one doesn't resolve, search the paper title directly on biorxiv.org or medrxiv.org.

---

## Architecture Reference

```
nexus/
├── app.py                        # Flask web server + live progress streaming
├── run.py                        # Command-line entry point
├── requirements.txt              # Python package dependencies
├── .env                          # Your local configuration (you create this)
├── model_comparison.py           # Diagnostic tool comparing local models on real failure cases
├── templates/                    # Web interface HTML pages
├── static/                       # Web interface styling
├── nexus/
│   ├── config.py                 # Settings (reads from .env)
│   ├── conductor.py               # Orchestrates the full 7-agent pipeline
│   ├── llm.py                     # Talks to Ollama, handles retries
│   ├── db.py                      # SQLite storage for sessions/hypotheses/papers
│   ├── output.py                  # Generates Markdown/JSON reports with clickable paper links
│   ├── paper_links.py             # Builds real URLs from each source's stored ID format
│   ├── agents/
│   │   ├── genesis.py             # Hypothesis generation
│   │   ├── fetcher.py             # Async literature search across 6 sources
│   │   ├── critic.py              # Evidence-based critique, batched relevance scoring
│   │   ├── ranker.py              # Novelty/evidence/feasibility scoring, 3x confidence
│   │   ├── evolver.py             # Combines and strengthens top hypotheses each round
│   │   ├── analogy_bridge.py      # Cross-domain analogy search
│   │   └── gap_detector.py        # Literature gap identification
│   ├── sources/
│   │   ├── pubmed.py              # NCBI Entrez API
│   │   ├── europe_pmc.py          # EBI REST API
│   │   ├── openalex.py            # Open scholarly graph
│   │   ├── biorxiv.py             # bioRxiv/medRxiv preprints (with retry on 503)
│   │   ├── clinical_trials.py     # ClinicalTrials.gov registry
│   │   ├── uniprot.py             # Protein/gene database
│   │   ├── _query_utils.py        # Query normalisation (Greek letters, ASCII cleaning)
│   │   ├── chembl.py               # NOT ACTIVE — left over from an earlier iteration, not imported by fetcher.py
│   │   └── semantic_scholar.py     # NOT ACTIVE — removed from the pipeline for reliability issues, file kept for reference only
│   ├── ingestion/
│   │   └── session.py             # Creates a research session, extracts domain/keywords
│   └── utils/
│       └── rate_limiter.py         # NOT CURRENTLY WIRED IN — available for future use, not called by any source yet
└── outputs/                       # Generated reports land here
```

---

## Configuration Reference

| Setting | Where | Default | What it does |
|---|---|---|---|
| `LLM_BACKEND` | `.env` | `ollama` | AI provider (`ollama` is the local, free option) |
| `OLLAMA_MODEL` | `.env` | `mistral` | Default model; overridden per-run by the web UI's Speed toggle |
| `OLLAMA_BASE_URL` | `.env` | `http://localhost:11434` | Where Ollama listens locally |
| `max_rounds` | `nexus/config.py` | 3 | Research rounds per session |
| `hypotheses_per_round` | `nexus/config.py` | 5 | Hypotheses generated per round |
| `papers_per_hypothesis` | `nexus/config.py` | 5 | Papers fetched per hypothesis per source query |
| `top_k_evolve` | `nexus/config.py` | 3 | How many top hypotheses survive into Evolver each round |

---

## Known Limitations & Honest Caveats

This project has been built and iteratively fixed through real testing, not just designed on paper. A few things worth knowing:

- **bioRxiv/medRxiv have no real search API.** The official API only supports bulk date-range downloads, not keyword search — NEXUS fetches a window of recent papers and filters client-side, which is the standard workaround used elsewhere too, not a bug. Expect this source to occasionally return less topically precise results than PubMed/OpenAlex/Europe PMC.
- **Evidence quality varies by hypothesis.** Critic is explicitly instructed to call out when supporting papers don't really address a hypothesis's specific claim, rather than defaulting to generic praise — but it's still an AI judgment call, not peer review. Always verify anything that matters against the actual linked papers.
- **`top_k_evolve` controls breadth vs. focus.** Each round only the top-K hypotheses carry forward into the next round's evolution; a low value narrows the search quickly, a higher value preserves more variety at the cost of more LLM calls per round.
- **Quality mode (`mistral`) is meaningfully slower than Fast mode (`llama3.2`)** — sometimes by 2x or more per call, and Critic's relevance-scoring step alone can take a minute or more per hypothesis on Quality mode with many papers. This is a deliberate quality-over-speed tradeoff, not unintended sluggishness.
- **NEXUS is a research assistant, not a source of medical or scientific fact.** Treat its output as a structured, evidence-linked starting point for human research — not a conclusion.

---

## License

MIT
