import sys
import json
import queue
import threading
from flask import Flask, render_template, request, Response, stream_with_context, send_file, abort
from nexus.config import ResearchConfig
from nexus.conductor import run
from nexus.output import generate
from nexus.db import get_conn, get_papers_for_hypothesis
from nexus.paper_links import build_paper_url

app = Flask(__name__)

# ── Global progress queue (one run at a time for now) ────────────────────────
_progress_queue = queue.Queue()

class QueueLogger:
    """Intercepts print() output and pushes lines to the SSE queue."""
    def __init__(self, q):
        self.q = q
        self._original = sys.stdout

    def write(self, msg):
        self._original.write(msg)
        if msg.strip():
            self.q.put({"type": "log", "text": msg.rstrip()})

    def flush(self):
        self._original.flush()


def _row_get(row, key, default=""):
    """Safe field access that works for both sqlite3.Row and plain dicts."""
    try:
        value = row[key]
        return value if value is not None else default
    except (IndexError, KeyError):
        return default


def _attach_papers(result, config):
    """Fetches papers for each ranked hypothesis and attaches them with
    clickable URLs, so the browser-side results page can show supporting
    literature the same way the markdown/JSON reports do."""
    conn = get_conn(config)
    enriched = []
    for h in result["ranked"]:
        papers = get_papers_for_hypothesis(conn, h["hypothesis_id"])
        papers_payload = []
        for p in papers:
            title  = _row_get(p, "title", "")
            source = _row_get(p, "source", "")
            pmid   = _row_get(p, "pmid", "")
            papers_payload.append({
                "title" : title,
                "source": source,
                "url"   : build_paper_url(source, pmid),
            })
        h_with_papers = dict(h)
        h_with_papers["papers"] = papers_payload
        enriched.append(h_with_papers)
    return enriched


def run_pipeline(goal, config):
    """Runs NEXUS in a background thread, pushes results to queue when done."""
    try:
        result = run(goal, config)
        md_path, json_path = generate(result, config)
        ranked_with_papers = _attach_papers(result, config)
        _progress_queue.put({
            "type": "done",
            "ranked": ranked_with_papers,
            "analogies": result.get("analogies", {}),
            "gaps": result.get("gaps", {}),
            "md_path": md_path,
            "json_path": json_path,
        })
    except Exception as e:
        _progress_queue.put({"type": "error", "text": str(e)})

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/run", methods=["POST"])
def run_research():
    goal       = request.form.get("goal", "").strip()
    rounds     = int(request.form.get("rounds", 3))
    hypotheses = int(request.form.get("hypotheses", 5))
    papers     = int(request.form.get("papers", 5))

    if not goal:
        return render_template("index.html", error="Please enter a research goal.")

    config = ResearchConfig()
    config.max_rounds            = rounds
    config.hypotheses_per_round  = hypotheses
    config.papers_per_hypothesis = papers
    config.validate()

    # Redirect stdout so NEXUS print() calls feed the SSE queue
    sys.stdout = QueueLogger(_progress_queue)

    thread = threading.Thread(target=run_pipeline, args=(goal, config), daemon=True)
    thread.start()

    return render_template("progress.html", goal=goal)

@app.route("/stream")
def stream():
    def event_stream():
        while True:
            try:
                msg = _progress_queue.get(timeout=120)
                yield f"data: {json.dumps(msg)}\n\n"
                if msg["type"] in ("done", "error"):
                    sys.stdout = sys.__stdout__   # restore stdout
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'log', 'text': '[timeout] No activity for 2 minutes.'})}\n\n"
                break

    return Response(stream_with_context(event_stream()),
                    mimetype="text/event-stream")

@app.route("/results")
def results():
    return render_template("results.html")

@app.route("/download")
def download():
    path = request.args.get("path", "")
    import os
    if not path or not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True)

if __name__ == "__main__":
    app.run(host='127.0.0.1', port=8080, debug=False, threaded=True)
