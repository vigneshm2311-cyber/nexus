# ⬡ NEXUS — Multi-Agent Research Intelligence Platform

A local, privacy-first research intelligence platform that generates, evolves, and ranks scientific hypotheses using a pipeline of specialised AI agents — powered entirely by a local LLM (no cloud APIs, no API keys, no subscription).

This guide assumes **zero prior coding experience or installed tools**. Every step is spelled out. If you've never opened a terminal before, start at Part 1.

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

---

## 1. What You're Building

NEXUS takes a research question (e.g. *"Bakuchiol for anti-ageing?"*) and runs it through a pipeline of AI agents that:

1. **Genesis** — generates several candidate scientific hypotheses
2. **Fetcher** — searches 6 real scientific databases (PubMed, Europe PMC, OpenAlex, ClinicalTrials.gov, bioRxiv/medRxiv) for supporting papers
3. **Critic** — reads the papers and critically evaluates each hypothesis
4. **Ranker** — scores hypotheses on novelty, evidence strength, and feasibility
5. **Analogy Bridge** — looks for similar mechanisms in unrelated scientific fields
6. **Gap Detector** — identifies unanswered questions in the field
7. **Evolver** — combines the best hypotheses into stronger, more specific ones for the next round

Everything runs **on your own computer**. The AI model (the "brain" doing the reasoning) runs locally via a free tool called **Ollama** — nothing is sent to the cloud, and there's no per-use cost.

By the end of this guide, you'll be able to run NEXUS either from a **command line** or from a **web browser interface** with a dark-themed UI showing live progress.

---

## Part 1 — Installing the Tools You Need

You need three things, in this order: **Python** (the programming language NEXUS is written in), **Git** (to download the code), and **Ollama** (to run the AI model locally).

### Step 1.1 — Open a Terminal

- **On Mac:** Press `Cmd + Space`, type `Terminal`, press Enter.
- **On Windows:** Press the `Windows key`, type `PowerShell`, press Enter.
- **On Linux:** Press `Ctrl + Alt + T`.

A black or white window with text will open. This is the terminal — it's where you'll type every command in this guide. Type or paste a command, then press Enter to run it.

### Step 1.2 — Install Python

Check if Python is already installed:

```bash
python3 --version
```

If you see something like `Python 3.11.8`, you already have it — skip to Step 1.3.

If you see an error like "command not found":

