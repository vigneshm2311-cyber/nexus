import sqlite3
from nexus.config import ResearchConfig

def get_conn(config: ResearchConfig) -> sqlite3.Connection:
    conn = sqlite3.connect(config.db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(config: ResearchConfig):
    with get_conn(config) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                goal TEXT NOT NULL,
                domain TEXT,
                keywords TEXT,
                status TEXT DEFAULT 'running',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS hypotheses (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                text TEXT NOT NULL,
                round INTEGER NOT NULL,
                parent_id TEXT,
                score REAL DEFAULT 0.0,
                novelty REAL DEFAULT 0.0,
                evidence REAL DEFAULT 0.0,
                feasibility REAL DEFAULT 0.0,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE TABLE IF NOT EXISTS papers (
                id TEXT PRIMARY KEY,
                hypothesis_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                pmid TEXT,
                title TEXT,
                abstract TEXT,
                source TEXT,
                relevance REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (hypothesis_id) REFERENCES hypotheses(id)
            );

            CREATE TABLE IF NOT EXISTS agent_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                round INTEGER NOT NULL,
                agent TEXT NOT NULL,
                input_summary TEXT,
                output_summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

def insert_session(conn, session_id, goal, domain, keywords):
    conn.execute(
        "INSERT INTO sessions (id, goal, domain, keywords) VALUES (?, ?, ?, ?)",
        (session_id, goal, domain, ",".join(keywords))
    )
    conn.commit()

def insert_hypothesis(conn, h_id, session_id, text, round_num, parent_id=None):
    conn.execute(
        "INSERT INTO hypotheses (id, session_id, text, round, parent_id) VALUES (?, ?, ?, ?, ?)",
        (h_id, session_id, text, round_num, parent_id)
    )
    conn.commit()

def update_hypothesis_score(conn, h_id, score, novelty, evidence, feasibility):
    conn.execute(
        "UPDATE hypotheses SET score=?, novelty=?, evidence=?, feasibility=? WHERE id=?",
        (score, novelty, evidence, feasibility, h_id)
    )
    conn.commit()

def insert_paper(conn, p_id, hypothesis_id, session_id, pmid, title, abstract, source, relevance):
    conn.execute(
        "INSERT OR IGNORE INTO papers (id, hypothesis_id, session_id, pmid, title, abstract, source, relevance) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (p_id, hypothesis_id, session_id, pmid, title, abstract, source, relevance)
    )
    conn.commit()

def log_agent(conn, session_id, round_num, agent, input_summary, output_summary):
    conn.execute(
        "INSERT INTO agent_logs (session_id, round, agent, input_summary, output_summary) VALUES (?, ?, ?, ?, ?)",
        (session_id, round_num, agent, input_summary, output_summary)
    )
    conn.commit()

def get_hypotheses_by_round(conn, session_id, round_num):
    return conn.execute(
        "SELECT * FROM hypotheses WHERE session_id=? AND round=? ORDER BY score DESC",
        (session_id, round_num)
    ).fetchall()

def get_papers_for_hypothesis(conn, hypothesis_id):
    return conn.execute(
        "SELECT * FROM papers WHERE hypothesis_id=?",
        (hypothesis_id,)
    ).fetchall()

def get_top_hypotheses(conn, session_id, k=2):
    return conn.execute(
        "SELECT * FROM hypotheses WHERE session_id=? ORDER BY score DESC LIMIT ?",
        (session_id, k)
    ).fetchall()
