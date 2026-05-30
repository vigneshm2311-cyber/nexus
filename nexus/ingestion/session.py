import uuid
from nexus.db import insert_session
from nexus.ingestion.parser import parse_goal

def create_session(conn, goal: str) -> dict:
    parsed = parse_goal(goal)
    session_id = str(uuid.uuid4())
    insert_session(conn, session_id, parsed["goal"], parsed["domain"], parsed["keywords"])
    return {
        "session_id": session_id,
        **parsed
    }