- **Mac:** Go to [python.org/downloads](https://www.python.org/downloads/), download the macOS installer, open it, and click through the installation wizard (keep all default options).
- **Windows:** Go to [python.org/downloads](https://www.python.org/downloads/), download the Windows installer. **Important:** on the first screen of the installer, check the box that says **"Add Python to PATH"** before clicking Install.
- **Linux:** Run `sudo apt update && sudo apt install python3 python3-pip` (Ubuntu/Debian) or the equivalent for your distribution.

After installing, close and reopen your terminal, then run `python3 --version` again to confirm it worked. NEXUS was built and tested on **Python 3.11.8** — any 3.10+ version should work fine.

### Step 1.3 — Install Git

Check if Git is already installed:

```bash
git --version
```

If you see a version number, skip to Step 1.4.

If not:
- **Mac:** Running `git --version` for the first time usually triggers a popup offering to install it automatically — click Install. If not, download from [git-scm.com/downloads](https://git-scm.com/downloads).
- **Windows:** Download from [git-scm.com/downloads](https://git-scm.com/downloads), run the installer, keep all default options.
- **Linux:** `sudo apt install git`

### Step 1.4 — Install Ollama (runs the AI model locally)

Go to [ollama.com/download](https://ollama.com/download) and download the installer for your operating system. Open it and follow the installation steps (default options are fine).

Confirm it installed correctly:

```bash
ollama --version
```

You should see a version number. Ollama runs as a background service — you don't need to manually start it most of the time, but if a later step says it can't connect, see [Troubleshooting](#troubleshooting).

---

## Part 2 — Getting the NEXUS Code

### Step 2.1 — Choose where to put it

Decide where on your computer you want the NEXUS folder to live. For example, your home folder. Navigate there in the terminal:

```bash
cd ~
```

(`cd` means "change directory" — this moves you to your home folder.)

### Step 2.2 — Download the code

```bash
git clone https://github.com/vigneshm2311-cyber/nexus.git
cd nexus
```

The first command downloads ("clones") the entire project into a new folder called `nexus`. The second command moves you inside that folder — **every command for the rest of this guide should be run from inside this `nexus` folder.**

---

## Part 3 — Setting Up the Local AI Model

NEXUS needs a language model to actually do the reasoning. We use **Mistral** — a free, open model that runs entirely on your machine through Ollama.

### Step 3.1 — Download the model

```bash
ollama pull mistral
```

This downloads about 4.4 GB — it may take a few minutes depending on your internet speed. You'll see a progress bar.

### Step 3.2 — Confirm it's there

```bash
ollama list
```

You should see `mistral` in the list.

> **Hardware note:** Mistral needs roughly 8 GB of free RAM to run comfortably. If your machine has 8 GB total RAM or less, consider using the smaller `llama3.2` model instead (`ollama pull llama3.2`) — it's faster but occasionally less precise with formatting. You can switch between them later just by changing one line in a config file (see [Part 5](#part-5--configuration)).

---

## Part 4 — Installing NEXUS's Dependencies

NEXUS relies on a handful of Python packages (pre-written code libraries) to function — things like a library for talking to web APIs, and a library for the web interface.

### Step 4.1 — Install the packages

From inside the `nexus` folder:

```bash
pip3 install -r requirements.txt
```

This reads the `requirements.txt` file in the project and installs everything listed: `flask` (web interface), `httpx` (fast network requests), `requests` (network requests), `python-dotenv` (configuration), `anyio` (async support).

If `pip3` isn't recognized, try `pip install -r requirements.txt` instead — depending on your system, the command might be named slightly differently.

> **If you see permission errors:** add `--user` to the end of the command: `pip3 install -r requirements.txt --user`

---

## Part 5 — Configuration

NEXUS reads its settings from a file called `.env` in the project folder. This file isn't included in the downloaded code (it's deliberately excluded for privacy/security reasons in most projects) — you need to create it yourself.

### Step 5.1 — Create the `.env` file

From inside the `nexus` folder, run:

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

This tells NEXUS: use Ollama as the AI backend, use the `mistral` model specifically, and connect to Ollama's default local address. The `GROK_*` lines are leftover support for a different AI provider NEXUS doesn't currently use — they can stay empty.

> If you chose `llama3.2` instead of `mistral` in Part 3, change `OLLAMA_MODEL=mistral` to `OLLAMA_MODEL=llama3.2` in the file above.

---

## Part 6 — Running NEXUS

You're ready. NEXUS can be run two ways: from the command line directly, or through a web browser interface.

### Option A — Command Line

```bash
python3 run.py "Bakuchiol for anti-ageing?" --rounds 3 --hypotheses 5 --papers 5
```

Replace the question in quotes with whatever you want to research. The numbers after each flag control how thorough the research is:
- `--rounds` — how many cycles of generate-critique-evolve to run (more = deeper, but slower)
- `--hypotheses` — how many hypotheses to generate per round
- `--papers` — how many papers to fetch per hypothesis

You'll see live progress printed in the terminal as each agent runs. When it finishes, it prints the top-ranked hypotheses and saves a full report to the `outputs/` folder as both a `.md` (Markdown, human-readable) file and a `.json` (structured data) file.

### Option B — Web Browser Interface

```bash
python3 app.py
```

You'll see something like:
```
* Running on http://127.0.0.1:8080
```

Open your web browser and go to **`http://127.0.0.1:8080`**. You'll see a dark-themed interface where you can type your research question, adjust the rounds/hypotheses/papers settings with a form, and watch the agents run live with a progress log. When it finishes, you'll see the ranked hypotheses as cards with score bars, critiques, and buttons to download the full report.

To stop the web server, go back to the terminal and press `Ctrl + C`.

---

## Troubleshooting

**"command not found: python3" / "command not found: git" / "command not found: ollama"**
The relevant tool isn't installed correctly, or your terminal needs to be restarted. Close the terminal completely and reopen it, then try again. If it still fails, revisit the install steps in Part 1.

**"Connection refused" or errors mentioning `localhost:11434`**
Ollama isn't running. Try starting it manually:
```bash
ollama serve
```
Leave that terminal window open and running, then open a **second** terminal window to run NEXUS commands.

**`AttributeError: 'ResearchConfig' object has no attribute ...`**
This usually means the code and the `.env`/config files are out of sync — re-check that `.env` exists and matches Part 5 exactly, and that you pulled the latest code with `git pull` if you'd already cloned it earlier.

**Port 5000 conflicts on Mac (AirPlay)**
If `app.py` complains a port is already in use, either turn off AirPlay Receiver (System Settings → General → AirDrop & Handoff → AirPlay Receiver → Off), or NEXUS is already configured to use port 8080 instead, which avoids this entirely.

**Everything seems to be running very slowly**
Local AI models are computationally heavy. Expect a single research round to take anywhere from 1-10+ minutes depending on your hardware and which model you chose. `mistral` is noticeably slower than `llama3.2` but more reliable; this is a real tradeoff, not a bug.

**`pip3: command not found`**
Try `pip` instead of `pip3`, or `python3 -m pip install -r requirements.txt`.

---

## Architecture Reference

```
nexus/
├── app.py                        # Flask web server + live progress streaming
├── run.py                        # Command-line entry point
├── requirements.txt              # Python package dependencies
├── .env                          # Your local configuration (you create this)
├── templates/                    # Web interface HTML pages
├── static/                       # Web interface styling
├── nexus/
│   ├── config.py                 # Settings (reads from .env)
│   ├── conductor.py              # Orchestrates the full agent pipeline
│   ├── llm.py                    # Talks to Ollama
│   ├── db.py                     # SQLite database (stores sessions, hypotheses, papers)
│   ├── output.py                 # Generates the final Markdown/JSON reports
│   ├── agents/                   # The 7 AI agents (genesis, fetcher, critic, ranker, evolver, analogy_bridge, gap_detector)
│   └── sources/                  # Connectors to PubMed, OpenAlex, Europe PMC, etc.
└── outputs/                      # Where your research reports get saved
```

## Configuration Reference

These can all be adjusted by editing `nexus/config.py` directly, or via `.env` for the LLM settings:

| Setting | Default | What it does |
|---|---|---|
| `LLM_BACKEND` | `ollama` | Which AI provider to use (`ollama` is the local, free option) |
| `OLLAMA_MODEL` | `mistral` | Which local model Ollama should run |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Where Ollama is listening (default rarely needs changing) |
| `max_rounds` | 3 | How many research rounds to run |
| `hypotheses_per_round` | 5 | Hypotheses generated per round |
| `papers_per_hypothesis` | 5 | Papers fetched per hypothesis |
| `top_k_evolve` | 2 | How many top hypotheses get "evolved" into the next round |

---

## A Note on What This Project Is and Isn't

NEXUS is a **research assistant**, not a source of medical or scientific fact. Every hypothesis it generates needs to be verified against real literature before being taken seriously — that's the whole point of the Critic and Ranker agents, but they're AI judgment calls, not peer review. Treat NEXUS's output as a structured starting point for human research, not a conclusion.
